#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
SKILL_DIR="$ROOT_DIR/skills/supernova-pool-intel"

OUT_DIR="$ROOT_DIR/runs/supernova-pool-intel"
mkdir -p "$OUT_DIR"

printf '[sim] running unit tests\n'
python3 -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py'

printf '[sim] running live scan smoke test\n'
python3 "$SKILL_DIR/scripts/supernova_pool_scan.py" \
  --max-pools 12 \
  --workers 6 \
  --http-workers 6 \
  --strict \
  --out-json "$OUT_DIR/sim-scan.json" \
  --out-csv "$OUT_DIR/sim-scan.csv"

printf '[sim] verifying read-only call helper\n'
python3 "$SKILL_DIR/scripts/supernova_contract_call.py" \
  --to 0x19a410046afc4203aece5fbfc7a6ac1a4f517ae2 \
  --sig 'length()(uint256)' \
  --json > "$OUT_DIR/sim-contract-call.json"

printf '[sim] done\n'
