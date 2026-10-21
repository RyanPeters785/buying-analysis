# Sector reversal (always invested)

2000-02-01 → 2022-12-30, $5,000 each January.

| strategy             | final_value   | xirr   |   sharpe | max_drawdown   |   n_trades | total_costs   | n2_median_final   |   n2_pct_final |   n2_pct_sharpe |
|:---------------------|:--------------|:-------|---------:|:---------------|-----------:|:--------------|:------------------|---------------:|----------------:|
| sector_bottom3_1-0   | $287k         | 7.0%   |     0.29 | -57.3%         |      1,429 | $10k          | $321k             |             31 |              32 |
| sector_bottom3_3-0   | $252k         | 6.1%   |     0.25 | -65.3%         |      1,084 | $5k           | $325k             |             12 |              12 |
| sector_top3_12-1     | $386k         | 9.1%   |     0.4  | -47.1%         |        782 | $3k           | $331k             |             78 |              81 |
| B1_spy_buy_hold      | $380k         | 9.0%   |     0.33 | -55.3%         |         23 | $0k           |                   |            nan |             nan |
| equal_weight_sectors | $395k         | 9.3%   |     0.41 | -53.3%         |      3,282 | $0k           |                   |            nan |             nan |

## Annualized return by half

| strategy             | 2000-2010   | 2011-2022   |
|:---------------------|:------------|:------------|
| sector_bottom3_1-0   | 2.4%        | 9.0%        |
| sector_bottom3_3-0   | 1.9%        | 7.6%        |
| sector_top3_12-1     | 4.1%        | 11.0%       |
| B1_spy_buy_hold      | 0.6%        | 11.8%       |
| equal_weight_sectors | 4.1%        | 11.2%       |
