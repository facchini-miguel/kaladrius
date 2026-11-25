#!/usr/bin/env python3
"""Copies the .env of Dokploy's Compose to /opt/kaladrius/.env without the quotes (the VPS).

Dokploy writes KEY="value"; Docker Compose reads it, but env_value of the repository's scripts
(common.sh) reads the line as it is. It runs before every kaladrius-* unit (the drop-in
/etc/systemd/system/kaladrius-.service.d/env.conf); the source stays Dokploy's.
"""

import os
import pathlib
import tempfile

src = pathlib.Path("/etc/dokploy/compose/kaladrius-sgyyve/code/.env")
dst = pathlib.Path("/opt/kaladrius/.env")
out = []
for line in src.read_text().splitlines():
    key, sep, value = line.partition("=")
    if sep and len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    out.append(f"{key}{sep}{value}")
fd, tmp = tempfile.mkstemp(dir=dst.parent, prefix=".env.")
with os.fdopen(fd, "w") as f:
    f.write("# Written by /opt/kaladrius/bin/sync-env.py from Dokploy's .env. Do not edit here.\n")
    f.write("\n".join(out) + "\n")
os.chmod(tmp, 0o600)
os.replace(tmp, dst)
