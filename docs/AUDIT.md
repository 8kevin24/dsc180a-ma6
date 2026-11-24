# Audit (Exercise 3)

## Part A: `/leakage-auditor` on a teammate's repo

**Teammate repo:** TODO: paste the teammate's repository URL

> **Not done yet.** This section needs a teammate's repo, and none was
> available when this file was written. To complete it: clone their repo, run
> `claude` from inside it (so their `.claude/agents/leakage-auditor.md` is
> loaded), ask *"Use the leakage-auditor subagent to review this repo's
> src/features.py and src/train.py"*, and paste its reply verbatim below.

### Auditor output (verbatim)

```
TODO: paste /leakage-auditor output
```

### My verdict

TODO: one paragraph, kept separate from the auditor's text. Which findings
change a number (name the metric and roughly how much), which I agree with,
and which are style or false positives. If it found nothing, say so here
and leave the run above as evidence.

## Part B: `agent/audit.py` on this repo

Command: `AUDIT_MODEL=claude-sonnet-5-5 python agent/audit.py . --out reports/audit.jsonl`.
I used a hosted model because Ollama is not installed on this machine. See
REPORT.md, Attribution.

### Auditor output (verbatim, `reports/audit.jsonl`)

```
{"repo": "D:\\capstone\\bikeshare-open", "leakage": "none", "temporal_ok": true, "baseline_reported": true, "reproducible": true, "findings": [{"file": "README.md", "line": 25, "issue": "README says `make test` runs 14 tests, but 19 tests ran and passed.", "why_it_matters": "Minor documentation drift. It doesn't affect the methodology."}, {"file": "src/features.py", "line": 68, "issue": "Lag and rolling features are built on the full table before the split. All of them use shift(1) or shift(7) on a gap-free calendar index, so they only look backward.", "why_it_matters": "Not a fault. Each feature at time t uses only past values, and the first valid-split rows legitimately use late-2011 targets as lags."}], "confidence": "high"}
```

### My verdict

Neither finding changes a number, and I agree with both. The first is
real documentation drift: the README still said 14 tests after I added five.
I fixed it in the same commit as this file. The second is a correct
non-finding. Building lags before the split is safe because every one is
backward-looking on a gap-free calendar, and the first validation rows using
late-2011 counts as lags is information a forecaster really has. What the
auditor did *not* check matters more. Its four checks cover leakage,
temporal validity, baselines and reproducibility, and none of them looks at
whether the enforcement works. None of its checks would catch
the starter's PostToolUse hook silently exiting 0 on Windows
(SEEDED_FAULTS.md, Fault 0), or a raw CSV altered by a Bash `cp` that keeps
`casual + registered == cnt` (Fault 4). "0 flagged" here means "no
leakage in the code as written", not "nothing can go wrong".
