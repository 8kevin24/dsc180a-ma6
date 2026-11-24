#!/usr/bin/env bash
# PostToolUse hook: re-run the leakage tests whenever src/ changes.
#
# This runs AFTER the edit has landed, so it cannot prevent the write. What
# exit 2 does is send stderr back to Claude as a system message, so the
# failure is in front of the agent immediately and it cannot carry on as if
# the edit were fine. To make "done" itself conditional on green tests, add
# a Stop hook that runs `make test` and exits 2 on failure (check
# stop_hook_active in the payload to avoid looping).
set -uo pipefail

payload=$(cat)
# Use the same interpreter as the pytest call below. The starter used
# `python3`, which on Windows is a Microsoft Store stub: the parse failed,
# $path came back empty, and the hook exited 0 on every edit -- silently.
PY=$(command -v python || command -v python3)
if ! path=$(printf '%s' "$payload" | "$PY" -c \
  'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))'); then
  echo "check_leakage.sh: could not parse hook payload with $PY" >&2
  exit 2
fi
path=${path//\\//}   # Windows backslashes -> forward slashes

case "$path" in
  *src/*.py) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if ! out=$("$PY" -m pytest tests/test_leakage.py -q 2>&1); then
  echo "Leakage tests failed after editing $path:" >&2
  echo "$out" | tail -20 >&2
  exit 2
fi
exit 0
