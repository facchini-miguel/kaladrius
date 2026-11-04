# The server scripts of 0.54.1

Frozen copies of `deploy/servidor/atualizar.sh`, `comum.sh` and `instalar.sh` as released in
0.54.1, before the names of decision 147. `tests/test_legacy_names.py` runs them against this
repository's `deploy/` to check that a Google Cloud server still on them moves to the new names
by itself (through the bridge `deploy/servidor/comum.sh`). They are never installed; delete this
folder together with the bridge.
