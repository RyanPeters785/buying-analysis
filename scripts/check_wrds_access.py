"""Check WRDS access for the ML stock-selection study (one tiny query per table; nothing is saved).

    uv run --python 3.11 --group wrds scripts/check_wrds_access.py --wrds-username YOUR_USER

Needed: CRSP monthly stock file + names (universe, returns, market cap), CRSP daily (volatility features),
CRSP/Compustat link table, and Compustat annual fundamentals (valuation, profitability).
"""

from __future__ import annotations

import argparse

CHECKS = {
    "CRSP monthly stock file (crsp.msf_v2)":
        "select permno, mthcaldt, mthret, mthprc, shrout from crsp.msf_v2 where mthcaldt = '2015-12-31' limit 3",
    "CRSP names / share-type filters (crsp.stocknames_v2)":
        "select permno, ticker, sharetype, securitytype, securitysubtype, usincflg, issuertype, primaryexch "
        "from crsp.stocknames_v2 limit 3",
    "CRSP daily stock file (crsp.dsf_v2)":
        "select permno, dlycaldt, dlyret from crsp.dsf_v2 where dlycaldt = '2015-12-31' limit 3",
    "CRSP/Compustat link table (crsp.ccmxpf_lnkhist)":
        "select gvkey, lpermno, linktype, linkprim, linkdt, linkenddt from crsp.ccmxpf_lnkhist limit 3",
    "Compustat annual fundamentals (comp.funda)":
        "select gvkey, datadate, ceq, seq, txditc, pstk, revt, cogs, xsga, xint, at, ib, oancf, sale "
        "from comp.funda where indfmt = 'INDL' and datafmt = 'STD' and popsrc = 'D' and consol = 'C' "
        "and datadate = '2015-12-31' limit 3",
    "Compustat latest fiscal year available (comp.funda)":
        "select max(datadate) as latest from comp.funda where indfmt = 'INDL' and datafmt = 'STD'",
    "CRSP monthly latest date (crsp.msf_v2)": "select max(mthcaldt) as latest from crsp.msf_v2",
}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrds-username", required=True)
    args = ap.parse_args()
    import wrds

    db = wrds.Connection(wrds_username=args.wrds_username)
    ok = 0
    try:
        for name, sql in CHECKS.items():
            try:
                df = db.raw_sql(sql)
                ok += 1
                print(f"[OK]   {name}")
                print("       " + df.head(3).to_string().replace("\n", "\n       "))
            except Exception as e:  # noqa: BLE001
                print(f"[FAIL] {name}: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
    finally:
        db.close()
    print(f"\n{ok}/{len(CHECKS)} checks passed")


if __name__ == "__main__":
    main()
