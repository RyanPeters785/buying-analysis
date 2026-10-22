# Long-only Gu-Kelly-Xiu replication (2003-2025, walk-forward)

Top decile of predicted next-month excess return, monthly rebalance; $5,000 each December month-end. After-cost runs charge per side by NYSE size bucket {1: 75.0, 2: 30.0, 3: 15.0, 4: 10.0} bps (SPY 2 bps). *2016-2025 was viewed in the earlier ML study.

## Replication checks (out-of-sample, 2003-2025)

| model   | universe     |       r2_oos (fraction) |     mean_ic |   ic_t |
|:--------|:-------------|-------------:|------------:|-------:|
| enet    | all          | -0.0207854   |  0.08841    |  10.17 |
| enet    | no microcaps | -0.0456991   |  0.0269284  |   2.83 |
| gbrt    | all          | -0.000267668 |  0.0900151  |  11.08 |
| gbrt    | no microcaps |  0.00173479  |  0.0297521  |   3.84 |
| nn3     | all          | -0.183139    |  0.00365661 |   0.9  |
| nn3     | no microcaps | -0.400679    | -0.00373158 |  -0.73 |
| ols3    | all          | -0.00224749  |  0.076278   |  12.06 |
| ols3    | no microcaps | -0.000393376 |  0.0149963  |   2.19 |

## Portfolios

| strategy                                | final_value   | vs_spy   | xirr   | cagr   |   sharpe | volatility   | max_drawdown   | pct_years_beat_spy   | pct_36m_sharpe_beats_spy   | pct_36m_return_beats_spy   |   excess_t |   dsr_vs_spy | turnover_per_yr   |   avg_holdings |
|:----------------------------------------|:--------------|:---------|:-------|:-------|---------:|:-------------|:---------------|:---------------------|:---------------------------|:---------------------------|-----------:|-------------:|:------------------|---------------:|
| SPY (before costs)                      | $609k         | 0.0%     | 12.3%  | 11.5%  |     0.72 | 14.4%        | -50.8%         | 100.0%               | 100.0%                     | 100.0%                     |       2.58 |              | 13.3%             |              1 |
| SPY                                     | $608k         | 0.0%     | 12.3%  | 11.5%  |     0.72 | 14.4%        | -50.8%         | 0.0%                 | 0.0%                       | 0.0%                       |            |              | 13.3%             |              1 |
| market cap-weight (all stocks)          | $611k         | 0.5%     | 12.3%  | 11.8%  |     0.72 | 14.9%        | -50.3%         | 60.9%                | 39.2%                      | 66.2%                      |       1.01 |              | 23.8%             |          4,074 |
| equal-weight all stocks                 | $294k         | -51.7%   | 7.2%   | 9.0%   |     0.45 | 20.4%        | -60.3%         | 34.8%                | 16.7%                      | 28.7%                      |      -0.54 |              | 140.4%            |          4,074 |
| equal-weight no microcaps               | $407k         | -33.1%   | 9.5%   | 10.6%  |     0.54 | 19.0%        | -54.3%         | 39.1%                | 20.8%                      | 41.2%                      |      -0.05 |              | 140.2%            |          1,901 |
| enet | all stocks | EW | before costs   | $497k         | -18.2%   | 10.9%  | 11.6%  |     0.73 | 14.3%        | -46.3%         | 52.2%                | 56.2%                      | 60.0%                      |       0.03 |              | 976.7%            |            406 |
| enet | all stocks | EW | after costs    | $303k         | -50.3%   | 7.4%   | 7.7%   |     0.48 | 14.2%        | -50.4%         | 34.8%                | 27.1%                      | 19.6%                      |      -2.17 |         0    | 976.8%            |            406 |
| enet | all stocks | VW | before costs   | $473k         | -22.2%   | 10.5%  | 10.5%  |     0.72 | 12.9%        | -41.4%         | 52.2%                | 59.2%                      | 50.0%                      |      -0.84 |              | 875.4%            |            406 |
| enet | all stocks | VW | after costs    | $407k         | -33.1%   | 9.5%   | 9.4%   |     0.64 | 12.9%        | -42.3%         | 43.5%                | 45.8%                      | 40.4%                      |      -1.68 |         0    | 875.3%            |            406 |
| enet | no microcaps | EW | before costs | $507k         | -16.7%   | 11.0%  | 11.5%  |     0.72 | 14.3%        | -42.5%         | 43.5%                | 60.8%                      | 65.0%                      |      -0.04 |              | 1073.2%           |            189 |
| enet | no microcaps | EW | after costs  | $374k         | -38.5%   | 8.9%   | 9.2%   |     0.58 | 14.3%        | -45.0%         | 30.4%                | 30.8%                      | 29.6%                      |      -1.45 |         0    | 1073.2%           |            189 |
| enet | no microcaps | VW | before costs | $467k         | -23.2%   | 10.5%  | 10.7%  |     0.73 | 13.0%        | -37.1%         | 43.5%                | 61.7%                      | 59.6%                      |      -0.64 |              | 1009.5%           |            189 |
| enet | no microcaps | VW | after costs  | $394k         | -35.3%   | 9.3%   | 9.5%   |     0.64 | 13.0%        | -38.0%         | 39.1%                | 54.2%                      | 44.6%                      |      -1.49 |         0    | 1009.4%           |            189 |
| gbrt | all stocks | EW | before costs   | $383k         | -37.1%   | 9.1%   | 10.2%  |     0.55 | 17.6%        | -48.1%         | 47.8%                | 30.4%                      | 36.2%                      |      -0.4  |              | 426.0%            |            406 |
| gbrt | all stocks | EW | after costs    | $282k         | -53.6%   | 6.9%   | 8.0%   |     0.44 | 17.5%        | -49.6%         | 43.5%                | 20.4%                      | 26.7%                      |      -1.54 |         0    | 426.2%            |            406 |
| gbrt | all stocks | VW | before costs   | $704k         | 15.7%    | 13.2%  | 12.6%  |     0.8  | 14.2%        | -43.1%         | 60.9%                | 68.8%                      | 64.2%                      |       1.26 |              | 249.1%            |            406 |
| gbrt | all stocks | VW | after costs    | $671k         | 10.3%    | 12.9%  | 12.3%  |     0.78 | 14.2%        | -43.2%         | 47.8%                | 65.4%                      | 58.3%                      |       0.85 |         0.16 | 249.2%            |            406 |
| gbrt | no microcaps | EW | before costs | $425k         | -30.2%   | 9.8%   | 10.7%  |     0.57 | 17.7%        | -46.7%         | 43.5%                | 30.8%                      | 42.1%                      |      -0.13 |              | 390.1%            |            189 |
| gbrt | no microcaps | EW | after costs  | $367k         | -39.7%   | 8.8%   | 9.7%   |     0.52 | 17.6%        | -47.3%         | 43.5%                | 27.1%                      | 36.7%                      |      -0.72 |         0.01 | 390.2%            |            189 |
| gbrt | no microcaps | VW | before costs | $757k         | 24.5%    | 13.7%  | 13.1%  |     0.82 | 14.4%        | -42.6%         | 56.5%                | 67.5%                      | 67.9%                      |       1.74 |              | 274.3%            |            189 |
| gbrt | no microcaps | VW | after costs  | $719k         | 18.1%    | 13.4%  | 12.8%  |     0.8  | 14.4%        | -42.7%         | 52.2%                | 66.7%                      | 63.7%                      |       1.35 |         0.3  | 274.4%            |            189 |
| nn3 | all stocks | EW | before costs    | $557k         | -8.4%    | 11.7%  | 13.9%  |     0.58 | 25.4%        | -58.7%         | 47.8%                | 29.6%                      | 45.0%                      |       1.22 |              | 1369.9%           |            406 |
| nn3 | all stocks | EW | after costs     | $173k         | -71.6%   | 3.3%   | 5.6%   |     0.28 | 25.2%        | -64.6%         | 30.4%                | 17.5%                      | 29.2%                      |      -0.97 |         0    | 1369.3%           |            406 |
| nn3 | all stocks | VW | before costs    | $351k         | -42.4%   | 8.5%   | 8.1%   |     0.4  | 21.0%        | -66.1%         | 34.8%                | 11.7%                      | 31.7%                      |      -0.81 |              | 1523.6%           |            406 |
| nn3 | all stocks | VW | after costs     | $242k         | -60.2%   | 5.8%   | 5.3%   |     0.28 | 21.0%        | -66.8%         | 26.1%                | 0.4%                       | 8.3%                       |      -1.94 |         0    | 1523.2%           |            406 |
| nn3 | no microcaps | EW | before costs  | $477k         | -21.7%   | 10.6%  | 11.7%  |     0.54 | 22.4%        | -58.2%         | 43.5%                | 27.9%                      | 45.4%                      |       0.66 |              | 1368.2%           |            189 |
| nn3 | no microcaps | EW | after costs   | $286k         | -53.0%   | 7.0%   | 8.1%   |     0.39 | 22.4%        | -60.2%         | 30.4%                | 14.2%                      | 25.4%                      |      -0.63 |         0.01 | 1368.0%           |            189 |
| nn3 | no microcaps | VW | before costs  | $546k         | -10.3%   | 11.5%  | 10.7%  |     0.53 | 20.3%        | -61.0%         | 43.5%                | 21.7%                      | 37.5%                      |       0.15 |              | 1437.0%           |            189 |
| nn3 | no microcaps | VW | after costs   | $403k         | -33.8%   | 9.4%   | 8.5%   |     0.43 | 20.3%        | -61.6%         | 39.1%                | 15.8%                      | 17.9%                      |      -0.78 |         0    | 1436.7%           |            189 |
| ols3 | all stocks | EW | before costs   | $601k         | -1.2%    | 12.2%  | 13.4%  |     0.69 | 18.2%        | -55.0%         | 43.5%                | 35.8%                      | 50.4%                      |       1.27 |              | 591.6%            |            406 |
| ols3 | all stocks | EW | after costs    | $470k         | -22.8%   | 10.5%  | 11.4%  |     0.6  | 18.2%        | -56.7%         | 43.5%                | 25.0%                      | 39.2%                      |       0.28 |         0.06 | 591.8%            |            406 |
| ols3 | all stocks | VW | before costs   | $615k         | 1.0%     | 12.3%  | 12.2%  |     0.73 | 15.2%        | -51.8%         | 52.2%                | 40.0%                      | 48.3%                      |       0.69 |              | 510.1%            |            406 |
| ols3 | all stocks | VW | after costs    | $562k         | -7.7%    | 11.7%  | 11.5%  |     0.69 | 15.2%        | -52.2%         | 47.8%                | 37.9%                      | 43.8%                      |       0.12 |         0.04 | 510.2%            |            406 |
| ols3 | no microcaps | EW | before costs | $602k         | -1.1%    | 12.2%  | 12.6%  |     0.66 | 18.2%        | -54.7%         | 47.8%                | 38.3%                      | 49.2%                      |       0.9  |              | 636.1%            |            189 |
| ols3 | no microcaps | EW | after costs  | $504k         | -17.1%   | 11.0%  | 11.3%  |     0.59 | 18.2%        | -55.9%         | 47.8%                | 30.4%                      | 45.0%                      |       0.24 |         0.05 | 636.3%            |            189 |
| ols3 | no microcaps | VW | before costs | $560k         | -8.0%    | 11.7%  | 11.8%  |     0.68 | 16.0%        | -52.5%         | 47.8%                | 34.2%                      | 43.8%                      |       0.35 |              | 586.5%            |            189 |
| ols3 | no microcaps | VW | after costs  | $507k         | -16.8%   | 11.0%  | 11.0%  |     0.63 | 16.0%        | -52.8%         | 43.5%                | 30.4%                      | 39.6%                      |      -0.14 |         0.02 | 586.6%            |            189 |

## Sharpe ratio by period

| strategy                                |   2003-2009 |   2010-2015 |   2016-2025* |
|:----------------------------------------|------------:|------------:|-------------:|
| SPY (before costs)                      |        0.31 |        0.99 |         0.85 |
| SPY                                     |        0.31 |        0.99 |         0.85 |
| market cap-weight (all stocks)          |        0.37 |        0.97 |         0.81 |
| equal-weight all stocks                 |        0.49 |        0.71 |         0.3  |
| equal-weight no microcaps               |        0.48 |        0.83 |         0.44 |
| enet | all stocks | EW | before costs   |        0.58 |        0.9  |         0.72 |
| enet | all stocks | EW | after costs    |        0.26 |        0.61 |         0.54 |
| enet | all stocks | VW | before costs   |        0.46 |        0.91 |         0.77 |
| enet | all stocks | VW | after costs    |        0.36 |        0.82 |         0.7  |
| enet | no microcaps | EW | before costs |        0.57 |        0.88 |         0.72 |
| enet | no microcaps | EW | after costs  |        0.4  |        0.73 |         0.6  |
| enet | no microcaps | VW | before costs |        0.6  |        0.92 |         0.7  |
| enet | no microcaps | VW | after costs  |        0.49 |        0.82 |         0.63 |
| gbrt | all stocks | EW | before costs   |        0.57 |        0.7  |         0.46 |
| gbrt | all stocks | EW | after costs    |        0.46 |        0.59 |         0.35 |
| gbrt | all stocks | VW | before costs   |        0.52 |        0.93 |         0.89 |
| gbrt | all stocks | VW | after costs    |        0.49 |        0.91 |         0.87 |
| gbrt | no microcaps | EW | before costs |        0.55 |        0.7  |         0.52 |
| gbrt | no microcaps | EW | after costs  |        0.5  |        0.65 |         0.47 |
| gbrt | no microcaps | VW | before costs |        0.54 |        0.93 |         0.92 |
| gbrt | no microcaps | VW | after costs  |        0.52 |        0.9  |         0.9  |
| nn3 | all stocks | EW | before costs    |        0.74 |        0.65 |         0.44 |
| nn3 | all stocks | EW | after costs     |        0.44 |        0.3  |         0.16 |
| nn3 | all stocks | VW | before costs    |        0.15 |        0.68 |         0.47 |
| nn3 | all stocks | VW | after costs     |        0.03 |        0.56 |         0.34 |
| nn3 | no microcaps | EW | before costs  |        0.56 |        0.63 |         0.48 |
| nn3 | no microcaps | EW | after costs   |        0.43 |        0.46 |         0.34 |
| nn3 | no microcaps | VW | before costs  |        0.25 |        0.74 |         0.64 |
| nn3 | no microcaps | VW | after costs   |        0.16 |        0.63 |         0.53 |
| ols3 | all stocks | EW | before costs   |        0.58 |        0.91 |         0.65 |
| ols3 | all stocks | EW | after costs    |        0.45 |        0.8  |         0.58 |
| ols3 | all stocks | VW | before costs   |        0.4  |        0.98 |         0.82 |
| ols3 | all stocks | VW | after costs    |        0.35 |        0.93 |         0.78 |
| ols3 | no microcaps | EW | before costs |        0.44 |        0.9  |         0.67 |
| ols3 | no microcaps | EW | after costs  |        0.36 |        0.84 |         0.61 |
| ols3 | no microcaps | VW | before costs |        0.41 |        0.96 |         0.7  |
| ols3 | no microcaps | VW | after costs  |        0.36 |        0.91 |         0.66 |
