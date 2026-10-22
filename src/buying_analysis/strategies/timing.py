"""Rule-based timing / allocation strategies (4-8). All signals use total-return index closes through t.

Shared behaviour (``Allocator``): the strategy computes a desired allocation when its rule is evaluated
(daily or on the first session of each month); the engine trades when that allocation changes, and new
deposits are invested in the current allocation (or kept in cash when the allocation is cash).
"""

from __future__ import annotations

import numpy as np

from buying_analysis.backtest import Context, Strategy, Weights
from buying_analysis.strategies.base import has_idle_cash, is_period_start

SPY, IEF = 84398, 89469
SECTORS = (86449, 86451, 86452, 86453, 86454, 86455, 86456, 86457, 86458, 15732, 17940)
# XLB XLV XLP XLY XLE XLF XLI XLK XLU XLRE XLC
MONTH = 21  # sessions


class Allocator(Strategy):
    frequency = "daily"  # or "monthly": evaluate on the first session of each month
    band = 0.0  # re-trade only if some weight moves by more than this

    def reset(self):
        self.current: Weights = {}
        self.started = False

    def allocation(self, ctx: Context) -> Weights | None:
        raise NotImplementedError

    def decide(self, ctx: Context):
        evaluate = self.frequency == "daily" or is_period_start(ctx, "monthly") or not self.started
        if evaluate:
            new = self.allocation(ctx)
            if new is not None:
                self.started = True
                new = {p: w for p, w in new.items() if w > 0 and ctx.tradable(p)}
                if self._changed(new):
                    self.current = new
                    return dict(new)
        if self.current and has_idle_cash(ctx) and ctx.deposit_today():
            return dict(self.current)
        return None

    def _changed(self, new: Weights) -> bool:
        keys = set(new) | set(self.current)
        if set(new) != set(self.current):
            return True
        return any(abs(new.get(k, 0) - self.current.get(k, 0)) > self.band for k in keys)


def month_end_positions(ctx: Context) -> np.ndarray:
    """Indices (into ctx history) of completed month-end sessions strictly before today."""
    s = ctx.sessions
    if len(s) < 2:
        return np.array([], int)
    ym = s.year * 12 + s.month
    return np.flatnonzero(ym[1:] != ym[:-1])  # last session of each month, before the current one


def sma(x: np.ndarray, n: int) -> float:
    return float(np.mean(x[-n:])) if len(x) >= n and not np.isnan(x[-n:]).any() else np.nan


def rsi(x: np.ndarray, n: int = 2) -> float:
    """Wilder RSI over n periods (seeded with a simple average over the available window)."""
    x = x[~np.isnan(x)]
    if len(x) < n + 1:
        return np.nan
    d = np.diff(x[-(10 * n + 1) :])
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    for u, v in zip(up[n:], dn[n:]):
        au, ad = (au * (n - 1) + u) / n, (ad * (n - 1) + v) / n
    return 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)


class TrendSMA(Allocator):
    """Hold the asset when its last month-end close is above the average of the last ``months`` month-ends."""

    frequency = "monthly"

    def __init__(self, asset: int = SPY, months: int = 10):
        self.asset, self.months = asset, months
        self.assets = (asset,)
        self.name = f"trend_sma{months}m"

    def allocation(self, ctx):
        me = month_end_positions(ctx)
        if len(me) < self.months:
            return None
        x = ctx.close(self.asset)[me[-self.months :]]
        if np.isnan(x).any():
            return None
        return {self.asset: 1.0} if x[-1] > x.mean() else {}


class SMACross(Allocator):
    """Hold the asset when its fast SMA is above its slow SMA (daily)."""

    def __init__(self, asset: int = SPY, fast: int = 50, slow: int = 200):
        self.asset, self.fast, self.slow = asset, fast, slow
        self.assets = (asset,)
        self.name = f"sma_cross_{fast}_{slow}"

    def allocation(self, ctx):
        x = ctx.close(self.asset)
        f, s = sma(x, self.fast), sma(x, self.slow)
        if np.isnan(s):
            return None
        return {self.asset: 1.0} if f > s else {}


class DualMomentum(Allocator):
    """SPY if its lookback return beats T-bills and IEF; otherwise IEF if IEF beats T-bills, else cash."""

    frequency = "monthly"

    def __init__(self, lookback_months: int = 12):
        self.n = lookback_months
        self.assets = (SPY, IEF)
        self.name = f"dual_momentum_{lookback_months}m"

    def allocation(self, ctx):
        me = month_end_positions(ctx)
        if len(me) < self.n + 1:
            return None
        a, b = me[-self.n - 1], me[-1]
        spy, ief = ctx.close(SPY), ctx.close(IEF)
        if np.isnan(ief[a]) or np.isnan(spy[a]):
            return None
        r_spy, r_ief = spy[b] / spy[a] - 1, ief[b] / ief[a] - 1
        rf = np.nan_to_num(ctx.rf()[a:b])
        days = (ctx.sessions[a + 1 : b + 1] - ctx.sessions[a:b]).days.to_numpy()
        r_bill = float(np.prod(1 + rf * days / 365) - 1)
        if r_spy > max(r_bill, r_ief):
            return {SPY: 1.0}
        return {IEF: 1.0} if r_ief > r_bill else {}


class SectorRotation(Allocator):
    """Monthly: equal weight the top ``k`` sector ETFs by 12-1 month return (only ETFs that existed then).

    ``reversal=True`` holds the ``k`` worst performers instead (short-term reversal), always fully invested.
    """

    frequency = "monthly"

    def __init__(self, k: int = 3, lookback: int = 12, skip: int = 1, universe=SECTORS,
                 reversal: bool = False):  # fmt: skip
        self.k, self.lookback, self.skip, self.reversal = k, lookback, skip, reversal
        self.assets = tuple(universe)
        side = "bottom" if reversal else "top"
        self.name = f"sector_{side}{k}_{lookback}-{skip}"

    def scores(self, ctx) -> dict[int, float]:
        me = month_end_positions(ctx)
        if len(me) < self.lookback + 1:
            return {}
        a, b = me[-self.lookback - 1], me[-1 - self.skip]
        out = {}
        for p in self.assets:
            x = ctx.close(p)
            if not (np.isnan(x[a]) or np.isnan(x[b])) and ctx.tradable(p):
                out[p] = x[b] / x[a] - 1
        return out

    def allocation(self, ctx):
        sc = self.scores(ctx)
        if len(sc) < self.k:
            return None
        top = sorted(sc, key=sc.get, reverse=not self.reversal)[: self.k]
        return {p: 1.0 / self.k for p in top}


class VolTarget(Allocator):
    """Scale exposure to ``target`` annualized vol using ``window``-day realized vol, capped at 100%.

    Re-trades when the desired weight moves more than ``band`` from the last traded weight.
    """

    def __init__(
        self, asset: int = SPY, target: float = 0.15, window: int = 21, band: float = 0.10
    ):
        self.asset, self.target, self.window, self.band = asset, target, window, band
        self.assets = (asset,)
        self.name = f"vol_target_{int(target * 100)}_{window}d"

    def allocation(self, ctx):
        x = ctx.close(self.asset)
        if len(x) < self.window + 1 or np.isnan(x[-self.window - 1 :]).any():
            return None
        r = np.diff(np.log(x[-self.window - 1 :]))
        vol = r.std(ddof=1) * np.sqrt(252)
        w = 1.0 if vol <= 0 else min(self.target / vol, 1.0)
        return {self.asset: w}


class RSI2(Allocator):
    """Enter when RSI(2) < ``entry``; exit when RSI(2) > ``exit_rsi`` or close > 5-day SMA. Cash otherwise."""

    def __init__(
        self, asset: int = SPY, entry: float = 10, exit_rsi: float = 70, exit_sma: int = 5
    ):
        self.asset, self.entry, self.exit_rsi, self.exit_sma = asset, entry, exit_rsi, exit_sma
        self.assets = (asset,)
        self.name = f"rsi2_{int(entry)}_{int(exit_rsi)}"

    def allocation(self, ctx):
        x = ctx.close(self.asset)
        r = rsi(x, 2)
        if np.isnan(r):
            return None
        holding = bool(self.current)
        if not holding:
            return {self.asset: 1.0} if r < self.entry else {}
        if r > self.exit_rsi or x[-1] > sma(x, self.exit_sma):
            return {}
        return {self.asset: 1.0}


class PriceVsSMA(Allocator):
    """Daily: hold the asset while its close is above its ``n``-day simple moving average, else cash
    (T-bills via the engine's cash yield). Signal at t's close, trade at t+1's open."""

    def __init__(self, asset: int = SPY, n: int = 200):
        self.asset, self.n = asset, n
        self.assets = (asset,)
        self.name = f"above_sma{n}d"

    def allocation(self, ctx):
        x = ctx.close(self.asset)
        s = sma(x, self.n)
        if np.isnan(s):
            return None
        return {self.asset: 1.0} if x[-1] > s else {}


class AssetMomentum(SectorRotation):
    """Multi-asset relative momentum: equal weight the top ``k`` assets by ``lookback``-month total return
    (no skip month). With ``absolute=True`` an asset is only held if its return beat T-bills over the same
    window; otherwise its share stays in cash."""

    def __init__(
        self, assets, k: int = 1, lookback: int = 12, absolute: bool = False, name: str = ""
    ):
        super().__init__(k=k, lookback=lookback, skip=0, universe=assets)
        self.absolute = absolute
        self.name = name or f"asset_mom_top{k}_{lookback}m" + ("_abs" if absolute else "")

    def allocation(self, ctx):
        sc = self.scores(ctx)
        if len(sc) < len(self.assets):  # wait until every asset has a full lookback
            return None
        top = sorted(sc, key=sc.get, reverse=True)[: self.k]
        if self.absolute:
            me = month_end_positions(ctx)
            a, b = me[-self.lookback - 1], me[-1]
            rf = np.nan_to_num(ctx.rf()[a:b])
            days = (ctx.sessions[a + 1 : b + 1] - ctx.sessions[a:b]).days.to_numpy()
            bill = float(np.prod(1 + rf * days / 365) - 1)
            top = [p for p in top if sc[p] > bill]
        return {p: 1.0 / self.k for p in top}
