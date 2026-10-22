# ML stock selection, holdout phase (2016-2025)

Top-1000 point-in-time universe; walk-forward (refit each January on realized targets); $5,000 each December month-end; equal-weight top-N; costs per side as labelled (SPY 2 bps).

## Portfolios (sorted by ending value)

| strategy                                  | final_value   | vs_spy   | xirr   |   sharpe | volatility   | max_drawdown   | worst_3y_vs_spy   | pct_3y_windows_beat_spy   |   excess_t |   dsr_vs_spy | turnover_per_yr   |   avg_holdings |
|:------------------------------------------|:--------------|:---------|:-------|---------:|:-------------|:---------------|:------------------|:--------------------------|-----------:|-------------:|:------------------|---------------:|
| xgboost | monthly | top 100 | 10 bps      | $138k         | 15.3%    | 17.9%  |     0.98 | 17.6%        | -18.7%         | -6.2%             | 86.7%                     |       1.48 |         0.33 | 1286.7%           |            100 |
| lightgbm | monthly | top 50 | 10 bps      | $134k         | 11.9%    | 17.4%  |     0.87 | 20.1%        | -23.4%         | -23.7%            | 68.7%                     |       1.18 |         0.23 | 1610.1%           |             50 |
| xgboost | monthly | top 100 | 20 bps      | $126k         | 5.9%     | 16.4%  |     0.98 | 17.6%        | -18.7%         | -6.2%             | 86.7%                     |       1.48 |         0.33 | 1286.7%           |            100 |
| lightgbm | monthly | top 50 | 20 bps      | $120k         | 0.6%     | 15.5%  |     0.87 | 20.1%        | -23.4%         | -23.7%            | 68.7%                     |       1.18 |         0.23 | 1610.0%           |             50 |
| universe cap-weight                       | $120k         | 0.3%     | 15.5%  |     0.88 | 15.5%        | -24.8%         | -5.4%             | 55.4%                     |       0.69 |         0.11 | 37.7%             |          1,000 |
| SPY                                       | $119k         | 0.0%     | 15.4%  |     0.89 | 15.0%        | -23.9%         | 0.0%              | 0.0%                      |            |              | 25.1%             |              1 |
| ridge | quarterly | top 50 | 10 bps       | $95k          | -20.1%   | 11.5%  |     0.59 | 18.4%        | -28.7%         | -23.3%            | 13.3%                     |      -0.91 |         0    | 479.3%            |             50 |
| ridge | quarterly | top 50 | 20 bps       | $93k          | -22.4%   | 11.0%  |     0.59 | 18.4%        | -28.7%         | -23.3%            | 13.3%                     |      -0.91 |         0    | 479.5%            |             50 |
| random_forest | monthly | top 50 | 10 bps | $92k          | -23.1%   | 10.9%  |     0.61 | 19.8%        | -36.2%         | -24.4%            | 26.5%                     |      -0.44 |         0.01 | 1550.3%           |             50 |
| universe equal-weight                     | $91k          | -23.9%   | 10.7%  |     0.61 | 17.8%        | -27.0%         | -21.7%            | 3.6%                      |      -1.2  |         0    | 148.4%            |          1,000 |
| random_forest | monthly | top 50 | 20 bps | $83k          | -30.2%   | 9.2%   |     0.61 | 19.8%        | -36.2%         | -24.4%            | 26.5%                     |      -0.44 |         0.01 | 1550.2%           |             50 |
| factor_score | monthly | top 50 | 10 bps  | $76k          | -36.1%   | 7.6%   |     0.58 | 16.3%        | -30.1%         | -36.1%            | 21.7%                     |      -1.46 |         0    | 1457.9%           |             50 |
| factor_score | monthly | top 50 | 20 bps  | $70k          | -41.5%   | 6.0%   |     0.58 | 16.3%        | -30.1%         | -36.1%            | 21.7%                     |      -1.46 |         0    | 1457.8%           |             50 |

DSR = probability the monthly excess over SPY has a positive Sharpe after 10 configurations.

## Ranking skill: information coefficient (monthly rank correlation of score vs realized return)

| model         |   horizon |   mean_ic |   ic_t | pct_months_positive   |
|:--------------|----------:|----------:|-------:|:----------------------|
| factor_score  |         1 |    0.0162 |   1.1  | 47.9%                 |
| lightgbm      |         1 |    0.0313 |   3.14 | 59.7%                 |
| random_forest |         1 |    0.0267 |   2.55 | 58.8%                 |
| ridge         |         3 |    0.0184 |   2.34 | 58.1%                 |
| xgboost       |         1 |    0.0355 |   3.93 | 66.4%                 |
