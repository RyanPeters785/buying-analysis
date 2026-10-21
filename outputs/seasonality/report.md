# Seasonality (US market, excess return over T-bills)

## By calendar month, 1927-2022

| month   | mean   | median   | ci95   | pct_positive   |    p |   p_holm |
|:--------|:-------|:---------|:-------|:---------------|-----:|---------:|
| Jan     | 1.2%   | 1.3%     | 1.0%   | 60.4%          | 0.02 |     0.19 |
| Feb     | 0.3%   | 0.9%     | 0.8%   | 56.2%          | 0.44 |     1    |
| Mar     | 0.4%   | 1.0%     | 1.0%   | 63.5%          | 0.39 |     1    |
| Apr     | 1.1%   | 0.7%     | 1.3%   | 62.5%          | 0.09 |     0.6  |
| May     | 0.2%   | 1.2%     | 1.1%   | 61.5%          | 0.69 |     1    |
| Jun     | 0.6%   | 0.5%     | 1.0%   | 54.2%          | 0.27 |     1    |
| Jul     | 1.4%   | 1.4%     | 1.2%   | 58.3%          | 0.02 |     0.19 |
| Aug     | 0.9%   | 1.1%     | 1.2%   | 61.5%          | 0.15 |     0.9  |
| Sep     | -1.1%  | -0.3%    | 1.2%   | 46.9%          | 0.07 |     0.54 |
| Oct     | 0.2%   | 0.9%     | 1.3%   | 56.2%          | 0.72 |     1    |
| Nov     | 1.4%   | 2.0%     | 1.0%   | 67.7%          | 0.01 |     0.08 |
| Dec     | 1.3%   | 1.5%     | 0.8%   | 77.1%          | 0    |     0.01 |

## Mean by month, two halves

| month   | 1927-1974   | 1975-2022   |
|:--------|:------------|:------------|
| Jan     | 1.2%        | 1.1%        |
| Feb     | 0.3%        | 0.3%        |
| Mar     | 0.1%        | 0.8%        |
| Apr     | 0.8%        | 1.5%        |
| May     | -0.4%       | 0.8%        |
| Jun     | 0.7%        | 0.4%        |
| Jul     | 2.1%        | 0.7%        |
| Aug     | 1.5%        | 0.2%        |
| Sep     | -1.2%       | -1.0%       |
| Oct     | 0.0%        | 0.4%        |
| Nov     | 0.8%        | 2.1%        |
| Dec     | 1.4%        | 1.2%        |

## Winter (Nov-Apr) vs summer (May-Oct)

| period    | winter_monthly   | summer_monthly   | difference   |   t_stat | years_winter_beat_summer   |
|:----------|:-----------------|:-----------------|:-------------|---------:|:---------------------------|
| 1927-1974 | 0.8%             | 0.5%             | 0.3%         |     0.59 | 62.5%                      |
| 1975-2022 | 1.2%             | 0.3%             | 0.9%         |     2.37 | 68.8%                      |
| 1927-2022 | 1.0%             | 0.4%             | 0.6%         |     1.89 | 65.6%                      |

## Seasonal path (detrended): typical high and low

- US market 1927-1974: highest Sep 06 (+1.4%), lowest Oct 29 (-2.0%)
- US market 1975-2022: highest Jun 06 (+1.4%), lowest Oct 27 (-2.8%)
- SPY 1994-2022: highest Jan 03 (+0.6%), lowest Sep 30 (-3.0%)

## Daily (21-day smoothed), US market 1927-2022

- best stretch centred on Dec 31 (+14.5 bp/day), worst centred on Sep 17 (-8.8 bp/day); smoothed average below zero on 59 days, all between Feb 27 and Oct 19

## Strategy: Sell in May, $5,000 each January, 1927-2022

| strategy                     | final_value   | vs_buy_hold   | xirr   |   sharpe | max_drawdown   | avg_stock_weight   |
|:-----------------------------|:--------------|:--------------|:-------|---------:|:---------------|:-------------------|
| buy_and_hold                 | $769,919k     | 0.0%          | 10.5%  |     0.43 | -83.9%         | 100.0%             |
| sell_in_may (stocks Nov-Apr) | $283,416k     | -63.2%        | 9.2%   |     0.47 | -57.4%         | 50.0%              |
| opposite (stocks May-Oct)    | $8,384k       | -98.9%        | 4.6%   |     0.15 | -69.6%         | 50.0%              |

## 2023-2025 (descriptive)

| strategy                     | final_value   | vs_buy_hold   | xirr   |
|:-----------------------------|:--------------|:--------------|:-------|
| buy_and_hold                 | $23k          | 0.0%          | 23.3%  |
| sell_in_may (stocks Nov-Apr) | $17k          | -23.6%        | 7.9%   |
| opposite (stocks May-Oct)    | $22k          | -4.9%         | 20.3%  |
