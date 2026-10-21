# buying-analysis

An honest backtest comparison of simple, long-only investing and trading strategies for a **Roth IRA**,
using daily price data only (no news, no fundamentals, no LLMs). Every design choice aims to avoid
look-ahead, survivorship, overfitting and regime bias. All results are **hypothetical**.

Results: [RESULTS.md](RESULTS.md). Generated tables: `outputs/report_tables.md`.

## Setup

Requires [uv](https://docs.astral.sh/uv/). Python 3.11 and locked dependencies are installed automatically.

```bash
uv sync                      # install
uv run pytest                # tests
```

### Data (licensed, not in the repo)

`data/` is gitignored. CRSP data is licensed through WRDS and must never be published.

```bash
uv run scripts/copy_data.py                                   # 2010-2025 CRSP panel + point-in-time macro file
uv run --python 3.11 --group wrds scripts/fetch_crsp_history.py --wrds-username USER   # 1993-2009 (Duo push)
uv run scripts/fetch_ken_french.py                            # free 1926+ market + size/value portfolios
uv run --python 3.11 --group wrds scripts/fetch_country_etfs.py --wrds-username USER   # 24 country ETFs, 1996-2025
uv run scripts/fetch_shiller.py                               # free Shiller monthly S&P data (CAPE signal)
uv run scripts/validate_data.py                               # writes outputs/data_validation.md
```

`data/MANIFEST.md` records the source, date, row count, date range and SHA-256 of every file.

## Run

```bash
uv run scripts/run_all.py            # validation, then every development experiment (through 2022)
uv run scripts/run_all.py --quick    # fewer random/bootstrap draws, to check the pipeline
uv run scripts/run_all.py --lockbox  # the one-time 2023-2025 evaluation (see "Lockbox")
```

Follow-up studies, each standalone (outputs in `outputs/<study>/`). These came after the lockbox was spent,
so they use pre-declared settings, report full grids, and treat 2023-2025 as descriptive only.

| Script | Question |
|---|---|
| `scripts/day_of_week.py` | Does the weekday / open vs close of a weekly DCA purchase matter? |
| `scripts/mean_reversion.py` | Swing-trade assets that mean-revert (select 1993-2007, test 2008-2022) |
| `scripts/sector_reversal.py` | Always-invested rotation into last month's worst sectors |
| `scripts/factor_tilts.py` | Small-cap / value tilts, 1927-2022 (Ken French portfolios) |
| `scripts/country_momentum.py` | Country momentum, US vs international switching, rolling US lead |
| `scripts/sma_rule.py` | Daily X-day moving-average rule, out to T-bills |
| `scripts/cape_timing.py` | Sell when CAPE is expensive (real-time percentile thresholds) |
| `scripts/seasonality.py` | Returns by calendar day / month, Sell in May |
| `scripts/valuation_scatter.py` | Trailing P/E and CAPE at purchase vs next-10-year return |
| `scripts/single_stock_trend.py` | 200-day / 10-month trend rules on each Dow stock |
| `scripts/value_profitability.py` | Cheap + profitable stocks (Ken French 5x5 BM x OP portfolios, 1964-2022) |
| `scripts/stock_momentum.py` | 12-1 month momentum winners vs the market (Ken French, 1927-2022) |

## Assumptions

**Account (Roth IRA).** No taxes. Long-only: no margin, shorting or leverage. Uninvested cash sits in a
money-market fund earning the 3-month T-bill rate (DGS3MO, point-in-time) minus 0.10%/yr, floored at 0.

**Contributions.** Hypothetical: $5,000 on the first trading day of each year (configurable in
`configs/default.yaml`). Real Roth limits were $2,000-$7,000/yr over 1993-2025. Two framings: (a) the
deposit schedule; (b) everyone starts with the same total pile on day 1, and DCA draws it down over 12 months.

**SPY stands in for VOO.** Both track the S&P 500. VOO's expense ratio is ~0.06%/yr lower (0.03% vs
0.09%), so a VOO holder would earn slightly more; relative comparisons between strategies are unaffected.
SPY is used because its history starts in 1993 (VOO: 2010).

**Execution.** Signals use data through day t's close; trades fill at day t+1's open. Prices are total-return
indexes from CRSP `ret` (dividends reinvested, splits handled); the open is placed on the same index via the
open/close ratio. Fractional shares by default.

**Costs** (applied by the engine only, never by strategies): $0 commission; spread 2 bps/side for ETFs and
5 bps/side for stocks (also run at 0x and 2x); SEC Section 31 fee and FINRA TAF on sells. Fund expense
ratios are already inside ETF returns and are not deducted again.

**Settlement.** IRAs are cash accounts settling T+1: sale proceeds can be used the next session, never the
same day. Deposits settle on arrival. Delisted positions convert to cash at their last value.

**Bias controls.**
- *Lockbox:* all tuning uses data through 2022. 2023-2025 is evaluated once, at the end, in a separate table.
- *Trials:* every configuration tried is logged in `outputs/trials.csv`; full grids are reported.
- *Statistics:* paired block-bootstrap CIs vs SPY (21-day blocks, deposits on their real days), Deflated
  Sharpe Ratio per strategy family, Holm-adjusted p-values across strategies.
- *Null baselines:* exposure-matched SPY (N1) and 100 random-timing runs with the same time in market and
  number of in-market spells (N2); random sector picks for sector rotation.
- *Regimes and start dates:* results by calendar year and regime, and fresh portfolios started every month
  over 10- and 20-year windows.
- *Survivorship:* the Dow stock list is today's membership, chosen with hindsight. ETF/SPY results are the
  main findings; single-stock results are illustrative only.

**Known data issues (accepted).** SPY 2000-04-04 close looks like a bad print (also possibly 2000-04-14,
2001-04-30); blocking signals on those days changes results by < 0.02 pp/yr. Spinoff distributions appear
missing from CRSP returns for HWM 2020-04-01 and DD 2019-06-03 (single stocks only). See
`outputs/data_validation.md`.

## Data sources and licensing

| Source | Use | License |
|---|---|---|
| CRSP daily stock file (`crsp.dsf_v2`) via WRDS | all prices, 1993-2025 | licensed; not redistributable |
| FRED / ALFRED DGS3MO | cash yield (point-in-time) | public |
| CRSP via WRDS: 24 US-listed country/region ETFs | country study, 1996-2025 | licensed; not redistributable |
| Ken French Data Library | 1926+ US market, size x value portfolios | free for research |
| Robert Shiller, `ie_data.xls` | monthly S&P earnings / CPI for CAPE (1871-2023) | free for research |
| yfinance, FRED | validation only, never mixed into results | public |

## Layout

```
src/buying_analysis/
  data.py        local data access (CRSP, risk-free, Ken French), manifest
  validate.py    data validation checks
  backtest.py    engine: MarketData, Context, Strategy, Engine
  costs.py       spreads, sell fees, money-market yield
  metrics.py     XIRR, CAGR, Sharpe, drawdowns, turnover
  stats.py       block bootstrap, Deflated Sharpe, Holm
  experiments.py null baselines, per-ticker runs, rolling windows, trials log, lockbox guard
  report.py      tables;  plots.py  charts
  strategies/    benchmarks, deployment (lump sum, DCA), dip, timing, learned, meanrev, nulls
scripts/         data: copy_data, fetch_crsp_history, fetch_country_etfs, fetch_ken_french, fetch_shiller,
                 validate_data; main study: run_all; follow-ups: see the table under "Run"
configs/default.yaml
tests/
```

## Adding a strategy

Subclass `Strategy` (or `Allocator` for rule-based allocations) and implement `decide(ctx)`, returning target
weights `{permno: weight}` (cash is the remainder; weights must sum to <= 1) or `None` to hold. `ctx` only
exposes history through today's close (`ctx.close(permno)`, `ctx.open(permno)`, `ctx.rf()`), plus the
strategy's own portfolio (`ctx.cash`, `ctx.weight(permno)`) and the deposit schedule.

```python
from buying_analysis.strategies.timing import Allocator, sma, SPY

class AboveSMA(Allocator):
    name, assets = "above_sma100", (SPY,)

    def allocation(self, ctx):
        x = ctx.close(SPY)
        return None if len(x) < 100 else ({SPY: 1.0} if x[-1] > sma(x, 100) else {})
```

Then add it to the relevant list in `scripts/run_all.py`, and add it to the truncation test in
`tests/test_strategies.py`, which checks that removing future data changes nothing before the cut.
