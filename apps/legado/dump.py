"""Reads the rows of a MySQL dump (phpMyAdmin/mysqldump INSERT statements) without MySQL.

Only what the legacy Odonto System dumps use: INSERT INTO `table` (`col`, ...) VALUES
(...), (...); with numbers, NULL and quoted strings (MySQL backslash escapes and
doubled quotes).
"""

import re
from collections import defaultdict

_INSERT = re.compile(r"INSERT INTO `(\w+)`\s*(?:\(([^)]*)\))?\s*VALUES\s*", re.IGNORECASE)
_ESCAPES = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}


class DumpInvalido(ValueError):
    pass


def _valores(texto, inicio):
    """Parse "(...), (...);" from `inicio`. Returns (rows, position after the ';')."""
    linhas, linha, i, n = [], None, inicio, len(texto)
    while i < n:
        c = texto[i]
        if c in " \t\r\n,":
            i += 1
        elif c == "(" and linha is None:
            linha, i = [], i + 1
        elif c == ")" and linha is not None:
            linhas.append(tuple(linha))
            linha, i = None, i + 1
        elif c == ";" and linha is None:
            return linhas, i + 1
        elif linha is None:
            raise DumpInvalido(f"Caractere inesperado na posição {i}: {c!r}")
        elif c == "'":
            partes, i = [], i + 1
            while True:
                if i >= n:
                    raise DumpInvalido("Texto sem aspas de fechamento.")
                c = texto[i]
                if c == "\\" and i + 1 < n:
                    partes.append(_ESCAPES.get(texto[i + 1], texto[i + 1]))
                    i += 2
                elif c == "'" and texto.startswith("''", i):
                    partes.append("'")
                    i += 2
                elif c == "'":
                    i += 1
                    break
                else:
                    fim = i
                    while fim < n and texto[fim] not in "\\'":
                        fim += 1
                    partes.append(texto[i:fim])
                    i = fim
            linha.append("".join(partes))
        else:
            fim = i
            while fim < n and texto[fim] not in ",)":
                fim += 1
            bruto = texto[i:fim].strip()
            if bruto.upper() == "NULL":
                linha.append(None)
            else:
                try:
                    linha.append(float(bruto) if "." in bruto else int(bruto))
                except ValueError as erro:
                    raise DumpInvalido(f"Valor inválido: {bruto!r}") from erro
            i = fim
    raise DumpInvalido("Fim do arquivo dentro de um INSERT.")


def ler_tabelas(texto, tabelas=None):
    """{table: [row dict]} for every INSERT in the dump (optionally only some tables)."""
    resultado = defaultdict(list)
    posicao = 0
    while encontrado := _INSERT.search(texto, posicao):
        tabela, colunas = encontrado.group(1), encontrado.group(2)
        linhas, posicao = _valores(texto, encontrado.end())
        if tabelas is not None and tabela not in tabelas:
            continue
        if colunas is None:
            raise DumpInvalido(f"INSERT sem nomes de colunas na tabela {tabela}.")
        nomes = [nome.strip().strip("`") for nome in colunas.split(",")]
        for linha in linhas:
            if len(linha) != len(nomes):
                raise DumpInvalido(f"Linha com {len(linha)} valores em {tabela}.")
            resultado[tabela].append(dict(zip(nomes, linha, strict=True)))
    return dict(resultado)
