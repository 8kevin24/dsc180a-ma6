#!/usr/bin/env bash
# PreToolUse hook on Bash: refuse shell commands that write into data/raw/.
#
# The Edit/Write deny rules in settings.json do not cover Bash, so a
# `cp fixed.csv data/raw/bike_daily.csv` walks past them and past the
# PostToolUse leakage hook (Exercise 2, fault 4). This runs *before* the
# command; exit 2 blocks it and sends stderr to the agent.
#
# It is a filter on the command string, not a sandbox: an obfuscated
# command can slip through. The sha256 check in `make data` and
# tests/test_contract.py::test_raw_file_is_unmodified is the backstop.
set -uo pipefail

PY=$(command -v python || command -v python3)
payload=$(cat)
if ! cmd=$(printf '%s' "$payload" | "$PY" -c \
  'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))'); then
  echo "guard_raw.sh: could not parse hook payload with $PY" >&2
  exit 2
fi
cmd=${cmd//\\//}   # Windows backslashes -> forward slashes

# Only commands that mention data/raw are interesting.
case "$cmd" in
  *data/raw*) ;;
  *) exit 0 ;;
esac

# Writers: redirection into data/raw; cp/install whose *destination* (last
# argument) is in data/raw (copying out is fine); mv/rm/touch/tee/dd/ln/
# truncate touching data/raw at all; in-place sed; pandas/open() writes.
if printf '%s' "$cmd" | grep -Eq \
  '(>{1,2}[[:space:]]*[^[:space:]]*data/raw)|(^|[;&|[:space:]])(cp|install)[[:space:]][^;&|]*[[:space:]][^[:space:];&|]*data/raw[^[:space:];&|]*[[:space:]]*($|[;&|])|(^|[;&|[:space:]])(mv|rm|touch|tee|dd|ln|truncate)[[:space:]][^;&|]*data/raw|sed[[:space:]]+(-[a-zA-Z]*i|--in-place)[^;&|]*data/raw|to_csv\([^)]*data/raw|open\([^)]*data/raw[^)]*["'"'"'][wa]'; then
  # Restoring the pinned file is the one write we want to allow.
  if printf '%s' "$cmd" | grep -Eq '^[[:space:]]*git[[:space:]]+(checkout|restore)[[:space:]]+(--[[:space:]]+)?data/raw/?'; then
    exit 0
  fi
  echo "Blocked: this command writes to data/raw/, which is immutable (sha256 pinned in src/config.py)." >&2
  echo "  command: $cmd" >&2
  echo "Write derived data to data/processed/ instead. To restore the raw file: git checkout -- data/raw/" >&2
  exit 2
fi
exit 0
