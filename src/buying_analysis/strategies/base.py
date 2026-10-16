"""Shared helpers for strategies."""

from __future__ import annotations

import pandas as pd

from buying_analysis.backtest import Context

MIN_CASH_FRAC = 1e-4  # ignore idle cash below this fraction of equity


def is_period_start(ctx: Context, frequency: str) -> bool:
    """True on the first session of a month / week / year (known from today's and yesterday's dates)."""
    if len(ctx.sessions) < 2:
        return True
    a, b = ctx.sessions[-2], ctx.sessions[-1]
    if frequency == "monthly":
        return (a.year, a.month) != (b.year, b.month)
    if frequency == "quarterly":
        return (a.year, a.quarter) != (b.year, b.quarter)
    if frequency == "weekly":
        return a.to_period("W") != b.to_period("W")
    if frequency == "annual":
        return a.year != b.year
    raise ValueError(frequency)


def has_idle_cash(ctx: Context) -> bool:
    return ctx.equity > 0 and ctx.cash > max(1.0, MIN_CASH_FRAC * ctx.equity)


def horizon_end(ctx: Context, default_days: int = 365) -> pd.Timestamp:
    """When the current deposit should be fully deployed: the next deposit date (deposit plans are known in
    advance), or ``default_days`` after the latest deposit when no further deposit is scheduled."""
    later = ctx.deposits.index[ctx.deposits.index > ctx.date]
    if len(later):
        return later[0]
    last = ctx.deposits.index[ctx.deposits.index <= ctx.date]
    return (last[-1] if len(last) else ctx.date) + pd.Timedelta(days=default_days)
