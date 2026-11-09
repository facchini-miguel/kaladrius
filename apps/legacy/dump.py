"""Reads the rows of a MySQL dump (phpMyAdmin/mysqldump INSERT statements) without MySQL.

Only what the legacy Odonto System dumps use: INSERT INTO `table` (`col`, ...) VALUES
(...), (...); with numbers, NULL and quoted strings (MySQL backslash escapes and
doubled quotes).
"""

import re
from collections import defaultdict

_INSERT = re.compile(r"INSERT INTO `(\w+)`\s*(?:\(([^)]*)\))?\s*VALUES\s*", re.IGNORECASE)
_ESCAPES = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}


class InvalidDump(ValueError):
    pass


def _values(text, start):
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
            raise InvalidDump(f"Unexpected character at position {i}: {c!r}")
        elif c == "'":
            parts, i = [], i + 1
            while True:
                if i >= n:
                    raise InvalidDump("Text without a closing quote.")
                c = text[i]
                if c == "\\" and i + 1 < n:
                    parts.append(_ESCAPES.get(text[i + 1], text[i + 1]))
                    i += 2
                elif c == "'" and text.startswith("''", i):
                    parts.append("'")
                    i += 2
                elif c == "'":
                    i += 1
                    break
                else:
                    end = i
                    while end < n and text[end] not in "\\'":
                        end += 1
                    parts.append(text[i:end])
                    i = end
            row.append("".join(parts))
        else:
            end = i
            while end < n and text[end] not in ",)":
                end += 1
            raw = text[i:end].strip()
            if raw.upper() == "NULL":
                row.append(None)
            else:
                try:
                    row.append(float(raw) if "." in raw else int(raw))
                except ValueError as error:
                    raise InvalidDump(f"Invalid value: {raw!r}") from error
            i = end
    raise InvalidDump("End of file inside an INSERT.")


def read_tables(text, tables=None):
    """{table: [row dict]} for every INSERT in the dump (optionally only some tables)."""
    result = defaultdict(list)
    position = 0
    while found_one := _INSERT.search(text, position):
        table, columns = found_one.group(1), found_one.group(2)
        rows, position = _values(text, found_one.end())
        if tables is not None and table not in tables:
            continue
        if columns is None:
            raise InvalidDump(f"INSERT without column names in the table {table}.")
        names = [name.strip().strip("`") for name in columns.split(",")]
        for row in rows:
            if len(row) != len(names):
                raise InvalidDump(f"Row with {len(row)} values in {table}.")
            result[table].append(dict(zip(names, row, strict=True)))
    return dict(result)
