"""Local data access: CRSP daily prices and point-in-time DGS3MO, plus the data manifest.

Everything reads from ``data/raw/`` only; nothing here touches the network or other repos.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST = DATA_DIR / "MANIFEST.md"

PRICES_FILE = "prices_daily.parquet"  # CRSP 2010-01-04 .. 2025-12-31 (copied from regime-router)
HISTORY_FILE = "prices_daily_1993_2009.parquet"  # CRSP 1993-01-29 .. 2009-12-31 (scripts/fetch_crsp_history.py)
MACRO_FILE = "macro_pit.parquet"
RF_HISTORY_FILE = "dgs3mo_1993_2009.parquet"
END = pd.Timestamp("2025-12-31")  # 2026 is out of scope


def load_prices(include_history: bool = True) -> pd.DataFrame:
    """CRSP daily rows keyed on (permno, session); history file is stitched in front when present."""
    frames = [pd.read_parquet(RAW_DIR / PRICES_FILE)]
    hist = RAW_DIR / HISTORY_FILE
    if include_history and hist.exists():
        frames.insert(0, pd.read_parquet(hist))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["session"] <= END]
    return df.sort_values(["permno", "session"]).reset_index(drop=True)


def load_dgs3mo() -> pd.DataFrame:
    """DGS3MO observations with ``available_at`` (UTC), history file first when present."""
    m = pd.read_parquet(RAW_DIR / MACRO_FILE)
    m = m[m["series_id"] == "DGS3MO"][["observation_date", "value", "available_at"]]
    hist = RAW_DIR / RF_HISTORY_FILE
    if hist.exists():
        m = pd.concat([pd.read_parquet(hist)[m.columns], m], ignore_index=True)
    return m.dropna(subset=["value"]).sort_values("observation_date").reset_index(drop=True)


def session_close_times(prices: pd.DataFrame) -> pd.Series:
    """Session -> close timestamp (UTC), taken from the price panel's ``available_at``."""
    return prices.groupby("session")["available_at"].first().sort_index()


def rf_daily(prices: pd.DataFrame | None = None) -> pd.Series:
    """Annualized DGS3MO (decimal) known at each session's close; only past releases, forward-filled.

    NaN before the first release is available (never back-filled).
    """
    prices = load_prices() if prices is None else prices
    closes = session_close_times(prices).rename("close_ts").reset_index()
    obs = load_dgs3mo().sort_values("available_at")
    out = pd.merge_asof(
        closes.sort_values("close_ts"),
        obs[["available_at", "value"]],
        left_on="close_ts",
        right_on="available_at",
        direction="backward",
    )
    return out.set_index("session")["value"].div(100.0).rename("rf")


def wide(prices: pd.DataFrame, col: str) -> pd.DataFrame:
    """Session x permno panel of one column (NaN where a permno did not trade)."""
    return prices.pivot(index="session", columns="permno", values=col).astype(float).sort_index()


def total_return_index(prices: pd.DataFrame) -> pd.DataFrame:
    """Close-to-close total-return index from CRSP ``ret`` (dividends reinvested), 1.0 on each first day.

    NaN on sessions where the permno has no row (before listing, after delisting). The listing day has a
    row but no ret, so it starts the index at 1.0.
    """
    r = wide(prices, "ret")
    listed = prices.assign(_on=True).pivot(index="session", columns="permno", values="_on")
    listed = listed.reindex_like(r).notna()
    idx = (1.0 + r.fillna(0.0)).cumprod()
    return idx.where(listed)


def tickers(prices: pd.DataFrame) -> pd.Series:
    """permno -> most recent non-null ticker."""
    return prices.dropna(subset=["ticker"]).groupby("permno")["ticker"].last()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(sources: dict[str, str]) -> Path:
    """Rewrite ``data/MANIFEST.md`` describing every parquet in ``data/raw``.

    ``sources`` maps file name -> where it came from; files without an entry keep their old source line.
    """
    old = _manifest_sources()
    lines = [
        "# Data manifest",
        "",
        "Licensed CRSP data: never commit or publish. Regenerate with `scripts/copy_data.py` /",
        "`scripts/fetch_crsp_history.py`.",
        "",
        "| file | source | copied/fetched | rows | date range | sha256 |",
        "|---|---|---|---|---|---|",
    ]
    for f in sorted(RAW_DIR.glob("*.parquet")):
        df = pd.read_parquet(f)
        dcol = next(c for c in ("session", "observation_date", "date") if c in df)
        rng = f"{df[dcol].min():%Y-%m-%d} → {df[dcol].max():%Y-%m-%d}"
        src, when = sources.get(f.name), date.today().isoformat()
        if src is None:
            src, when = old.get(f.name, ("unknown", "unknown"))
        lines.append(f"| {f.name} | {src} | {when} | {len(df):,} | {rng} | `{sha256(f)}` |")
    MANIFEST.write_text("\n".join(lines) + "\n")
    return MANIFEST


def _manifest_sources() -> dict[str, tuple[str, str]]:
    if not MANIFEST.exists():
        return {}
    out = {}
    for line in MANIFEST.read_text().splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 6 and cells[0].endswith(".parquet"):
            out[cells[0]] = (cells[1], cells[2])
    return out


KF_FILE = "ff_factors_daily.parquet"
KF_MARKET = 1  # synthetic permno for the Ken French US market portfolio


def load_ken_french_panel() -> pd.DataFrame:
    """Ken French value-weighted US market (1926+) as an engine panel.

    No opens exist, so ``open`` is NaN and the engine fills at that day's close (signal at t's close, fill at
    t+1's close). ``rf`` is the daily T-bill return annualized (x 252). Treated as a 2 bps-spread fund.
    """
    kf = pd.read_parquet(RAW_DIR / KF_FILE).sort_values("date")
    px = (1 + kf["mkt"]).cumprod().to_numpy()
    return pd.DataFrame({
        "permno": KF_MARKET, "session": kf["date"].to_numpy(), "ticker": "MKT", "prc": px, "close": px,
        "open": np.nan, "ret": np.r_[np.nan, kf["mkt"].to_numpy()[1:]], "securitytype": "FUND",
        "tradingstatusflg": "A", "rf": kf["rf"].to_numpy() * 252,
    })  # fmt: skip
