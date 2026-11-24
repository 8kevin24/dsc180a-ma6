# Audit (Exercise 3)

## Part A: `/leakage-auditor` on a teammate's repo

**Teammate repo:** https://github.com/mihirnvad/DSC180A-Methodology-6
(cloned at `cbdc552`; diff reviewed: `git diff b183a4e HEAD -- src tests`,
where `b183a4e` is their unmodified starter. I confirmed `src/features.py`
there is byte-identical to the starter zip.)

**How it was run.** Their `.claude/agents/leakage-auditor.md` (identical to
the starter's) was run headless through the Agent SDK. The system prompt is
the subagent's body, the tools are exactly its `Read, Grep, Glob, Bash`, and
Edit/Write are disallowed. `setting_sources=[]` keeps their `settings.json`
(hooks, Ollama endpoint) from loading on my machine. The prompt only named
the diff to review and said `python` with the pinned requirements was on
PATH. Model and turns: `model=claude-opus-5-5 turns=6 is_error=False`. The runner script is not in this repo; it
lived in my scratch directory.

### Auditor output (verbatim)

```
All five checks pass, with no finding that changes a number or invalidates a conclusion: I re-ran the pipeline and tests (16 passed, `reports/metrics.json` reproduced), altering targets from date *t* onward at every fifth date changed no feature dated up to *t*, all 714 rows' lag and rolling values match an independent calendar-day recomputation, the split is by date and the scaler was fitted on the 348 training rows only, the 14 lost rows are exactly the 7 warm-up days plus the 7 after the 2011-03-10 gap (within the asserted bound, all 20 BAD-weather days kept), and both baselines are reported beside the model scores in `train` and `target_transform` (`compare_persistence` prints only persistence, but the mean baseline on the same rows is in `metrics.json`, so its conclusion stands).
```

### My verdict

The auditor reported nothing that changes a number, and I agree. I checked
three of its claims myself. After its run, `git status` in their clone was
empty: its pipeline re-run left `reports/metrics.json` byte-identical. Their
REPORT.md table matches metrics.json to the printed digit (e.g. ridge test
0.6356 / 840.3, hgb valid 0.0977). Their feature `cnt_roll_7_std` shifts
before it rolls and needs no extra warm-up (714 rows, same as the starter).
Two things fall outside its five checks and change no number, but would
cost them points:

1. `src/target_transform.py` chooses the transform on validation and then,
   in the same function, prints **test** scores (lines 67-75). So every run
   while iterating shows test numbers. "Test touched once" holds by
   discipline, not by construction. Minimal fix: print test only behind a
   `--final` flag.
2. Their Results table has 8 rows, but they are 4 models × {valid, test}.
   There are no *before/after-feature* rows, which rubric item 4 asks for. The
   before numbers are in their DECISIONS.md line for `cnt_roll_7_std`, but
   not in the table.

I'd also note that the auditor's checks cover none of the enforcement
layer. Their repo independently hit the same Windows `python3` hook bug I
found (their commit `1ed55c8`), and no line of a leakage review would have
caught it.

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
