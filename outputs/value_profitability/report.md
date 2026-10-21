# Value + profitability (Ken French 5x5 BM x OP portfolios)

1964-01-31 → 2022-12-31; $5,000 each January; fees 0.25%/yr tilted, 0.03%/yr market.

| strategy                              | final_value   | vs_market   | xirr   |   sharpe | max_drawdown   | monthly_vs_market   |   t_stat |   p_holm |   median_firms |
|:--------------------------------------|:--------------|:------------|:-------|---------:|:---------------|:--------------------|---------:|---------:|---------------:|
| market                                | $18,784k      | 0.0%        | 10.5%  |     0.42 | -50.2%         | 0.0%                |          |          |                |
| cheap + most profitable (corner)      | $123,413k     | 557.0%      | 14.6%  |     0.39 | -88.9%         | 5.2%                |     1.74 |     0.16 |             25 |
| cheap + profitable (top 2 x top 2)    | $64,542k      | 243.6%      | 13.2%  |     0.51 | -57.9%         | 3.4%                |     2.43 |     0.08 |            204 |
| value trap: cheap + unprofitable      | $18,151k      | -3.4%       | 10.4%  |     0.43 | -68.0%         | 1.0%                |     1.01 |     0.31 |          1,055 |
| cheap (any profitability)             | $35,044k      | 86.6%       | 11.9%  |     0.5  | -65.3%         | 2.1%                |     2.18 |     0.12 |          1,505 |
| profitable (any price)                | $25,430k      | 35.4%       | 11.2%  |     0.47 | -48.1%         | 0.8%                |     2.11 |     0.12 |          1,101 |
| junk growth: expensive + unprofitable | $3,021k       | -83.9%      | 6.3%   |     0.15 | -74.8%         | -3.2%               |    -2.8  |     0.03 |            604 |
| all 25 cells (check vs market)        | $19,423k      | 3.4%        | 10.6%  |     0.43 | -50.3%         | 0.0%                |     0.37 |          |                |

`monthly_vs_market` is the gross average return gap, annualized (x12).

## Annualized return by era (after fees)

| strategy                              | 1964-1989   | 1990-2006   | 2007-2022   |
|:--------------------------------------|:------------|:------------|:------------|
| market                                | 10.5%       | 10.8%       | 8.7%        |
| cheap + most profitable (corner)      | 9.8%        | 21.8%       | 6.3%        |
| cheap + profitable (top 2 x top 2)    | 14.6%       | 17.2%       | 6.0%        |
| value trap: cheap + unprofitable      | 13.8%       | 12.3%       | 3.9%        |
| cheap (any profitability)             | 14.9%       | 14.1%       | 5.1%        |
| profitable (any price)                | 10.8%       | 11.8%       | 9.5%        |
| junk growth: expensive + unprofitable | 4.5%        | 4.3%        | 8.1%        |
| all 25 cells (check vs market)        | 10.6%       | 10.9%       | 8.6%        |

## Every 20-year window (monthly starts), ending value vs market

| strategy                              |   windows | median   | pct_beat   | worst   | best    |
|:--------------------------------------|----------:|:---------|:-----------|:--------|:--------|
| cheap + most profitable (corner)      |       469 | 201.0%   | 92.8%      | -42.2%  | 1334.0% |
| cheap + profitable (top 2 x top 2)    |       469 | 74.3%    | 86.8%      | -46.2%  | 163.8%  |
| value trap: cheap + unprofitable      |       469 | 6.7%     | 57.6%      | -54.9%  | 72.7%   |
| cheap (any profitability)             |       469 | 39.9%    | 78.5%      | -48.4%  | 87.7%   |
| profitable (any price)                |       469 | 9.5%     | 88.1%      | -5.4%   | 30.3%   |
| junk growth: expensive + unprofitable |       469 | -47.9%   | 7.0%       | -67.8%  | 51.3%   |

## 2023-2025 (descriptive)

| strategy                              | final_value   | xirr   | max_drawdown   |
|:--------------------------------------|:--------------|:-------|:---------------|
| market                                | $23k          | 23.2%  | -9.2%          |
| cheap + most profitable (corner)      | $18k          | 11.1%  | -34.2%         |
| cheap + profitable (top 2 x top 2)    | $24k          | 26.2%  | -11.7%         |
| value trap: cheap + unprofitable      | $21k          | 19.9%  | -13.2%         |
| cheap (any profitability)             | $22k          | 20.6%  | -12.5%         |
| profitable (any price)                | $23k          | 24.9%  | -8.8%          |
| junk growth: expensive + unprofitable | $23k          | 23.3%  | -13.8%         |
| all 25 cells (check vs market)        | $23k          | 23.3%  | -8.9%          |
