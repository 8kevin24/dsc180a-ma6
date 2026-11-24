#!/usr/bin/env bash
# Stop hook: the agent may only finish its turn on a green suite.
#
# The PostToolUse hook runs only tests/test_leakage.py and only after
# Edit/Write under src/. It never sees a Bash-made change, a broken contract
# test, or a tampered raw file. This runs the whole suite (including the
# raw-file sha256 test) when the agent tries to stop; exit 2 sends the
# failures back and makes it keep working.
set -uo pipefail

PY=$(command -v python || command -v python3)
payload=$(cat)

# Claude Code sets stop_hook_active when the agent is already continuing
# because of this hook. Let it stop the second time rather than loop forever;
# the failures are already in front of it.
active=$(printf '%s' "$payload" | "$PY" -c \
  'import json,sys; print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())' 2>/dev/null || echo false)
[ "$active" = "true" ] && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if ! out=$("$PY" -m pytest tests/ -q 2>&1); then
  echo "Not done: the test suite is red. Fix it before finishing." >&2
  echo "$out" | grep -E "^(FAILED|ERROR)|passed|failed" | tail -15 >&2
  exit 2
fi
exit 0
