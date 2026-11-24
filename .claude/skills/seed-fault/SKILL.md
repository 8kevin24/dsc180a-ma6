---
name: seed-fault
description: Seed one deliberate methodology fault, prove a test goes red and the leakage hook fires, fix it, and log real output to docs/SEEDED_FAULTS.md. Use when asked to break something on purpose, test the tests, or check whether a fault would be caught.
allowed-tools: Read, Edit, Bash(python -m pytest*), Bash(make*), Bash(git diff*), Bash(git status*), Bash(git checkout -- data/raw/*), Bash(sha256sum*)
---

# Current state (must be green before seeding)

!`python -m pytest tests/ -q 2>&1 | tail -1`

# Seeding fault: $ARGUMENTS

Do these in order. Paste real output and never paraphrase it.

1. **Name the fault in one sentence**: the file, the line, and which
   contract in `src/features.py` or `CLAUDE.md` it breaks. If the line above
   is not all-passed, stop and say so. A fault seeded on a red tree proves
   nothing.

2. **Seed it with a single `Edit`.** Seed it under `src/` so the PostToolUse
   hook fires. If the fault is in `data/raw/`, seed it with a Bash `cp`, not
   `Edit` (Edit is denied there), and say that the hook cannot see it.
   Capture `git diff`.

3. **Run `make test`.** Copy the FAILED lines and the summary line.
   - Red: note which tests caught it.
   - Green: the fault is invisible. Write the smallest test that fails
     *for this reason*. It must hand-compute its expectation from the raw
     file or a literal, not from a helper that shares the bug. Put leakage
     tests in `tests/test_leakage.py`, the only file the hook runs. Re-run
     and confirm it is red.

4. **Record the hook's verdict**: the system message it returned (exit 2
   plus stderr), or "hook silent" with the reason.

5. **Fix it**, then run `make test` until it passes. Count your tool calls from
   first red to green.

6. **Append a section to `docs/SEEDED_FAULTS.md`** with: the change (diff),
   the red test output, the hook stderr, the agent turns to fix, and one line
   on what would have caught it sooner if nothing did. For a `data/raw/`
   fault, finish with `git checkout -- data/raw/` and paste a `sha256sum`
   that starts `a6bed1577f6e4de5`.

7. Tell the user the commit message: `fault: <one line>`, with the fix in
   the body. Do not commit yourself.
