Build a Python project that backtests and compares simple investing/trading strategies on daily price data, to find which strategies hold up best for a long-only Roth IRA. No text, news or LLMs: price and market data only. The goal is an honest comparison, not the most flattering backtest: every design choice below exists to prevent look-ahead, survivorship, overfitting and regime bias.

## Account assumptions (Roth IRA)
- No taxes. Long-only, no margin, no shorting. Uninvested cash sits in a money-market fund.
- Contributions are a **hypothetical** fixed schedule (default $1,000 on the first trading day of each month, configurable). Label results as hypothetical; real Roth limits are lower ($5k–$7k/yr over this period) and a large day-1 lump sum is only possible via rollover.
- Costs (all configurable, all applied by the engine, never by individual strategies):
  - Commission: $0 default.
  - Spread/slippage per side: 2 bps ETFs, 5 bps single stocks by default; also report 0 and 2× defaults.
  - Regulatory fees on sells (SEC Section 31 + FINRA TAF): small configurable rate.
  - Cash yield: T-bill rate minus 0.10%/yr (money-market expense).
  - Fund expense ratios are already in ETF returns; do not deduct them again.
- Settlement: IRAs are cash accounts settling T+1. The engine must only buy with settled cash (or flag would-be good-faith violations). Fractional shares allowed (configurable to whole shares).

## Data
All data lives locally under `data/` (gitignored: CRSP is licensed, never publish it). The code never reads from other repos at runtime.

1. **Primary (CRSP):** copy `/home/ryanf/classes/CS592/regime-router/data/processed/prices_daily.parquet` and `macro_pit.parquet` into `data/raw/` (read-only source; do not modify or import anything from `regime-router/`). Write `data/MANIFEST.md` with source path, copy date, row counts, date range and SHA-256 of each file.
   - Prices: CRSP daily, 2010-01-04 → 2025-12-31, ~69 tickers (Dow stocks, SPY, DIA, sector ETFs, TLT/IEF/LQD/HYG/GLD/USO/UUP). Key on `permno` (tickers change, e.g. UTX→RTX). Build adjusted series from cumulative `ret` (total return incl. dividends), not raw `close`. `open` is unadjusted: use `cumfacpr` (or `ret_oo_next`, which has some NaNs) for open-based returns.
   - Risk-free: `macro_pit.parquet`, `series_id == "DGS3MO"`, using `available_at` so only values known on each date are used.
2. **Longer history (to cover 2000–02 and 2008):** WRDS access is confirmed (SPY permno 84398 available from 1993-01-29). Write `scripts/fetch_crsp_history.py` that pulls `crsp.dsf_v2` for the same permnos from 1993-01-29 through 2009-12-31 (same columns as the processed file) plus DGS3MO from FRED for that span, saving to `data/raw/` and updating the manifest. The user runs it manually: login needs `wrds.Connection(wrds_username=...)` and a Duo push, and must use Python 3.11 (`uv run --python 3.11`), because `wrds` pins pandas 2.2.x, which has no Python 3.14 wheel. Verify the stitched 2009→2010 boundary matches the existing file (no gaps, no duplicate sessions, identical `ret` on any overlap). Per-asset start dates differ (SPY 1993, sector ETFs Dec 1998, IEF/TLT 2002, GLD 2004); strategies needing an asset only run from when it exists. Optionally add the free **Ken French Data Library** (daily market + RF since 1926) as a long-history robustness check for market-level strategies.
3. **Independent validation (free APIs, validation only, never mixed into the primary series):** yfinance or Stooq for SPY + a handful of tickers; FRED API for DGS3MO.
4. 2026 data is out of scope.

### Data validation (`scripts/validate_data.py`, writes `outputs/data_validation.md`, run before any backtest)
- Sessions match the NYSE calendar: no gaps, duplicates or weekend dates per permno.
- Each permno has a continuous history; list partial histories (e.g. DOW starts 2019) explicitly.
- Flag |daily ret| > 25% and check each against a known corporate action (spinoffs: UTX/RTX, DWDP→DOW/DD/CTVA, KFT→MDLZ).
- Cross-source: daily-return correlation > 0.999 and annual total returns within ~0.1%/yr vs the API source; SPY annual total returns vs published figures.
- DGS3MO matches FRED; missing values forward-filled only from past values.
- Fail loudly (non-zero exit) on any hard check failure.

## Strategies
Every strategy plugs into one engine and outputs target weights (across assets + cash); the engine handles cash, contributions, costs, settlement and accounting.

**Benchmarks**
- B1. SPY buy-and-hold with the *same cash-flow schedule* as the strategy being compared (the primary benchmark).
- B2. 60/40 SPY/IEF, rebalanced monthly or quarterly.
- B3. Equal-weight portfolio of the universe, rebalanced monthly.

**Deployment of new cash (per ticker and SPY)**
1. Lump sum: invest everything on day 1 and hold.
2. Annual / monthly / weekly DCA: equal tranches on the first trading day of each period.
3. Buy the dip: contribute monthly, hold cash (earning the cash yield) until price ≥ X% below its trailing 52-week high, then deploy all of it; fallback: deploy after N months of waiting. Report a small X × N grid.

**Timing / allocation (rule-based)**
4. Trend: 10-month (≈200-day) SMA timing on SPY, plus the 50/200-day crossover.
5. Dual momentum: hold SPY if its 12-month return beats both T-bills and IEF, otherwise the better of IEF / cash.
6. Sector rotation: monthly, hold the top 3 of the 11 sector ETFs by 12-1 month return (only ETFs that existed on that date).
7. Volatility targeting: scale SPY exposure to a target annualized vol (e.g. 15%), capped at 100% (no leverage).
8. Short-term mean reversion: RSI(2) on SPY (buy when RSI(2) < 10, exit when above 70 or close > 5-day SMA).

**Learned**
9. Adaptive swing: long/flat signal. Features from the past only (multi-lookback returns, MA ratios, RSI, realized vol, distance from 52-week high/low). Target: sign of next-k-day return. Logistic regression first; gradient boosting optional. Walk-forward with an expanding window, retrain yearly, purge a k-day gap between train and test (overlapping labels), fit scalers on train only. Long when predicted probability > threshold, else cash.

**Null baselines (required, used to judge every timing strategy)**
- N1. Exposure-matched benchmark: SPY scaled to the strategy's average time in market, rest in cash.
- N2. Random timing: many seeded random entry/exit series with the same time in market and trade count; report where the strategy ranks in that distribution.

## Avoiding overfitting and bias
- **Lockbox:** tune all parameters (dip X/N, thresholds, lookbacks, model hyperparameters) only on data through 2022. 2023–2025 is held out and evaluated exactly once, at the end, in a separate clearly labelled table.
- Log every configuration tried (`outputs/trials.csv`); report the full grid, not only the best cell. Report a Deflated Sharpe Ratio (or a bootstrap p-value on Sharpe difference vs B1) that accounts for the number of trials.
- Block-bootstrap confidence intervals on CAGR / Sharpe differences vs SPY.
- Sub-period results: by calendar year and by regime (e.g. 1993–99 bull, 2000–02 dot-com bust, 2003–07, 2008–09 GFC, 2010–19, 2020–22, 2023–25). Tune/walk-forward on 1993–2022; the 2023–2025 lockbox is unchanged.
- Survivorship: the Dow stock list is chosen with hindsight (e.g. NVDA, AMZN, CRM are in the list because they are Dow members today). Treat ETF/SPY results as the main findings and single-stock results as illustrative; if feasible, add a variant using point-in-time Dow membership.
- No look-ahead: signals use data through day t's close and trade at day t+1's open (document this). Test it (below).

## Fairness and metrics
- Same total capital for every strategy, same contribution schedule; uninvested cash earns the cash yield.
- Report both framings: (a) contribution schedule, (b) everyone starts with the same pile and DCA variants draw it down from cash.
- Per strategy × asset: final value, XIRR (money-weighted), CAGR (time-weighted), annualized vol, Sharpe (excess of T-bill), Sortino, max drawdown, longest drawdown duration, Calmar, time in market, # trades, turnover, total costs paid.
- Summary across tickers: median, and % of tickers where each strategy beats lump sum and beats B1.
- Plots: equity curves for a few assets, drawdown chart, distribution of strategy-minus-lump-sum across tickers, strategy vs random-timing distribution, rolling 3-year excess return vs SPY.
- Outputs to `outputs/` (CSV + PNG) and a short `RESULTS.md` with tables and takeaways, stating plainly which strategies did *not* beat SPY after costs.

## Engineering
- Python 3.11 with `uv` (`pyproject.toml`, locked deps): pandas, numpy, pyarrow, scikit-learn, matplotlib, pyyaml, pytest, yfinance (validation only); ruff for lint.
- Layout: `src/<pkg>/{data.py, validate.py, strategies/, backtest.py, costs.py, metrics.py, stats.py, plots.py}`, `scripts/{validate_data.py, run_all.py, fetch_crsp_history.py}`, `configs/default.yaml`, `tests/`, `data/` (gitignored).
- Tests:
  - Accounting identities: cash + holdings = equity every day; contributions sum correctly; costs reduce equity by exactly the charged amount.
  - No look-ahead: perturbing prices after date t does not change any signal or position on or before t.
  - XIRR on a known example; DCA on a constant-price series; zero-cost lump sum on SPY reproduces cumulative `ret`.
  - Settlement: a sell-then-buy on the same day cannot use unsettled proceeds.
- Deterministic (fixed seeds), runnable end to end with one command (`make run` or `uv run scripts/run_all.py`), validation runs first.
- README: setup, how to run, all assumptions above, data sources and licensing, and how to add a new strategy.

## How to work
1. Copy data, write the manifest, build and run validation; report findings before backtesting.
2. Propose a short plan (layout, engine design, conventions) before writing much code.
3. Build the engine + benchmarks + DCA strategies; verify against hand calculations.
4. Add buy-the-dip and the rule-based timing strategies with null baselines.
5. Add the learned swing model.
6. Run the lockbox evaluation last.
Keep it simple; this is a class-sized comparison study, not a production system.
