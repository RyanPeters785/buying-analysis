# Country momentum and US vs international

$5,000 each January; always invested.

| study   | strategy               | start      | final_value   | xirr   | xirr_costs_x5   |   sharpe | max_drawdown   |   n_trades |   pct_beat_random |   months_in_intl |   switches |
|:--------|:-----------------------|:-----------|:--------------|:-------|:----------------|---------:|:---------------|-----------:|------------------:|-----------------:|-----------:|
| A       | country_top3_12-1      | 1997-04-01 | $345k         | 6.6%   | 5.9%            |     0.32 | -68.9%         |      1,169 |                85 |              nan |        nan |
| A       | B1_spy_buy_hold        | 1997-04-01 | $474k         | 8.6%   |                 |     0.41 | -55.3%         |         26 |               nan |              nan |        nan |
| A       | equal_weight_countries | 1997-04-01 | $302k         | 5.8%   |                 |     0.3  | -62.5%         |      8,381 |               nan |              nan |        nan |
| B       | us_vs_intl_12m         | 2002-09-03 | $303k         | 8.9%   | 8.7%            |     0.47 | -56.7%         |         53 |                91 |               93 |          9 |
| B       | B1_spy_buy_hold        | 2002-09-03 | $344k         | 9.9%   |                 |     0.5  | -55.3%         |         21 |               nan |              nan |        nan |
| B       | EFA_buy_hold           | 2002-09-03 | $175k         | 4.4%   |                 |     0.32 | -61.0%         |         21 |               nan |              nan |        nan |
| B       | 50_50_us_intl          | 2002-09-03 | $247k         | 7.3%   |                 |     0.42 | -57.9%         |        621 |               nan |              nan |        nan |

Random-portfolio medians: A $262k, B $256k.

## Annualized return by sub-period

| strategy               | 1997-2009   | 2010-2022   | 2002-2009   |
|:-----------------------|:------------|:------------|:------------|
| country_top3_12-1      | 8.3%        | 5.8%        |             |
| B1_spy_buy_hold        | 4.8%        | 12.1%       |             |
| equal_weight_countries | 8.3%        | 4.4%        |             |
| us_vs_intl_12m         |             | 9.9%        | 7.2%        |
| B1_spy_buy_hold        |             | 12.1%       | 4.9%        |
| EFA_buy_hold           |             | 4.3%        | 9.1%        |
| 50_50_us_intl          |             | 8.2%        | 7.2%        |

## 2023-2025 (descriptive only)

| strategy               | final_value   | xirr   | max_drawdown   |
|:-----------------------|:--------------|:-------|:---------------|
| country_top3_12-1      | $24k          | 26.4%  | -18.3%         |
| equal_weight_countries | $23k          | 22.1%  | -13.9%         |
| us_vs_intl_12m         | $21k          | 18.7%  | -18.8%         |
| B1_spy_buy_hold        | $23k          | 21.9%  | -18.8%         |
| EFA_buy_hold           | $21k          | 18.9%  | -14.1%         |
| 50_50_us_intl          | $22k          | 20.4%  | -15.1%         |

## Rolling gaps, latest (2025-12)

| series                             | gap   |
|:-----------------------------------|:------|
| 5y US minus developed ex-US (EFA)  | 5.3%  |
| 5y US minus emerging (EEM)         | 10.8% |
| 5y US minus avg country ex-US      | 4.0%  |
| 10y US minus developed ex-US (EFA) | 6.5%  |
| 10y US minus emerging (EEM)        | 6.9%  |
| 10y US minus avg country ex-US     | 5.2%  |
