# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-23 Add `cnt_roll_28` (mean cnt over d-28..d-1; known at prediction time for d since every input predates d). Valid ridge R^2 0.6475 -> 0.6839 (MAE 832.9 -> 777.5); hgb 0.2185 -> 0.2415. LAG_WARMUP 7 -> 28 drops 42 more train rows, so I re-ran on identical rows: without the feature ridge is 0.6462, so the feature itself is worth +0.038. Kept. Decided on validation only; `make train` also printed test, which I did not use.
- 2026-11-23 Split `LAG_WARMUP` from the window lengths (`WEEK`, `MONTH_WINDOW` in config). The starter computed `cnt_lag_7` as `shift(LAG_WARMUP)`, so raising the warm-up for any longer feature would silently have turned it into a 28-day lag.
- 2026-11-23 Classify every raw column in `src/config.py` and test it (`test_every_raw_column_is_classified`). `feature_columns()` admits any numeric column not in FORBIDDEN, so a renamed `casual` would have become a feature; now it fails the contract test first.
