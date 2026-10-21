# Factor tilts (Ken French size x value portfolios)

1927-07-01 → 2022-12-30; $5,000 each January; fees deducted: {'market': 0.0003, 'big_blend': 0.0003, 'big_growth': 0.0005, 'big_value': 0.001, 'small_blend': 0.0015, 'small_growth': 0.0025, 'small_value': 0.0025}.

| strategy                 | final_value   | vs_market   | xirr   |   sharpe | max_drawdown   |   longest_dd_days | final_value_ratio_lo   | final_value_ratio_hi   |
|:-------------------------|:--------------|:------------|:-------|---------:|:---------------|------------------:|:-----------------------|:-----------------------|
| market                   | $742,371k     | 0.0%        | 10.5%  |     0.43 | -84.0%         |             5,641 |                        |                        |
| small_growth             | $265,258k     | -64.3%      | 9.1%   |     0.33 | -89.7%         |             4,830 | -94.9%                 | 136.0%                 |
| small_blend              | $7,652,286k   | 930.8%      | 13.4%  |     0.54 | -86.6%         |             2,937 | 50.3%                  | 3953.5%                |
| small_value              | $29,896,126k  | 3927.1%     | 15.2%  |     0.56 | -89.4%         |             2,831 | 68.4%                  | 24165.4%               |
| big_growth               | $574,398k     | -22.6%      | 10.1%  |     0.41 | -82.5%         |             5,740 | -53.5%                 | 79.1%                  |
| big_blend                | $1,071,696k   | 44.4%       | 10.9%  |     0.43 | -89.4%         |             5,711 | -53.8%                 | 227.6%                 |
| big_value                | $5,080,072k   | 584.3%      | 12.9%  |     0.45 | -89.4%         |             5,416 | -29.7%                 | 3265.1%                |
| 70_market_30_small_value | $2,626,580k   | 253.8%      | 12.1%  |     0.5  | -85.1%         |             2,737 | 37.3%                  | 546.9%                 |
| 70_market_30_big_value   | $1,453,951k   | 95.9%       | 11.3%  |     0.45 | -85.6%         |             5,421 | -0.6%                  | 228.7%                 |

## Annualized return by era

| strategy                 | 1927-1963   | 1964-2006   | 2007-2022   |
|:-------------------------|:------------|:------------|:------------|
| market                   | 8.0%        | 10.6%       | 8.7%        |
| small_growth             | 7.6%        | 8.5%        | 7.6%        |
| small_blend              | 9.6%        | 15.6%       | 8.1%        |
| small_value              | 10.8%       | 18.1%       | 6.7%        |
| big_growth               | 7.9%        | 9.7%        | 10.6%       |
| big_blend                | 8.4%        | 11.7%       | 6.7%        |
| big_value                | 9.7%        | 14.4%       | 6.6%        |
| 70_market_30_small_value | 9.1%        | 13.1%       | 8.2%        |
| 70_market_30_big_value   | 8.8%        | 11.9%       | 8.2%        |

## Every 20-year window (quarterly starts), ending value vs market

| strategy                 |   windows | median_vs_market   | pct_beat_market   | worst   | best   |
|:-------------------------|----------:|:-------------------|:------------------|:--------|:-------|
| 70_market_30_big_value   |       306 | 15.4%              | 91.5%             | -13.7%  | 27.8%  |
| 70_market_30_small_value |       306 | 27.8%              | 96.1%             | -10.5%  | 51.5%  |
| big_blend                |       306 | 13.4%              | 85.3%             | -29.0%  | 30.1%  |
| big_growth               |       306 | -8.1%              | 28.8%             | -27.7%  | 30.0%  |
| big_value                |       306 | 53.9%              | 88.6%             | -42.4%  | 119.4% |
| small_blend              |       306 | 62.6%              | 91.2%             | -16.8%  | 156.6% |
| small_growth             |       306 | -13.3%             | 33.3%             | -69.3%  | 94.0%  |
| small_value              |       306 | 108.3%             | 95.8%             | -35.8%  | 275.3% |

## 2023-2025 (descriptive only)

| strategy                 | final_value   | xirr   | max_drawdown   |
|:-------------------------|:--------------|:-------|:---------------|
| market                   | $23k          | 22.3%  | -19.6%         |
| small_growth             | $19k          | 13.0%  | -30.6%         |
| small_blend              | $19k          | 11.7%  | -29.4%         |
| small_value              | $19k          | 11.0%  | -25.9%         |
| big_growth               | $24k          | 25.8%  | -21.5%         |
| big_blend                | $19k          | 13.5%  | -17.8%         |
| big_value                | $24k          | 25.0%  | -15.9%         |
| 70_market_30_small_value | $21k          | 19.1%  | -20.6%         |
| 70_market_30_big_value   | $23k          | 23.4%  | -17.9%         |
