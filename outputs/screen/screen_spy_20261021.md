# Cheap + profitable screen: SPY holdings as of 20-Oct-2026

Run 2026-10-21. 503 holdings; 373 usable (101 financials/real estate excluded, 36 without usable data or with negative book equity). Buckets use Ken French NYSE breakpoints (quintile 5 = cheapest / most profitable). Not investment advice; the historical edge was for ~200-stock portfolios, not single names.

## How many usable stocks fall in each cell (rows = cheapness quintile, columns = profitability)

|   bm_q |   1 |   2 |   3 |   4 |   5 |
|-------:|----:|----:|----:|----:|----:|
|      1 |   2 |   4 |  11 |  26 | 120 |
|      2 |   3 |  17 |  20 |  20 |  17 |
|      3 |   5 |  15 |  17 |  22 |  11 |
|      4 |  13 |   9 |  11 |   8 |   9 |
|      5 |   9 |   3 |   0 |   0 |   1 |

## Caveats on the definitions

- Profitability is operating profit / *book equity*. Companies with large goodwill from acquisitions (big book equity) look less profitable than their margins suggest, and companies with tiny book equity (heavy buybacks) look more profitable. Rows flagged in `check` deserve a manual look.
- yfinance maps some industries poorly (e.g. health insurers' medical costs are not 'cost of revenue'), which inflates their profitability.
- The S&P 500 is mostly large, expensive, profitable companies, so few land in the cheapest quintile; `--universe sptm` (S&P 1500) adds mid and small caps, where the value effect was historically stronger.

## Historical return vs market of each target cell (value-weighted, before fees)

- Cheapest + most profitable (5,5): +2.3%/yr 1964-2022, -2.1%/yr 2007-2022
- Expensive + unprofitable (1,1): -8.0%/yr 1964-2022, -2.4%/yr 2007-2022

## Cheapest + most profitable (both quintile 5): 1 stocks

| ticker   | name                 | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check   |
|:---------|:---------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:--------|
| CMCSA    | COMCAST CORP CLASS A | Communication Services | 1.03 |      5 |             78 |      5 |            4 | -5.2%           | -13.6%    |         78.4 |         |

## Broader cheap + profitable (quintiles 4-5 on both): 18 stocks

| ticker   | name                         | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check                                        |
|:---------|:-----------------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:---------------------------------------------|
| CMCSA    | COMCAST CORP CLASS A         | Communication Services | 1.03 |      5 |             78 |      5 |            4 | -5.2%           | -13.6%    |         78.4 |                                              |
| CVS      | CVS HEALTH CORP              | Healthcare             | 0.76 |      4 |             69 |      5 |            8 | 28.5%           | 6.5%      |        119.5 |                                              |
| CHTR     | CHARTER COMMUNICATIONS INC A | Communication Services | 0.67 |      4 |            134 |      5 |            1 | -44.6%          | -36.3%    |         12.3 | OP > 100% of book: verify costs / small book |
| EIX      | EDISON INTERNATIONAL         | Utilities              | 0.8  |      4 |             43 |      5 |            5 | 3.0%            | -13.5%    |         22   |                                              |
| APA      | APA CORP                     | Energy                 | 0.73 |      4 |             49 |      5 |           10 | 83.9%           | 35.8%     |         17.4 |                                              |
| HUM      | HUMANA INC                   | Healthcare             | 0.58 |      4 |            731 |      5 |            9 | 48.9%           | 40.5%     |         51.1 | OP > 100% of book: verify costs / small book |
| ES       | EVERSOURCE ENERGY            | Utilities              | 0.66 |      4 |             63 |      5 |            5 | 2.0%            | -4.6%     |         24.7 |                                              |
| ELV      | ELEVANCE HEALTH INC          | Healthcare             | 0.59 |      4 |            451 |      5 |            7 | 23.4%           | 18.0%     |         94.1 | OP > 100% of book: verify costs / small book |
| UHS      | UNIVERSAL HEALTH SERVICES B  | Healthcare             | 0.57 |      4 |            101 |      5 |            2 | -16.4%          | 3.0%      |         10.8 | OP > 100% of book: verify costs / small book |
| VZ       | VERIZON COMMUNICATIONS INC   | Communication Services | 0.66 |      4 |             39 |      5 |            7 | 21.6%           | -3.8%     |        181   |                                              |
| T        | AT+T INC                     | Communication Services | 0.68 |      4 |             35 |      4 |            4 | -4.0%           | -10.6%    |        150.1 |                                              |
| PFE      | PFIZER INC                   | Healthcare             | 0.64 |      4 |             35 |      4 |            7 | 19.5%           | 14.3%     |        170.1 |                                              |
| ED       | CONSOLIDATED EDISON INC      | Utilities              | 0.67 |      4 |             32 |      4 |            6 | 10.0%           | 4.2%      |         41.4 |                                              |
| EXC      | EXELON CORP                  | Utilities              | 0.66 |      4 |             29 |      4 |            4 | -0.2%           | -4.1%     |         44.4 |                                              |
| PSX      | PHILLIPS 66                  | Energy                 | 0.58 |      4 |             33 |      4 |           10 | 86.7%           | 50.6%     |        115.7 |                                              |
| BIIB     | BIOGEN INC                   | Healthcare             | 0.7  |      4 |             26 |      4 |            9 | 54.7%           | 21.2%     |         35.6 |                                              |
| CVX      | CHEVRON CORP                 | Energy                 | 0.64 |      4 |             27 |      4 |            8 | 38.0%           | 20.2%     |        444.9 |                                              |
| PNW      | PINNACLE WEST CAPITAL        | Utilities              | 0.67 |      4 |             26 |      4 |            6 | 13.1%           | 5.2%      |         12.6 |                                              |

## Expensive + unprofitable (quintiles 1-2 on both, historically the worst): 26 stocks

| ticker   | name                         | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check   |
|:---------|:-----------------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:--------|
| BA       | BOEING CO/THE                | Industrials            | 0.03 |      1 |            -84 |      1 |            4 | -3.7%           | -12.2%    |        152   |         |
| ECHO     | ECHOSTAR CORP A              | Communication Services | 0.18 |      1 |             -0 |      1 |            6 | 13.2%           | -14.0%    |         26.9 |         |
| TSLA     | TESLA INC                    | Consumer Cyclical      | 0.05 |      1 |             13 |      2 |            2 | -17.3%          | -0.1%     |       1526.4 |         |
| PANW     | PALO ALTO NETWORKS INC       | Technology             | 0.1  |      1 |             12 |      2 |           10 | 87.7%           | 32.0%     |        284.1 |         |
| AXON     | AXON ENTERPRISE INC          | Industrials            | 0.07 |      1 |             16 |      2 |            2 | -21.1%          | -17.1%    |         32.7 |         |
| SKYD     | SKYDANCE CORP                | Communication Services | 0.23 |      2 |             10 |      1 |            1 | -41.5%          | -22.4%    |         39.7 |         |
| MLM      | MARTIN MARIETTA MATERIALS    | Basic Materials        | 0.23 |      2 |             12 |      2 |            2 | -17.4%          | -12.0%    |         36.2 |         |
| COHR     | COHERENT CORP                | Technology             | 0.23 |      2 |             13 |      2 |           10 | 157.9%          | -19.5%    |         46.8 |         |
| TYL      | TYLER TECHNOLOGIES INC       | Technology             | 0.2  |      2 |             17 |      2 |            2 | -28.9%          | 11.0%     |         15.4 |         |
| SNPS     | SYNOPSYS INC                 | Technology             | 0.31 |      2 |             11 |      1 |            3 | -10.9%          | 1.3%      |         86.5 |         |
| DHR      | DANAHER CORP                 | Healthcare             | 0.33 |      2 |             11 |      1 |            5 | 8.3%            | 16.6%     |        164.4 |         |
| TECH     | BIO TECHNE CORP              | Healthcare             | 0.19 |      1 |             18 |      2 |            8 | 30.7%           | 15.7%     |         11.4 |         |
| TMO      | THERMO FISHER SCIENTIFIC INC | Healthcare             | 0.25 |      2 |             15 |      2 |            8 | 27.6%           | 26.7%     |        256.6 |         |
| VMC      | VULCAN MATERIALS CO          | Basic Materials        | 0.23 |      2 |             16 |      2 |            3 | -11.7%          | -5.7%     |         34.3 |         |
| ADI      | ANALOG DEVICES INC           | Technology             | 0.26 |      2 |             15 |      2 |            9 | 48.8%           | 10.8%     |        196.7 |         |
| RTX      | RTX CORP                     | Industrials            | 0.27 |      2 |             15 |      2 |            7 | 26.0%           | -1.3%     |        258.2 |         |
| AME      | AMETEK INC                   | Industrials            | 0.23 |      2 |             17 |      2 |            7 | 25.7%           | 7.6%      |         57.4 |         |
| CARR     | CARRIER GLOBAL CORP          | Industrials            | 0.32 |      2 |             15 |      2 |            4 | -1.0%           | -8.2%     |         46.5 |         |
| DOV      | DOVER CORP                   | Industrials            | 0.28 |      2 |             17 |      2 |            7 | 17.6%           | -4.3%     |         26.9 |         |
| CRL      | CHARLES RIVER LABORATORIES   | Healthcare             | 0.33 |      2 |             15 |      2 |           10 | 84.2%           | 59.0%     |         16.5 |         |
| MKC      | MCCORMICK + CO NON VTG SHRS  | Consumer Defensive     | 0.32 |      2 |             16 |      2 |            2 | -16.3%          | -12.6%    |         12.5 |         |
| IEX      | IDEX CORP                    | Industrials            | 0.31 |      2 |             16 |      2 |            9 | 42.6%           | 10.5%     |         17.4 |         |
| CPRT     | COPART INC                   | Industrials            | 0.25 |      2 |             18 |      2 |            2 | -26.6%          | -15.7%    |         25.6 |         |
| APD      | AIR PRODUCTS + CHEMICALS INC | Basic Materials        | 0.28 |      2 |             18 |      2 |            6 | 16.5%           | 6.1%      |         67.4 |         |
| IR       | INGERSOLL RAND INC           | Industrials            | 0.33 |      2 |             16 |      2 |            3 | -6.6%           | -2.9%     |         30.7 |         |
| STE      | STERIS PLC                   | Healthcare             | 0.33 |      2 |             16 |      2 |            4 | -5.5%           | -1.5%     |         21.6 |         |
