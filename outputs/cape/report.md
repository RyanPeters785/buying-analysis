# CAPE valuation timing (1927-2022)

Latest real-time CAPE in the data: 31.0 (88th percentile of its history), 2023-09.

| strategy      | final_value   | vs_buy_hold   | xirr   |   sharpe | max_drawdown   | avg_stock_weight   |   months_reduced |   exits |   pct_beat_random |
|:--------------|:--------------|:--------------|:-------|---------:|:---------------|:-------------------|-----------------:|--------:|------------------:|
| buy_and_hold  | $769,919k     | 0.0%          | 10.5%  |     0.43 | -83.9%         | 100.0%             |                0 |       0 |             nan   |
| cape_p70_out  | $105,333k     | -86.3%        | 8.0%   |     0.36 | -71.7%         | 53.8%              |              532 |      15 |              80.2 |
| cape_p70_half | $317,120k     | -58.8%        | 9.4%   |     0.42 | -77.3%         | 76.9%              |              532 |      15 |              82   |
| cape_p80_out  | $143,838k     | -81.3%        | 8.4%   |     0.37 | -76.1%         | 65.6%              |              396 |      16 |              67.6 |
| cape_p80_half | $360,164k     | -53.2%        | 9.5%   |     0.42 | -78.4%         | 82.8%              |              396 |      16 |              67.3 |
| cape_p90_out  | $461,271k     | -40.1%        | 9.9%   |     0.41 | -83.9%         | 91.9%              |               93 |       4 |              48   |
| cape_p90_half | $611,952k     | -20.5%        | 10.2%  |     0.42 | -83.9%         | 96.0%              |               93 |       4 |              51.3 |

## Annualized return by era

| strategy      | 1927-1963   | 1964-1994   | 1995-2022   |
|:--------------|:------------|:------------|:------------|
| buy_and_hold  | 9.2%        | 10.2%       | 10.0%       |
| cape_p70_out  | 10.0%       | 9.2%        | 3.4%        |
| cape_p70_half | 9.7%        | 9.8%        | 7.0%        |
| cape_p80_out  | 10.0%       | 9.8%        | 3.7%        |
| cape_p80_half | 9.7%        | 10.1%       | 7.1%        |
| cape_p90_out  | 9.2%        | 10.2%       | 8.0%        |
| cape_p90_half | 9.2%        | 10.2%       | 9.1%        |

## Every 20-year window (monthly starts) vs buy-and-hold

| strategy      |   windows | median   | pct_beat   |
|:--------------|----------:|:---------|:-----------|
| cape_p70_out  |       913 | -14.3%   | 24.3%      |
| cape_p70_half |       913 | -6.7%    | 24.6%      |
| cape_p80_out  |       913 | -4.6%    | 13.4%      |
| cape_p80_half |       913 | -1.8%    | 13.7%      |
| cape_p90_out  |       913 | 0.0%     | 4.8%       |
| cape_p90_half |       913 | 0.0%     | 4.9%       |

## Share of months out of stocks, 80th-percentile all-out rule, by decade

|   decade | share_out   |
|---------:|:------------|
|     1920 | 38.9%       |
|     1930 | 3.3%        |
|     1940 | 0.0%        |
|     1950 | 0.0%        |
|     1960 | 60.8%       |
|     1970 | 0.0%        |
|     1980 | 0.0%        |
|     1990 | 65.8%       |
|     2000 | 84.2%       |
|     2010 | 74.2%       |
|     2020 | 100.0%      |

## Does CAPE predict returns? (descriptive, full-sample quintiles)

| horizon   | corr_log_cape_vs_fwd_return   | r_squared   | ann_return_cheapest   | ann_return_2   | ann_return_3   | ann_return_4   | ann_return_most expensive   |
|:----------|:------------------------------|:------------|:----------------------|:---------------|:---------------|:---------------|:----------------------------|
| 1y        | -27.0%                        | 7.3%        | 21.2%                 | 12.4%          | 5.2%           | 5.7%           | 5.7%                        |
| 10y       | -66.3%                        | 44.0%       | 15.0%                 | 13.2%          | 10.0%          | 7.8%           | 6.1%                        |
