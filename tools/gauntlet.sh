#!/usr/bin/env bash
# cds-callbook GAUNTLET：一条命令跑完全部关卡，遇错即停；新鲜性靠机制。
set -euo pipefail
cd "$(dirname "$0")/.."

# 优先使用本地 venv（ruff/pytest  pinned）
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

rm -rf .coverage coverage.xml htmlcov .pytest_cache

echo "== 1. full test suite =="
python3 -m pytest -q

echo "== 2. lint + format =="
ruff check scripts/ tests/
ruff format --check scripts/ tests/

echo "== 3. schema validate-all =="
python3 scripts/lib_ledger.py --validate-all public-ledger/
