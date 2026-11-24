# Seeded faults (Exercise 2)

Every block below is pasted from a real run on Windows 10, Python 3.13.13,
the pinned `requirements.txt`. The hook output is the stderr of
`.claude/hooks/check_leakage.sh` fed the exact PostToolUse payload Claude
Code sends after an `Edit` of `src/features.py`:

    {"hook_event_name": "PostToolUse", "tool_name": "Edit",
     "tool_input": {"file_path": "D:/capstone/bikeshare-open/src/features.py"}}

piped by hand (`bash .claude/hooks/check_leakage.sh < payload.json`),
because the agent that made these edits was not running from inside this
repo, so the project's hook was not registered in its session. "Agent turns
to fix" counts the agent's tool calls from seeing red to seeing green.

## Fault 0 (found, not seeded): the hook was a no-op on Windows

Before seeding anything I fed the starter hook a payload on a green tree:

    $ bash .claude/hooks/check_leakage.sh < payload.json
    Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
    STARTER hook exit=0

`python3` is the Microsoft Store stub on this machine, so the payload parse
printed nothing, `$path` was empty, the `case` fell through to `exit 0`,
and **the hook would have passed every fault below**. Fixed in commit
`fab53e1` (use the pytest interpreter, normalise `\`, exit 2 on a parse
failure). All hook output below is from the fixed hook.

## Feature test, before the feature (red for the right reason)

`test_roll_28_is_mean_of_28_prior_calendar_days`, committed in `c6a136d`
before `cnt_roll_28` existed:

```
$ python -m pytest tests/test_leakage.py -q --tb=line
E   AttributeError: 'DataFrame' object has no attribute 'cnt_roll_28'. Did you mean: 'cnt_roll_7'?
D:\capstone\bikeshare-open\.venv\Lib\site-packages\pandas\core\generic.py:6194: AttributeError: 'DataFrame' object has no attribute 'cnt_roll_28'. Did you mean: 'cnt_roll_7'?
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_roll_28_is_mean_of_28_prior_calendar_days
1 failed, 7 passed in 0.91s
```

It failed because the column did not exist, not because of an import
error or a typo in the test. After `e70e95c` it passes (15 passed).

## Fault 1: a forbidden column added to `feature_columns`

Change:

```diff
@@ -85,7 +85,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
 def feature_columns(df: pd.DataFrame) -> list[str]:
     """Numeric columns that are safe to feed the model."""
     numeric = df.select_dtypes(include="number").columns
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["registered"]
 
 
 if __name__ == "__main__":
```

`make test`:

```
....F.F.........                                                         [100%]
================================== FAILURES ===================================
_____________________ test_every_raw_column_is_classified _____________________
tests\test_contract.py:76: in test_every_raw_column_is_classified
    assert not leaked_through, f"undeclared raw columns used as features: {sorted(leaked_through)}"
E   AssertionError: undeclared raw columns used as features: ['registered']
E   assert not {'registered'}
_________________________ test_no_forbidden_features __________________________
tests\test_leakage.py:31: in test_no_forbidden_features
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E   AssertionError: forbidden columns in feature set: {'registered'}
E   assert not ({'atemp', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})
=========================== short test summary info ===========================
FAILED tests/test_contract.py::test_every_raw_column_is_classified - Assertio...
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
2 failed, 14 passed in 3.24s
```

Hook stderr:

```
Leakage tests failed after editing D:/capstone/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7  cnt_roll_28
0   2011-01-31     31.0  WINTER  ...     141....142857  4071.321429
671 2012-12-31    731.0  WINTER  ...      920.0  1531.428571  3969.428571

[672 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'registered'}
E       assert not ({'atemp', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_28', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 1.18s
exit=2
```

Agent turns to fix: **1** (one `Edit` reverting the line; `make test` then
printed `16 passed`). Both the starter's gate test and my new contract test
went red.

## Fault 2: `.shift(1)` deleted from `cnt_roll_7`

Change:

```diff
@@ -73,7 +73,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
     # If you add a longer window, raise LAG_WARMUP in src/config.py.
     out["cnt_lag_1"] = out[TARGET].shift(1)
     out["cnt_lag_7"] = out[TARGET].shift(WEEK)
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(WEEK).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(WEEK).mean()
     # 28-day level: the mean of the 28 calendar days before today. Known at
     # prediction time for d (uses d-28 .. d-1 only). Tracks the slow 2011->
     # 2012 growth that a 7-day window confuses with weekly noise.
```

`make test`:

```
.........F......                                                         [100%]
================================== FAILURES ===================================
______________________ test_rolling_mean_excludes_today _______________________
tests\test_leakage.py:57: in test_rolling_mean_excludes_today
    assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E   assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E     
E     comparison failed
E     Obtained: 4605.285714285715
E     Expected: 4724.428571428572 ± 0.00472443
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 15 passed in 3.25s
```

Hook stderr (last 12 lines; the full block also dumps the fixture frame):

```
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4605.285714285715) == 4724.428571428572 ± 0.00472443
E             
E             comparison failed
E             Obtained: 4605.285714285715
E             Expected: 4724.428571428572 ± 0.00472443

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 1.07s
exit=2
```

Agent turns to fix: **1** (one `Edit` restoring `.shift(1)`).

It was caught, but by luck. The starter's test sampled `feats.dteday.iloc[200]`
and wrapped the assertion in `if all(d in by_date.index for d in window):`,
with `by_date` taken from the *feature* frame, which has rows missing after
the 2011-03-10 gap. If the sampled date's window touches a gap, the test
asserts nothing and passes. My change to `cnt_roll_28` moved `iloc[200]`
from 2011-08-06 to 2011-09-17. I hardened the test in the same commit: fixed
date 2011-09-15, window from the raw file, unconditional assert. I re-seeded
the fault against the hardened test, and it is still red:

```
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 15 passed in 2.93s
```

## Fault 3: the `raise` removed from the weather encoder

Change:

```diff
@@ -26,8 +26,6 @@ def encode_weather(series: pd.Series) -> pd.Series:
     """
     known = series.dropna()
     unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
 
 
```

`make test` with the starter's tests plus mine (**no test went red**):

```
................                                                         [100%]
16 passed in 2.93s
```

Hook stderr: empty.

```
exit=0
```

Nothing failed because the clean data only contains GOOD/MISTY/BAD, so no
run ever reaches the `raise`. The fault is real but dormant: the next mirror
that spells a label differently loses those days to `dropna()`, and
`test_only_expected_rows_are_dropped` would catch that only if the loss
exceeded its bound. I added two tests to `tests/test_leakage.py` (so the
hook runs them too): `test_weather_encoder_rejects_unseen_labels` feeds the
encoder an unseen label, and `test_bad_weather_days_survive` checks that all
20 BAD days reach the model with severity 2. With the fault still in:

```
.............F....                                                       [100%]
================================== FAILURES ===================================
_________________ test_weather_encoder_rejects_unseen_labels __________________
tests\test_leakage.py:95: in test_weather_encoder_rejects_unseen_labels
    with pytest.raises(ValueError, match="unmapped weather labels"):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE ValueError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unseen_labels - Fa...
1 failed, 17 passed in 3.36s
```

Hook stderr:

```
        spells it "Bad" loses those days to dropna() with no error."""
        from src.features import encode_weather
    
>       with pytest.raises(ValueError, match="unmapped weather labels"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests\test_leakage.py:95: Failed
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unseen_labels - Fa...
1 failed, 9 passed in 1.09s
exit=2
```

Agent turns to fix: **2**. One `Edit` writing the test that exposes the
fault, and one `Edit` restoring the `raise`. After that, 18 passed.

## Fault 4: a `cp` into `data/raw/` from Bash (the hook cannot see it)

The seed was a plausible "cleaned" raw file. I took the Hurricane Sandy day
(2012-10-29: casual 2, registered 20, cnt 22) and rewrote it as a typical
late-October day (600 / 4400 / 5000). `casual + registered == cnt` still
holds, so the identity test has nothing to object to. Then I copied the
result over the raw file from Bash:

```
$ cp "$SCRATCH/bike_daily_fixed.csv" data/raw/bike_daily.csv
$ sha256sum data/raw/bike_daily.csv
edb418fb3491b25e6942e26017a2bc03dd60dbd5bdd25d3acad340b3d2cebc2e *data/raw/bike_daily.csv
$ git status --short data/raw
 M data/raw/bike_daily.csv
$ python -m pytest tests -q
18 passed in 2.81s
$ python -m src.ingest && python -m src.features && python -m src.train  (valid/test ridge only)
OK ingest: 728 rows, 2011-01-03 -> 2012-12-31
OK features: 672 rows, 15 features -> features.parquet
ridge {'valid': {'r2': 0.6839, 'mae': 777.5}, 'test': {'r2': 0.6176, 'mae': 860.5}}
```

What happened: **nothing stopped it, and nothing went red.**

- The PostToolUse hook matches `Edit|Write` only, so a Bash `cp` never
  triggers it. Even if it did, its `case` only reacts to `src/*.py`.
- The `Write(./data/raw/**)` / `Edit(./data/raw/**)` deny rules apply to
  those tools, not to a shell command that writes the same path.
- All 18 tests passed on the altered data.
- Validation was unchanged (Sandy is in test), so the test numbers shifted
  silently: ridge test R^2 0.6239 -> 0.6176 and MAE 879.3 -> 860.5;
  persistence test R^2 0.5099 -> 0.4869. A reported test result now rests
  on data nobody can reproduce.

What catches it: a **hash check**, which I implemented.
`src/config.py` pins `RAW_SHA256`. `src/ingest.py::verify_raw()` runs in
`make data` and in the new `tests/test_contract.py::test_raw_file_is_unmodified`.
`.gitattributes` marks the CSV `-text`, so a Windows checkout with
`core.autocrlf=true` cannot change its bytes and trip the check falsely.
Re-seeding the same `cp` with the check in place:

```
$ make data
ValueError: bike_daily.csv sha256 edb418fb3491b25e... != expected a6bed1577f6e4de5...; the raw file was modified. Restore it with: git checkout -- data/raw/
exit=1
$ make test
D:\capstone\bikeshare-open\src\ingest.py:33: ValueError: bike_daily.csv sha256 edb418fb3491b25e... != expected a6bed1577f6e4de5...; the raw file was modified. Restore it with: git checkout -- data/raw/
=========================== short test summary info ===========================
FAILED tests/test_contract.py::test_raw_file_is_unmodified - ValueError: bike...
1 failed, 18 passed in 2.57s
```

Restored with `git checkout -- data/raw/`. The sha256 is back to `a6bed1577f6e4de5...`.

### Second mechanism: block the write before it happens

I added a **PreToolUse hook on `Bash`**, `.claude/hooks/guard_raw.sh`,
registered in `.claude/settings.json`. It exits 2 when a command writes into
`data/raw/`: redirection, `cp`/`install` *to* it, `mv`/`rm`/`tee`/`touch`,
`sed -i`, or pandas/`open()` writes. Copying *out of* `data/raw/` and
`git checkout -- data/raw/` are allowed. Each case was fed to the hook as
the PreToolUse payload Claude Code sends:

```
ok   exit 2 | want 2 | cp /tmp/bike_daily_fixed.csv data/raw/bike_daily.csv
ok   exit 2 | want 2 | echo x >> data/raw/bike_daily.csv
ok   exit 2 | want 2 | sed -i 's/22/5000/' data/raw/bike_daily.csv
ok   exit 2 | want 2 | mv data/raw/bike_daily.csv /tmp/x.csv
ok   exit 2 | want 2 | python -c "import pandas as pd; pd.read_csv('data/raw/bike_daily.csv').to_csv('data/raw/bike_daily.csv')"
ok   exit 2 | want 2 | cp C:\tmp\x.csv data\raw\bike_daily.csv
ok   exit 2 | want 2 | cp x.csv data/raw/bike_daily.csv && make test
ok   exit 0 | want 0 | git checkout -- data/raw/
ok   exit 0 | want 0 | sha256sum data/raw/bike_daily.csv
ok   exit 0 | want 0 | head -3 data/raw/bike_daily.csv
ok   exit 0 | want 0 | python -m pytest tests -q
ok   exit 0 | want 0 | cp data/raw/bike_daily.csv /tmp/copy.csv
failures: 0

$ hook stderr for the fault-4 command:
Blocked: this command writes to data/raw/, which is immutable (sha256 pinned in src/config.py).
  command: cp /tmp/bike_daily_fixed.csv data/raw/bike_daily.csv
Write derived data to data/processed/ instead. To restore the raw file: git checkout -- data/raw/
exit=2
```

It filters the command string and is not a sandbox: an obfuscated command
(`eval`, a variable holding the path) gets through. That is why the
sha256 check stays as the backstop.

### Third mechanism: no "done" on a red suite

`.claude/hooks/stop_tests.sh`, registered as a **Stop hook**, runs the
whole suite (including the hash test) when the agent tries to finish, and
exits 2 if anything is red. On the second attempt it honours
`stop_hook_active` so it cannot loop. Real run, with fault 4 re-seeded:

```
$ # green tree
exit=0
$ cp bike_daily_fixed.csv data/raw/bike_daily.csv   # fault 4 again, then the agent tries to stop
Not done: the test suite is red. Fix it before finishing.
FAILED tests/test_contract.py::test_raw_file_is_unmodified - ValueError: bike...
1 failed, 18 passed in 3.37s
exit=2
$ # second stop attempt (stop_hook_active=true)
exit=0
$ git checkout -- data/raw/ && sha256sum data/raw/bike_daily.csv
a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc *data/raw/bike_daily.csv
```

Not implemented:

- A **filesystem permission**: mark `data/raw/bike_daily.csv` read-only
  (`chmod a-w`, or `attrib +R` on Windows). This catches every tool, but
  the agent can undo it with another shell command.
