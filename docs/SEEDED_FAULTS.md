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
