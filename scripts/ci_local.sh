#!/usr/bin/env bash
set -euo pipefail

python_cmds=("python3.10" "python3.11")

run_ci() {
  local py="$1"
  echo "==> Running CI checks with ${py}"
  "$py" -m pip install --upgrade pip
  "$py" -m pip install -e ".[dev]"
  "$py" -m ruff check src tests
  "$py" -m black --check src tests
  "$py" -m mypy src
  "$py" -m pytest --cov=src/bitegraph --cov-report=term-missing --cov-report=xml
}

ran_any=false
for py in "${python_cmds[@]}"; do
  if command -v "$py" >/dev/null 2>&1; then
    run_ci "$py"
    ran_any=true
  fi
done

if [ "$ran_any" = false ]; then
  if command -v python3 >/dev/null 2>&1; then
    echo "python3.10/3.11 not found; running with python3"
    run_ci "python3"
  else
    echo "No suitable python interpreter found" >&2
    exit 1
  fi
fi
