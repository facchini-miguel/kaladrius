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


def _valores(text, start):
    """Parse "(...), (...);" from `inicio`. Returns (rows, position after the ';')."""
    rows, row, i, n = [], None, start, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n,":
            i += 1
        elif c == "(" and row is None:
            row, i = [], i + 1
        elif c == ")" and row is not None:
            rows.append(tuple(row))
            row, i = None, i + 1
        elif c == ";" and row is None:
            return rows, i + 1
        elif row is None:
            raise DumpInvalido(f"Caractere inesperado na posição {i}: {c!r}")
        elif c == "'":
            partes, i = [], i + 1
            while True:
                if i >= n:
                    raise DumpInvalido("Texto sem aspas de fechamento.")
                c = text[i]
                if c == "\\" and i + 1 < n:
                    partes.append(_ESCAPES.get(text[i + 1], text[i + 1]))
                    i += 2
                elif c == "'" and text.startswith("''", i):
                    partes.append("'")
                    i += 2
                elif c == "'":
                    i += 1
                    break
                else:
                    end = i
                    while end < n and text[end] not in "\\'":
                        end += 1
                    partes.append(text[i:end])
                    i = end
            row.append("".join(partes))
        else:
            end = i
            while end < n and text[end] not in ",)":
                end += 1
            bruto = text[i:end].strip()
            if bruto.upper() == "NULL":
                row.append(None)
            else:
                try:
                    row.append(float(bruto) if "." in bruto else int(bruto))
                except ValueError as error:
                    raise DumpInvalido(f"Valor inválido: {bruto!r}") from error
            i = end
    raise DumpInvalido("Fim do arquivo dentro de um INSERT.")


def ler_tabelas(text, tables=None):
    """{table: [row dict]} for every INSERT in the dump (optionally only some tables)."""
    resultado = defaultdict(list)
    position = 0
    while encontrado := _INSERT.search(text, position):
        table, colunas = encontrado.group(1), encontrado.group(2)
        rows, position = _valores(text, encontrado.end())
        if tables is not None and table not in tables:
            continue
        if colunas is None:
            raise DumpInvalido(f"INSERT sem nomes de colunas na tabela {table}.")
        nomes = [name.strip().strip("`") for name in colunas.split(",")]
        for row in rows:
            if len(row) != len(nomes):
                raise DumpInvalido(f"Linha com {len(row)} valores em {table}.")
            resultado[table].append(dict(zip(nomes, row, strict=True)))
    return dict(resultado)
