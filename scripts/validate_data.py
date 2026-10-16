"""Validate local data before any backtest; writes outputs/data_validation.md and exits 1 on any FAIL."""

import sys

from buying_analysis.data import ROOT
from buying_analysis.validate import FAIL, run_all, to_markdown


def main() -> int:
    checks = run_all()
    out = ROOT / "outputs" / "data_validation.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(to_markdown(checks))
    failed = [c.name for c in checks if c.status == FAIL]
    print(f"\nwrote {out}")
    if failed:
        print(f"FAILED: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
