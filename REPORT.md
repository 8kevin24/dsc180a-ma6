# Bikeshare demand forecast: report

## Results

"Before" is the unmodified starter pipeline (`reports/metrics.json` at
commit `36e0f67`; 14 features, 348 train rows). "After" is the committed
`reports/metrics.json` that `make all` reproduces (15 features with
`cnt_roll_28`; `LAG_WARMUP` 28, so 306 train rows). Validation is
2012-01-01 to 2012-06-30 (182 days). Test is 2012-07-01 to 2012-12-31 (184
days).

| Model | Pipeline | Valid R² | Valid MAE | Test R² | Test MAE |
|---|---|---:|---:|---:|---:|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| baseline_mean | after | -0.6894 | 1877.3 | -1.7717 | 2659.6 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | after | 0.6839 | 777.5 | 0.6239 | 879.3 |
| hgb | after | 0.2415 | 1296.6 | -0.46 | 1952.4 |

The mean baseline moves between the two pipelines only because the longer
warm-up drops January 2011 from training. Its training mean is the only
thing it fits. Persistence is identical because it fits nothing and
validation and test rows are unchanged.

## Headline finding

> A ridge model on calendar, weather and lagged-demand features explains
> 62% of the variance in H2-2012 daily ridership (test R² 0.6239). That is
> only 0.114 better than predicting yesterday's count again (0.5099), and
> it is *worse* on MAE (879.3 vs 840.1 rides). Gradient-boosted trees on the
> same features score test R² -0.46, worse than a constant. A tree trained
> on 2011 cannot predict a level it never saw, and ridership grew ~65% into
> 2012. Every R² above sits beside a mean and a persistence baseline. The
> leaky model that adds `casual + registered` scores 1.000 and has learned
> addition.

My feature, `cnt_roll_28` (mean ridership over the 28 days before *d*), raised
validation ridge R² from 0.6475 to 0.6839. On identical rows it is worth
+0.038 (0.6462 without it), well above the 0.01 noise bar. **I kept it.**

## Exercise 4: target transformation

The tree fails because its leaves are bounded by 2011 counts. Rescaling
the target by a *lagged level* makes it roughly stationary. I added
`RelativeTarget` behind `python -m src.train --target-transform X`, and
the default run and `metrics.json` are untouched. I compared four transforms
on **validation only** (`--valid-only`):

| Transform (applied to ridge and hgb) | ridge valid R² | hgb valid R² | hgb valid MAE |
|---|---:|---:|---:|
| none (committed pipeline) | 0.6839 | 0.2415 | 1296.6 |
| `log` (log cnt) | 0.3740 | 0.1840 | 1325.5 |
| `log_ratio7` (log cnt / cnt_roll_7) | 0.4605 | 0.6989 | 759.4 |
| `log_ratio28` (log cnt / cnt_roll_28) | 0.4175 | **0.7132** | **694.4** |
| `diff28` (cnt - cnt_roll_28) | 0.6932 | 0.6950 | 716.2 |

`log` alone does nothing, because the tree still cannot reach unseen
levels. Anything relative to a lagged level lets it compete: under
`log_ratio28` hgb goes from 0.2415 to 0.7132 and beats untransformed ridge
(0.6839). After choosing, I touched the test set **once**: hgb +
`log_ratio28` scored test R² **0.6381**, MAE **779.8**, against ridge 0.6239 /
879.3 and persistence 0.5099 / 840.1.

**Is it defensible?** Mostly yes. The divisor `cnt_roll_28` is a feature
known at prediction time and covered by a leakage test, so nothing from
day *d* enters. The transform also follows from the diagnosis in the
headline, not from a search: it removes exactly the level shift we blamed
for the failure, and it lifts every tree variant tried, not just one. Two
honest caveats. (1) I picked the best of four transforms on 182 validation
days. `diff28` (0.6950) is within 0.02 of the winner, so the *choice among
relative transforms* is noise; *using one* is not. (2) The same transform
**hurts ridge** (0.6839 to 0.4175), so "the tree now beats ridge" means a
per-model choice of target. That is fair only if each model gets its
best-validated target. Under the shared `diff28` the two models tie
(0.6932 vs 0.6950). My conclusion: a relative target is a legitimate fix
for non-stationarity, and the claim worth making is that the tree is
competitive, not that it wins.

## Exercise 5: ridge vs persistence

Ridge is the better *forecaster*, but on this test half-year it is not
clearly worth deploying over "yesterday again" without one more fix. For:
it beats persistence on R² in both splits (valid 0.6839 vs 0.4507; test
0.6239 vs 0.5099) because it avoids the big misses. On test it is more than
2000 rides off on 10 days, against 17 for persistence. Its 90th-percentile
error is 1711 vs 1960, and its worst day is Sandy (4115 vs 4470). Against:
its typical day is worse. Test median absolute error is 807 vs 506, and
persistence is closer on 57% of test days. The cause is bias: ridge
under-predicts H2 2012 by 427 rides on average (mean signed error), because
it learned 2011's level. That is the same non-stationarity that sinks the
tree. So the decision depends on the cost of an error. A rebalancing
operation that pays for *large* misses (empty docks on a surge day) should
prefer ridge. One that pays per ride of error should keep persistence,
which is free, unfittable, and 39 rides better on MAE. I would deploy ridge
only with the level bias removed (a relative target, as in Exercise 4, or
periodic refitting on recent data). As it stands, it is not worth deploying
over yesterday's count.

## Attribution

**Model:** Claude Opus 5.5 (`claude-opus-5-5`, hosted by Anthropic), running
in the Claude Code VS Code extension on Windows. It was **not** the local
`bikeshare-coder` / `qwen3.5:9b` Ollama build: Ollama was not installed on
this machine. I did not set the context window, and I do not know its
exact size. The batch audit (`reports/audit.jsonl`) ran
`agent/audit.py` with `AUDIT_MODEL=claude-sonnet-5-5`, also hosted. The
teammate audit (`docs/AUDIT.md` Part A) ran their leakage-auditor prompt on
`claude-opus-5-5` via `agent/run_leakage_auditor.py`. I did not switch
models mid-task. Because the agent ran from outside this repo,
the project's PostToolUse hook was not registered in its session. Hook
output in `docs/SEEDED_FAULTS.md` comes from piping the exact PostToolUse
payload into the hook script, as that file says.

**What the agent generated:**
- `src/features.py`: `cnt_roll_28`, and `WEEK` replacing `LAG_WARMUP` in the
  existing window features
- `src/config.py`: `WEEK`, `MONTH_WINDOW`, the derived `LAG_WARMUP`,
  `RAW_SHA256`, and the raw-column classification sets
- `src/ingest.py`: `raw_sha256()`, `verify_raw()`
- `src/train.py`: `RelativeTarget`, `TARGET_TRANSFORMS`, `build_models()`,
  the `--target-transform` / `--valid-only` CLI
- `tests/test_leakage.py`: `test_roll_28_is_mean_of_28_prior_calendar_days`,
  `test_weather_encoder_rejects_unseen_labels`,
  `test_bad_weather_days_survive`, and the hardened
  `test_rolling_mean_excludes_today`
- `tests/test_contract.py`: `test_every_raw_column_is_classified`,
  `test_raw_file_is_unmodified`
- `.claude/hooks/check_leakage.sh` (Windows fix), `.claude/hooks/guard_raw.sh`
  (PreToolUse on Bash), `.claude/hooks/stop_tests.sh` (Stop), their
  registration in `.claude/settings.json`, `.claude/skills/seed-fault/SKILL.md`
- `agent/run_leakage_auditor.py`
- `.gitattributes`, the Python >= 3.12 note in `requirements.txt`,
  `CLAUDE.md` edits, all of `docs/SEEDED_FAULTS.md`, `docs/AUDIT.md`
  (including the verdict paragraphs, which I reviewed), this report, and the
  commit sequence

**What was my decision** (each traces to a line in `docs/DECISIONS.md`):
- Keep `cnt_roll_28` (+0.038 valid R² on identical rows).
- Decouple `LAG_WARMUP` from window lengths.
- Fail on unclassified raw columns.
- Fix the leakage hook that silently passed on Windows.
- Pin the raw file's sha256 as the fourth-fault mechanism, then add a
  PreToolUse Bash guard and a Stop hook on top of it.
- Choose `log_ratio28` for Exercise 4, and judge it defensible-with-caveats.
- Add the `/seed-fault` skill and the CLAUDE.md rules.
- Document Python >= 3.12 rather than change the pins.
- Exercise 3: agree with the teammate auditor's clean verdict, and flag two
  non-numeric issues.
- Exercise 5: don't deploy ridge over persistence until its level bias is fixed.
