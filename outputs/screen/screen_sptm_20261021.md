# Cheap + profitable screen: SPTM holdings as of 20-Oct-2026

Run 2026-10-21. 1506 holdings; 1090 usable (349 financials/real estate excluded, 78 without usable data or with negative book equity). Buckets use Ken French NYSE breakpoints (quintile 5 = cheapest / most profitable). Not investment advice; the historical edge was for ~200-stock portfolios, not single names.

## How many usable stocks fall in each cell (rows = cheapness quintile, columns = profitability)

|   bm_q |   1 |   2 |   3 |   4 |   5 |
|-------:|----:|----:|----:|----:|----:|
|      1 |  14 |  10 |  22 |  59 | 209 |
|      2 |  22 |  53 |  61 |  72 |  51 |
|      3 |  30 |  52 |  60 |  45 |  32 |
|      4 |  61 |  49 |  30 |  26 |  22 |
|      5 |  59 |  31 |  10 |   4 |   6 |

## Caveats on the definitions

- Profitability is operating profit / *book equity*. Companies with large goodwill from acquisitions (big book equity) look less profitable than their margins suggest, and companies with tiny book equity (heavy buybacks) look more profitable. Rows flagged in `check` deserve a manual look.
- yfinance maps some industries poorly (e.g. health insurers' medical costs are not 'cost of revenue'), which inflates their profitability.
- The S&P 500 is mostly large, expensive, profitable companies, so few land in the cheapest quintile; `--universe sptm` (S&P 1500) adds mid and small caps, where the value effect was historically stronger.

## Historical return vs market of each target cell (value-weighted, before fees)

- Cheapest + most profitable (5,5): +2.3%/yr 1964-2022, -2.1%/yr 2007-2022
- Expensive + unprofitable (1,1): -8.0%/yr 1964-2022, -2.4%/yr 2007-2022

## Cheapest + most profitable (both quintile 5): 6 stocks

| ticker   | name                     | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check   |
|:---------|:-------------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:--------|
| ZD       | ZIFF DAVIS INC           | Communication Services | 1.46 |      5 |             70 |      5 |            9 | 44.8%           | 22.3%     |          2   |         |
| ACHC     | ACADIA HEALTHCARE CO INC | Healthcare             | 1.48 |      5 |             51 |      5 |            6 | 11.3%           | 24.8%     |          2.9 |         |
| CMCSA    | COMCAST CORP CLASS A     | Communication Services | 1.03 |      5 |             78 |      5 |            4 | -5.2%           | -13.6%    |         78.4 |         |
| DXC      | DXC TECHNOLOGY CO        | Technology             | 1.2  |      5 |             42 |      5 |            2 | -17.1%          | 33.5%     |          2.5 |         |
| LKQ      | LKQ CORP                 | Consumer Cyclical      | 0.88 |      5 |             77 |      5 |            3 | -14.2%          | -21.3%    |          5.4 |         |
| KOP      | KOPPERS HOLDINGS INC     | Basic Materials        | 1.13 |      5 |             40 |      5 |           10 | 65.3%           | 0.9%      |          0.8 |         |

## Broader cheap + profitable (quintiles 4-5 on both): 58 stocks

| ticker   | name                         | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check                                        |
|:---------|:-----------------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:---------------------------------------------|
| ZD       | ZIFF DAVIS INC               | Communication Services | 1.46 |      5 |             70 |      5 |            9 | 44.8%           | 22.3%     |          2   |                                              |
| ACHC     | ACADIA HEALTHCARE CO INC     | Healthcare             | 1.48 |      5 |             51 |      5 |            6 | 11.3%           | 24.8%     |          2.9 |                                              |
| CMCSA    | COMCAST CORP CLASS A         | Communication Services | 1.03 |      5 |             78 |      5 |            4 | -5.2%           | -13.6%    |         78.4 |                                              |
| DXC      | DXC TECHNOLOGY CO            | Technology             | 1.2  |      5 |             42 |      5 |            2 | -17.1%          | 33.5%     |          2.5 |                                              |
| LKQ      | LKQ CORP                     | Consumer Cyclical      | 0.88 |      5 |             77 |      5 |            3 | -14.2%          | -21.3%    |          5.4 |                                              |
| CBRL     | CRACKER BARREL OLD COUNTRY   | Consumer Cyclical      | 0.83 |      4 |            197 |      5 |            8 | 28.7%           | 60.3%     |          1.5 | OP > 100% of book: verify costs / small book |
| KOP      | KOPPERS HOLDINGS INC         | Basic Materials        | 1.13 |      5 |             40 |      5 |           10 | 65.3%           | 0.9%      |          0.8 |                                              |
| PARR     | PAR PACIFIC HOLDINGS INC     | Energy                 | 0.86 |      4 |             68 |      5 |           10 | 125.6%          | 34.9%     |          4.2 |                                              |
| CRGY     | CRESCENT ENERGY INC A        | Energy                 | 1.92 |      5 |             34 |      4 |            9 | 60.1%           | 15.8%     |          4.5 |                                              |
| ABM      | ABM INDUSTRIES INC           | Industrials            | 0.74 |      4 |            445 |      5 |            5 | 3.8%            | 18.8%     |          3.1 | OP > 100% of book: verify costs / small book |
| UPBD     | UPBOUND GROUP INC            | Technology             | 0.73 |      4 |            190 |      5 |            2 | -17.4%          | -10.8%    |          0.9 | OP > 100% of book: verify costs / small book |
| GEO      | GEO GROUP INC/THE            | Industrials            | 0.71 |      4 |            148 |      5 |            9 | 55.2%           | 15.7%     |          3.6 | OP > 100% of book: verify costs / small book |
| CVS      | CVS HEALTH CORP              | Healthcare             | 0.76 |      4 |             69 |      5 |            8 | 28.5%           | 6.5%      |        119.5 |                                              |
| CHTR     | CHARTER COMMUNICATIONS INC A | Communication Services | 0.67 |      4 |            134 |      5 |            1 | -44.6%          | -36.3%    |         12.3 | OP > 100% of book: verify costs / small book |
| AVA      | AVISTA CORP                  | Utilities              | 0.87 |      4 |             42 |      5 |            5 | 3.1%            | -5.6%     |          3.1 |                                              |
| VTOL     | BRISTOW GROUP INC            | Energy                 | 0.98 |      5 |             36 |      4 |            8 | 26.9%           | -12.1%    |          1.1 |                                              |
| PRG      | PROG HOLDINGS INC            | Industrials            | 0.64 |      4 |            271 |      5 |            7 | 19.9%           | -13.6%    |          1.2 | OP > 100% of book: verify costs / small book |
| EIX      | EDISON INTERNATIONAL         | Utilities              | 0.8  |      4 |             43 |      5 |            5 | 3.0%            | -13.5%    |         22   |                                              |
| APA      | APA CORP                     | Energy                 | 0.73 |      4 |             49 |      5 |           10 | 83.9%           | 35.8%     |         17.4 |                                              |
| ANDE     | ANDERSONS INC/THE            | Consumer Defensive     | 0.7  |      4 |             54 |      5 |           10 | 65.3%           | -4.1%     |          2.2 |                                              |
| HUM      | HUMANA INC                   | Healthcare             | 0.58 |      4 |            731 |      5 |            9 | 48.9%           | 40.5%     |         51.1 | OP > 100% of book: verify costs / small book |
| ES       | EVERSOURCE ENERGY            | Utilities              | 0.66 |      4 |             63 |      5 |            5 | 2.0%            | -4.6%     |         24.7 |                                              |
| ELV      | ELEVANCE HEALTH INC          | Healthcare             | 0.59 |      4 |            451 |      5 |            7 | 23.4%           | 18.0%     |         94.1 | OP > 100% of book: verify costs / small book |
| KMT      | KENNAMETAL INC               | Industrials            | 0.66 |      4 |             60 |      5 |            9 | 43.6%           | -9.6%     |          2.4 |                                              |
| ADT      | ADT INC                      | Industrials            | 0.66 |      4 |             59 |      5 |            3 | -13.1%          | -2.9%     |          5   |                                              |
| UNFI     | UNITED NATURAL FOODS INC     | Consumer Defensive     | 0.58 |      4 |            252 |      5 |            6 | 16.6%           | 2.3%      |          2.8 | OP > 100% of book: verify costs / small book |
| UHS      | UNIVERSAL HEALTH SERVICES B  | Healthcare             | 0.57 |      4 |            101 |      5 |            2 | -16.4%          | 3.0%      |         10.8 | OP > 100% of book: verify costs / small book |
| CZR      | CAESARS ENTERTAINMENT INC    | Consumer Cyclical      | 0.74 |      4 |             43 |      5 |            6 | 9.9%            | 5.1%      |          5.9 |                                              |
| PRSU     | PURSUIT ATTRACTIONS AND HOSP | Consumer Cyclical      | 0.63 |      4 |             57 |      5 |            8 | 32.7%           | 26.6%     |          1.5 |                                              |
| VAC      | MARRIOTT VACATIONS WORLD     | Consumer Cyclical      | 1.03 |      5 |             27 |      4 |           10 | 62.3%           | 35.3%     |          3.9 |                                              |
| CRC      | CALIFORNIA RESOURCES CORP    | Energy                 | 0.94 |      5 |             28 |      4 |            5 | 1.9%            | -4.7%     |          4.8 |                                              |
| VZ       | VERIZON COMMUNICATIONS INC   | Communication Services | 0.66 |      4 |             39 |      5 |            7 | 21.6%           | -3.8%     |        181   |                                              |
| ALK      | ALASKA AIR GROUP INC         | Industrials            | 0.73 |      4 |             33 |      4 |            2 | -17.0%          | -24.6%    |          3.7 |                                              |
| T        | AT+T INC                     | Communication Services | 0.68 |      4 |             35 |      4 |            4 | -4.0%           | -10.6%    |        150.1 |                                              |
| PFE      | PFIZER INC                   | Healthcare             | 0.64 |      4 |             35 |      4 |            7 | 19.5%           | 14.3%     |        170.1 |                                              |
| SKYW     | SKYWEST INC                  | Industrials            | 0.7  |      4 |             31 |      4 |            4 | -5.9%           | -2.0%     |          3.7 |                                              |
| ED       | CONSOLIDATED EDISON INC      | Utilities              | 0.67 |      4 |             32 |      4 |            6 | 10.0%           | 4.2%      |         41.4 |                                              |
| REZI     | RESIDEO TECHNOLOGIES INC     | Industrials            | 0.79 |      4 |             27 |      4 |            1 | -35.6%          | -23.9%    |          2.7 |                                              |
| UTL      | UNITIL CORP                  | Utilities              | 0.71 |      4 |             29 |      4 |            6 | 16.1%           | 3.8%      |          1   |                                              |
| NWN      | NORTHWEST NATURAL HOLDING CO | Utilities              | 0.77 |      4 |             27 |      4 |            6 | 13.7%           | -1.3%     |          2.1 |                                              |
| RRX      | REGAL REXNORD CORP           | Industrials            | 0.74 |      4 |             27 |      4 |            6 | 11.1%           | -16.0%    |         10.6 |                                              |
| POR      | PORTLAND GENERAL ELECTRIC CO | Utilities              | 0.76 |      4 |             26 |      4 |            6 | 14.7%           | -10.7%    |          5.2 |                                              |
| SBH      | SALLY BEAUTY HOLDINGS INC    | Consumer Cyclical      | 0.59 |      4 |             33 |      4 |            4 | 0.6%            | 10.9%     |          1.6 |                                              |
| FLO      | FLOWERS FOODS INC            | Consumer Defensive     | 0.6  |      4 |             32 |      4 |            1 | -43.3%          | -26.3%    |          1.2 |                                              |
| EXC      | EXELON CORP                  | Utilities              | 0.66 |      4 |             29 |      4 |            4 | -0.2%           | -4.1%     |         44.4 |                                              |
| PSX      | PHILLIPS 66                  | Energy                 | 0.58 |      4 |             33 |      4 |           10 | 86.7%           | 50.6%     |        115.7 |                                              |
| PCRX     | PACIRA BIOSCIENCES INC       | Healthcare             | 0.67 |      4 |             28 |      4 |            4 | 0.5%            | 48.9%     |          1.5 |                                              |
| AEO      | AMERICAN EAGLE OUTFITTERS    | Consumer Cyclical      | 0.58 |      4 |             32 |      4 |            4 | -0.1%           | -5.5%     |          2.9 |                                              |
| BIIB     | BIOGEN INC                   | Healthcare             | 0.7  |      4 |             26 |      4 |            9 | 54.7%           | 21.2%     |         35.6 |                                              |
| DV       | DOUBLEVERIFY HOLDINGS INC    | Communication Services | 0.63 |      4 |             28 |      4 |            6 | 11.9%           | 20.7%     |          2.1 |                                              |
| AMPH     | AMPHASTAR PHARMACEUTICALS IN | Healthcare             | 0.69 |      4 |             25 |      4 |            3 | -15.5%          | 17.4%     |          1.1 |                                              |
| CVX      | CHEVRON CORP                 | Energy                 | 0.64 |      4 |             27 |      4 |            8 | 38.0%           | 20.2%     |        444.9 |                                              |
| GPI      | GROUP 1 AUTOMOTIVE INC       | Consumer Cyclical      | 0.6  |      4 |             28 |      4 |            1 | -38.1%          | -27.7%    |          2.7 |                                              |
| PNW      | PINNACLE WEST CAPITAL        | Utilities              | 0.67 |      4 |             26 |      4 |            6 | 13.1%           | 5.2%      |         12.6 |                                              |
| CWT      | CALIFORNIA WATER SERVICE GRP | Utilities              | 0.64 |      4 |             26 |      4 |            6 | 12.0%           | -0.4%     |          2.8 |                                              |
| AGCO     | AGCO CORP                    | Industrials            | 0.59 |      4 |             27 |      4 |            6 | 11.7%           | -9.3%     |          7.4 |                                              |
| UGI      | UGI CORP                     | Utilities              | 0.61 |      4 |             25 |      4 |            7 | 19.2%           | 7.1%      |          8.3 |                                              |
| OI       | O I GLASS INC                | Consumer Cyclical      | 0.57 |      4 |             25 |      4 |            1 | -43.9%          | -38.4%    |          0.9 |                                              |

## Expensive + unprofitable (quintiles 1-2 on both, historically the worst): 99 stocks

| ticker   | name                         | sector                 |   bm |   bm_q |   op_%_of_book |   op_q |   mom_decile | momentum_12_1   | vs_200d   |   mkt_cap_$B | check   |
|:---------|:-----------------------------|:-----------------------|-----:|-------:|---------------:|-------:|-------------:|:----------------|:----------|-------------:|:--------|
| LQDA     | LIQUIDIA CORP                | Healthcare             | 0.01 |      1 |            -81 |      1 |           10 | 199.8%          | -28.0%    |          3.5 |         |
| BA       | BOEING CO/THE                | Industrials            | 0.03 |      1 |            -84 |      1 |            4 | -3.7%           | -12.2%    |        152   |         |
| CC       | CHEMOURS CO/THE              | Basic Materials        | 0.14 |      1 |            -66 |      1 |            4 | 0.4%            | -29.3%    |          1.9 |         |
| GKOS     | GLAUKOS CORP                 | Healthcare             | 0.1  |      1 |             -8 |      1 |           10 | 120.2%          | 27.7%     |         10.4 |         |
| ROIV     | ROIVANT SCIENCES LTD         | Healthcare             | 0.17 |      1 |            -13 |      1 |           10 | 128.9%          | 18.7%     |         26.6 |         |
| TLN      | TALEN ENERGY CORP            | Utilities              | 0.06 |      1 |              7 |      1 |            2 | -30.5%          | 2.5%      |         17   |         |
| PTGX     | PROTAGONIST THERAPEUTICS INC | Healthcare             | 0.11 |      1 |              0 |      1 |           10 | 122.4%          | 20.6%     |          8.9 |         |
| SITM     | SITIME CORP                  | Technology             | 0.11 |      1 |              5 |      1 |           10 | 87.7%           | -6.2%     |         15.3 |         |
| WRBY     | WARBY PARKER INC CLASS A     | Healthcare             | 0.14 |      1 |             -1 |      1 |            3 | -10.8%          | 1.5%      |          3.2 |         |
| DK       | DELEK US HOLDINGS INC        | Energy                 | 0.16 |      1 |             -9 |      1 |           10 | 135.5%          | 52.7%     |          4.8 |         |
| KTOS     | KRATOS DEFENSE + SECURITY    | Industrials            | 0.14 |      1 |              3 |      1 |            1 | -44.2%          | -41.8%    |          7.3 |         |
| ECHO     | ECHOSTAR CORP A              | Communication Services | 0.18 |      1 |             -0 |      1 |            6 | 13.2%           | -14.0%    |         26.9 |         |
| TSLA     | TESLA INC                    | Consumer Cyclical      | 0.05 |      1 |             13 |      2 |            2 | -17.3%          | -0.1%     |       1526.4 |         |
| LEU      | CENTRUS ENERGY CORP CLASS A  | Energy                 | 0.15 |      1 |              8 |      1 |            1 | -44.7%          | -43.4%    |          2.2 |         |
| PANW     | PALO ALTO NETWORKS INC       | Technology             | 0.1  |      1 |             12 |      2 |           10 | 87.7%           | 32.0%     |        284.1 |         |
| MP       | MP MATERIALS CORP            | Basic Materials        | 0.22 |      2 |            -10 |      1 |            2 | -18.4%          | -29.5%    |          7   |         |
| ELF      | ELF BEAUTY INC               | Consumer Defensive     | 0.17 |      1 |              8 |      1 |            2 | -17.7%          | 41.7%     |          6.7 |         |
| RGEN     | REPLIGEN CORP                | Healthcare             | 0.2  |      2 |              4 |      1 |            8 | 35.4%           | 24.7%     |         11.4 |         |
| SEDG     | SOLAREDGE TECHNOLOGIES INC   | Technology             | 0.24 |      2 |             -8 |      1 |            3 | -13.0%          | -21.6%    |          2   |         |
| KRMN     | KARMAN HOLDINGS INC          | Industrials            | 0.04 |      1 |             16 |      2 |            1 | -42.6%          | -46.6%    |          4.7 |         |
| AORT     | ARTIVION INC                 | Healthcare             | 0.2  |      2 |              7 |      1 |            1 | -36.3%          | -24.0%    |          1.1 |         |
| AXTI     | AXT INC                      | Technology             | 0.25 |      2 |             -5 |      1 |           10 | 1249.9%         | -6.9%     |          3.9 |         |
| ALHC     | ALIGNMENT HEALTHCARE INC     | Healthcare             | 0.04 |      1 |             16 |      2 |            2 | -23.2%          | -51.1%    |          1.8 |         |
| AXON     | AXON ENTERPRISE INC          | Industrials            | 0.07 |      1 |             16 |      2 |            2 | -21.1%          | -17.1%    |         32.7 |         |
| VCEL     | VERICEL CORP                 | Healthcare             | 0.19 |      2 |             11 |      1 |            8 | 26.8%           | 6.3%      |          2.1 |         |
| PRVA     | PRIVIA HEALTH GROUP INC      | Healthcare             | 0.24 |      2 |              6 |      1 |            2 | -17.7%          | -1.1%     |          2.9 |         |
| OKTA     | OKTA INC                     | Technology             | 0.19 |      2 |             11 |      1 |           10 | 88.7%           | 73.6%     |         36.5 |         |
| SDGR     | SCHRODINGER INC              | Healthcare             | 0.27 |      2 |              2 |      1 |            4 | -2.8%           | 45.0%     |          1.8 |         |
| STAA     | STAAR SURGICAL CO            | Healthcare             | 0.3  |      2 |             -2 |      1 |            3 | -15.9%          | -8.2%     |          1.1 |         |
| BTSG     | BRIGHTSPRING HEALTH SERVICES | Healthcare             | 0.25 |      2 |              7 |      1 |           10 | 97.6%           | 15.6%     |         12.3 |         |
| SKYD     | SKYDANCE CORP                | Communication Services | 0.23 |      2 |             10 |      1 |            1 | -41.5%          | -22.4%    |         39.7 |         |
| APG      | API GROUP CORP               | Industrials            | 0.21 |      2 |             12 |      2 |            6 | 14.2%           | -4.2%     |         17.4 |         |
| SGI      | SOMNIGROUP INTERNATIONAL INC | Consumer Cyclical      | 0.15 |      1 |             15 |      2 |            2 | -22.5%          | -15.5%    |         14.5 |         |
| FTRE     | FORTREA HOLDINGS INC         | Healthcare             | 0.34 |      2 |             -8 |      1 |           10 | 118.2%          | 55.5%     |          2.3 |         |
| VSEC     | VSE CORP                     | Industrials            | 0.3  |      2 |              7 |      1 |            7 | 25.8%           | -22.2%    |          4.3 |         |
| MLM      | MARTIN MARIETTA MATERIALS    | Basic Materials        | 0.23 |      2 |             12 |      2 |            2 | -17.4%          | -12.0%    |         36.2 |         |
| ROAD     | CONSTRUCTION PARTNERS INC A  | Industrials            | 0.15 |      1 |             16 |      2 |            2 | -16.4%          | -24.2%    |          4.8 |         |
| MIR      | MIRION TECHNOLOGIES INC      | Industrials            | 0.33 |      2 |              3 |      1 |            1 | -35.2%          | -17.4%    |          3.7 |         |
| DAN      | DANA INC                     | Consumer Cyclical      | 0.33 |      2 |              4 |      1 |            9 | 52.0%           | -6.4%     |          3.1 |         |
| MRCY     | MERCURY SYSTEMS INC          | Industrials            | 0.33 |      2 |              5 |      1 |            6 | 12.8%           | -18.1%    |          4.6 |         |
| RBC      | RBC BEARINGS INC             | Industrials            | 0.21 |      2 |             14 |      2 |            8 | 26.6%           | -8.7%     |         16   |         |
| COHR     | COHERENT CORP                | Technology             | 0.23 |      2 |             13 |      2 |           10 | 157.9%          | -19.5%    |         46.8 |         |
| WOR      | WORTHINGTON ENTERPRISES INC  | Industrials            | 0.32 |      2 |              8 |      1 |            5 | 4.6%            | 16.8%     |          3.2 |         |
| RDNT     | RADNET INC                   | Healthcare             | 0.19 |      2 |             15 |      2 |            4 | -0.5%           | 4.8%      |          5.4 |         |
| CVI      | CVR ENERGY INC               | Energy                 | 0.29 |      2 |             11 |      1 |            6 | 15.5%           | 76.7%     |          6.1 |         |
| AAON     | AAON INC                     | Industrials            | 0.14 |      1 |             18 |      2 |            2 | -18.5%          | -23.2%    |          6.2 |         |
| NPO      | ENPRO INC                    | Industrials            | 0.34 |      2 |              8 |      1 |            8 | 31.6%           | -0.0%     |          6.2 |         |
| ACI      | ALBERTSONS COS INC   CLASS A | Consumer Defensive     | 0.28 |      2 |             12 |      2 |            2 | -26.5%          | -9.9%     |          6.5 |         |
| KRYS     | KRYSTAL BIOTECH INC          | Healthcare             | 0.17 |      1 |             18 |      2 |           10 | 103.6%          | 5.1%      |          9.5 |         |
| CENX     | CENTURY ALUMINUM COMPANY     | Basic Materials        | 0.21 |      2 |             16 |      2 |            9 | 55.9%           | -31.4%    |          3.4 |         |
| TYL      | TYLER TECHNOLOGIES INC       | Technology             | 0.2  |      2 |             17 |      2 |            2 | -28.9%          | 11.0%     |         15.4 |         |
| SNPS     | SYNOPSYS INC                 | Technology             | 0.31 |      2 |             11 |      1 |            3 | -10.9%          | 1.3%      |         86.5 |         |
| CSW      | CSW INDUSTRIALS INC          | Industrials            | 0.22 |      2 |             15 |      2 |            8 | 27.8%           | 0.7%      |          4.8 |         |
| CELH     | CELSIUS HOLDINGS INC         | Consumer Defensive     | 0.25 |      2 |             14 |      2 |            1 | -45.3%          | -19.9%    |          7.2 |         |
| H        | HYATT HOTELS CORP   CL A     | Consumer Cyclical      | 0.22 |      2 |             16 |      2 |            7 | 18.1%           | 5.5%      |         16.8 |         |
| DHR      | DANAHER CORP                 | Healthcare             | 0.33 |      2 |             11 |      1 |            5 | 8.3%            | 16.6%     |        164.4 |         |
| TECH     | BIO TECHNE CORP              | Healthcare             | 0.19 |      1 |             18 |      2 |            8 | 30.7%           | 15.7%     |         11.4 |         |
| SXI      | STANDEX INTERNATIONAL CORP   | Industrials            | 0.23 |      2 |             16 |      2 |            8 | 37.4%           | -2.6%     |          3.3 |         |
| TMO      | THERMO FISHER SCIENTIFIC INC | Healthcare             | 0.25 |      2 |             15 |      2 |            8 | 27.6%           | 26.7%     |        256.6 |         |
| VMC      | VULCAN MATERIALS CO          | Basic Materials        | 0.23 |      2 |             16 |      2 |            3 | -11.7%          | -5.7%     |         34.3 |         |
| NVT      | NVENT ELECTRIC PLC           | Industrials            | 0.23 |      2 |             17 |      2 |            9 | 53.9%           | 1.6%      |         23.7 |         |
| ESE      | ESCO TECHNOLOGIES INC        | Technology             | 0.3  |      2 |             14 |      2 |            8 | 29.5%           | -13.5%    |          6.4 |         |
| ADI      | ANALOG DEVICES INC           | Technology             | 0.26 |      2 |             15 |      2 |            9 | 48.8%           | 10.8%     |        196.7 |         |
| RTX      | RTX CORP                     | Industrials            | 0.27 |      2 |             15 |      2 |            7 | 26.0%           | -1.3%     |        258.2 |         |
| AME      | AMETEK INC                   | Industrials            | 0.23 |      2 |             17 |      2 |            7 | 25.7%           | 7.6%      |         57.4 |         |
| FORM     | FORMFACTOR INC               | Technology             | 0.24 |      2 |             17 |      2 |           10 | 176.2%          | -0.7%     |          8.8 |         |
| LGND     | LIGAND PHARMACEUTICALS       | Healthcare             | 0.27 |      2 |             15 |      2 |            9 | 60.4%           | 26.6%     |          6.3 |         |
| SPXC     | SPX TECHNOLOGIES INC         | Industrials            | 0.22 |      2 |             18 |      2 |            5 | 5.3%            | -19.6%    |          8.4 |         |
| ONTO     | ONTO INNOVATION INC          | Technology             | 0.27 |      2 |             15 |      2 |           10 | 106.8%          | -14.7%    |         10.9 |         |
| LPX      | LOUISIANA PACIFIC CORP       | Industrials            | 0.31 |      2 |             14 |      2 |            2 | -19.4%          | -3.6%     |          5.1 |         |
| ATRC     | ATRICURE INC                 | Healthcare             | 0.24 |      2 |             17 |      2 |            8 | 37.2%           | 54.4%     |          2.9 |         |
| SXT      | SENSIENT TECHNOLOGIES CORP   | Basic Materials        | 0.3  |      2 |             15 |      2 |            9 | 46.0%           | 17.9%     |          5.6 |         |
| PGNY     | PROGYNY INC                  | Healthcare             | 0.26 |      2 |             17 |      2 |            7 | 18.9%           | 17.0%     |          2.2 |         |
| HXL      | HEXCEL CORP                  | Industrials            | 0.23 |      2 |             18 |      2 |            9 | 49.0%           | -0.7%     |          6.8 |         |
| BCPC     | BALCHEM CORP                 | Basic Materials        | 0.26 |      2 |             17 |      2 |            7 | 17.9%           | 1.2%      |          5.4 |         |
| SAIA     | SAIA INC                     | Industrials            | 0.3  |      2 |             16 |      2 |            7 | 18.6%           | -12.9%    |          9   |         |
| KAI      | KADANT INC                   | Industrials            | 0.29 |      2 |             16 |      2 |            4 | 1.0%            | -13.5%    |          3.1 |         |
| CARR     | CARRIER GLOBAL CORP          | Industrials            | 0.32 |      2 |             15 |      2 |            4 | -1.0%           | -8.2%     |         46.5 |         |
| MMSI     | MERIT MEDICAL SYSTEMS INC    | Healthcare             | 0.3  |      2 |             16 |      2 |            5 | 8.9%            | 19.1%     |          5.5 |         |
| DOV      | DOVER CORP                   | Industrials            | 0.28 |      2 |             17 |      2 |            7 | 17.6%           | -4.3%     |         26.9 |         |
| CRL      | CHARLES RIVER LABORATORIES   | Healthcare             | 0.33 |      2 |             15 |      2 |           10 | 84.2%           | 59.0%     |         16.5 |         |
| AZZ      | AZZ INC                      | Industrials            | 0.32 |      2 |             16 |      2 |            7 | 26.5%           | 1.1%      |          4.2 |         |
| MKC      | MCCORMICK + CO NON VTG SHRS  | Consumer Defensive     | 0.32 |      2 |             16 |      2 |            2 | -16.3%          | -12.6%    |         12.5 |         |
| IEX      | IDEX CORP                    | Industrials            | 0.31 |      2 |             16 |      2 |            9 | 42.6%           | 10.5%     |         17.4 |         |
| OSW      | ONESPAWORLD HOLDINGS LTD     | Consumer Cyclical      | 0.26 |      2 |             18 |      2 |            7 | 18.5%           | 1.1%      |          2.4 |         |
| CACI     | CACI INTERNATIONAL INC  CL A | Technology             | 0.32 |      2 |             16 |      2 |            7 | 24.9%           | 10.1%     |         13.8 |         |
| SANM     | SANMINA CORP                 | Technology             | 0.29 |      2 |             17 |      2 |           10 | 70.9%           | -10.2%    |          9.2 |         |
| ESAB     | ESAB CORP                    | Industrials            | 0.31 |      2 |             16 |      2 |            1 | -32.3%          | -30.0%    |          4.1 |         |
| CPRT     | COPART INC                   | Industrials            | 0.25 |      2 |             18 |      2 |            2 | -26.6%          | -15.7%    |         25.6 |         |
| APD      | AIR PRODUCTS + CHEMICALS INC | Basic Materials        | 0.28 |      2 |             18 |      2 |            6 | 16.5%           | 6.1%      |         67.4 |         |
| ITT      | ITT INC                      | Industrials            | 0.26 |      2 |             18 |      2 |            6 | 12.7%           | 1.2%      |         18   |         |
| SARO     | STANDARDAERO INC             | Industrials            | 0.28 |      2 |             18 |      2 |            3 | -10.3%          | -20.3%    |          7.1 |         |
| IR       | INGERSOLL RAND INC           | Industrials            | 0.33 |      2 |             16 |      2 |            3 | -6.6%           | -2.9%     |         30.7 |         |
| STE      | STERIS PLC                   | Healthcare             | 0.33 |      2 |             16 |      2 |            4 | -5.5%           | -1.5%     |         21.6 |         |
| RBA      | RB GLOBAL INC                | Industrials            | 0.32 |      2 |             17 |      2 |            2 | -21.4%          | -18.1%    |         15.2 |         |
| FRSH     | FRESHWORKS INC CL A          | Technology             | 0.32 |      2 |             17 |      2 |            7 | 18.3%           | 43.8%     |          3.9 |         |
| NOVT     | NOVANTA INC                  | Technology             | 0.29 |      2 |             18 |      2 |            9 | 46.0%           | -1.3%     |          5.3 |         |
| KGS      | KODIAK GAS SERVICES INC      | Energy                 | 0.33 |      2 |             17 |      2 |           10 | 65.0%           | -16.0%    |          5   |         |
| PSMT     | PRICESMART INC               | Consumer Defensive     | 0.33 |      2 |             18 |      2 |            9 | 41.5%           | 4.1%      |          5.3 |         |
