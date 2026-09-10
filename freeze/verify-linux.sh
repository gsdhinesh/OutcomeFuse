set -e
pip install -q pydantic pyyaml
export PYTHONPATH=/w/src:/w/freeze
python - <<'PY'
import sqlite3, sys
print("linux python", sys.version.split()[0], "sqlite", sqlite3.sqlite_version)
PY
python freeze/freeze.py --check
python freeze/check_cases.py | tail -1
