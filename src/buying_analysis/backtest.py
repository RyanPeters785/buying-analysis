"""Daily backtest engine for long-only target-weight strategies in an IRA cash account.

Timeline of each session t:
  morning  cash accrues the money-market yield since t-1; T+1 sale proceeds settle; deposits land;
           positions in delisted assets convert to cash at their last value
  open     pending orders (decided at t-1's close) execute: sells first, then buys with settled cash only
  close    positions are marked to market; the strategy sees data through t and may set a new target

Prices are total-return indexes built from CRSP ``ret`` (dividends reinvested, splits handled), so a unit of
an asset is worth ``close_idx`` at the close and ``open_idx`` at the open. Strategies never see a row after t:
``Context`` only exposes slices ``[: t + 1]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from buying_analysis import data
from buying_analysis.costs import CostModel

Weights = dict[int, float]  # permno -> fraction of equity; cash is the remainder


# --- Market data -----------------------------------------------------------------------------------------


@dataclass
class MarketData:
    sessions: pd.DatetimeIndex
    permnos: np.ndarray
    close_idx: np.ndarray  # T x N total-return index at the close (NaN when not listed)
    open_idx: np.ndarray  # T x N same units at the open (close_idx when the open is missing)
    open_px: np.ndarray  # T x N raw open price (for share counts)
    tradable: np.ndarray  # T x N bool: listed and not a delisting row
    is_etf: np.ndarray  # N bool
    rf: np.ndarray  # T annualized T-bill yield known at each close (NaN before the first release)
    days: np.ndarray  # T calendar days since the previous session
    tickers: dict[int, str]

    @classmethod
    def load(
        cls, permnos=None, start=None, end=None, prices: pd.DataFrame | None = None
    ) -> MarketData:
        p = data.load_prices() if prices is None else prices
        if permnos is not None:
            p = p[p["permno"].isin(list(permnos))]
        sessions_all = pd.DatetimeIndex(sorted(p["session"].unique()))
        rf = (
            data.rf_daily(p).reindex(sessions_all)
            if prices is None
            else _flat_rf(prices, sessions_all)
        )
        close = data.total_return_index(p)
        w = lambda c: data.wide(p, c).reindex(index=close.index, columns=close.columns)
        ratio = (w("open") / w("prc")).where(lambda x: x > 0)
        open_idx = (close * ratio).fillna(close)
        status = p.pivot(index="session", columns="permno", values="tradingstatusflg").reindex_like(
            close
        )
        tradable = close.notna() & status.astype(object).ne("D").fillna(True).astype(bool)
        etf = (
            p.groupby("permno")["securitytype"]
            .agg(lambda s: (s == "FUND").any())
            .reindex(close.columns)
        )
        mask = np.ones(len(close), bool)
        if start is not None:
            mask &= close.index >= pd.Timestamp(start)
        if end is not None:
            mask &= close.index <= pd.Timestamp(end)
        idx = close.index[mask]
        days = np.r_[1, np.diff(close.index.values).astype("timedelta64[D]").astype(int)][mask]
        return cls(
            sessions=idx,
            permnos=close.columns.to_numpy(),
            close_idx=close.to_numpy()[mask],
            open_idx=open_idx.to_numpy()[mask],
            open_px=w("open").fillna(w("prc")).to_numpy()[mask],
            tradable=tradable.to_numpy(bool)[mask],
            is_etf=etf.fillna(False).to_numpy(bool),
            rf=rf.reindex(idx).to_numpy(float),
            days=days,
            tickers=data.tickers(p).to_dict(),
        )

    def col(self, permno: int) -> int:
        return int(np.flatnonzero(self.permnos == permno)[0])

    def first_session(self, permnos) -> pd.Timestamp:
        """First session on which all ``permnos`` are tradable."""
        cols = [self.col(p) for p in permnos]
        ok = self.tradable[:, cols].all(axis=1)
        return self.sessions[int(np.argmax(ok))]


def _flat_rf(prices: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.Series:
    """Synthetic panels (tests) carry their own ``rf`` column or default to 0."""
    if "rf" in prices:
        return prices.groupby("session")["rf"].first().reindex(sessions)
    return pd.Series(0.0, index=sessions)


# --- Contribution schedule -------------------------------------------------------------------------------


def contribution_schedule(
    sessions: pd.DatetimeIndex, amount: float, frequency: str, total=None, start=None, end=None
) -> pd.Series:
    """Deposits on the first session of each period within [start, end]; the first session always gets one.

    ``once`` puts ``total`` (or ``amount``) on the first session.
    """
    if start is not None:
        sessions = sessions[sessions >= pd.Timestamp(start)]
    if end is not None:
        sessions = sessions[sessions <= pd.Timestamp(end)]
    if frequency == "once":
        return pd.Series([amount if total is None else total], index=sessions[:1])
    key = {"annual": sessions.year, "monthly": sessions.year * 100 + sessions.month,
           "weekly": sessions.to_period("W").astype(str)}[frequency]  # fmt: skip
    first = ~pd.Index(key).duplicated()
    return pd.Series(amount, index=sessions[first])


def period_starts(sessions: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    return contribution_schedule(sessions, 1.0, frequency).index


# --- Strategy interface ----------------------------------------------------------------------------------


class Context:
    """What a strategy can see at session t's close: history through t and its own portfolio."""

    def __init__(self, md: MarketData, i: int, port: Portfolio, deposits: pd.Series):
        self._md, self.i, self.port, self.deposits = md, i, port, deposits
        self.date = md.sessions[i]
        self.sessions = md.sessions[: i + 1]

    def close(self, permno: int) -> np.ndarray:
        """Total-return index history of ``permno`` through t (NaN before listing)."""
        return self._md.close_idx[: self.i + 1, self._md.col(permno)]

    def open(self, permno: int) -> np.ndarray:
        """Open-price total-return index through t (today's open is known at today's close)."""
        return self._md.open_idx[: self.i + 1, self._md.col(permno)]

    def rf(self) -> np.ndarray:
        return self._md.rf[: self.i + 1]

    def tradable(self, permno: int) -> bool:
        return bool(self._md.tradable[self.i, self._md.col(permno)])

    @property
    def equity(self) -> float:
        return self.port.equity

    @property
    def cash(self) -> float:
        return self.port.cash

    def weight(self, permno: int) -> float:
        return (
            self.port.values[self._md.col(permno)] / self.port.equity
            if self.port.equity > 0
            else 0.0
        )

    def weights(self) -> Weights:
        e = self.port.equity
        return (
            {int(p): v / e for p, v in zip(self._md.permnos, self.port.values) if v > 0}
            if e > 0
            else {}
        )

    def deposit_today(self) -> bool:
        return self.date in self.deposits.index


class Strategy:
    """Subclass and implement ``decide``; return target weights to trade at the next open, or None to hold."""

    name = "strategy"
    assets: tuple[int, ...] = ()

    def reset(self) -> None:  # called before each run
        pass

    def decide(self, ctx: Context) -> Weights | None:
        raise NotImplementedError


# --- Portfolio and engine --------------------------------------------------------------------------------


@dataclass
class Portfolio:
    units: np.ndarray
    values: np.ndarray
    settled: float = 0.0
    unsettled: float = 0.0
    equity: float = 0.0

    @property
    def cash(self) -> float:
        return self.settled + self.unsettled


@dataclass
class Result:
    name: str
    daily: pd.DataFrame  # equity, cash, invested, deposit, costs, twr_ret, rf
    trades: pd.DataFrame
    weights: pd.DataFrame  # end-of-day weights per asset
    meta: dict = field(default_factory=dict)


@dataclass
class Engine:
    md: MarketData
    costs: CostModel = field(default_factory=CostModel)
    fractional: bool = True
    min_trade: float = 1.0

    def run(self, strategy: Strategy, deposits: pd.Series, start=None, end=None) -> Result:
        md = self.md
        lo = 0 if start is None else int(md.sessions.searchsorted(pd.Timestamp(start)))
        hi = (
            len(md.sessions)
            if end is None
            else int(md.sessions.searchsorted(pd.Timestamp(end), "right"))
        )
        n = md.close_idx.shape[1]
        port = Portfolio(units=np.zeros(n), values=np.zeros(n))
        spread = self.costs.spreads(md.is_etf)
        deposits = deposits[
            (deposits.index >= md.sessions[lo]) & (deposits.index <= md.sessions[hi - 1])
        ]
        dep_at = {md.sessions.get_loc(d): float(a) for d, a in deposits.items()}
        strategy.reset()
        pending: Weights | None = None
        buys_only = False
        rows, trades, wts = [], [], []
        prev_equity = 0.0
        for i in range(lo, hi):
            cost_today = 0.0
            # morning: interest, settlement, deposits, delistings
            if i > lo:
                g = self.costs.cash_growth(md.rf[i - 1], int(md.days[i]))
                port.settled *= g
                port.unsettled *= g
            port.settled += port.unsettled
            port.unsettled = 0.0
            dep = dep_at.get(i, 0.0)
            port.settled += dep
            gone = (port.units > 0) & np.isnan(md.close_idx[i])
            for c in np.flatnonzero(gone):  # delisted overnight: cash at last close value
                port.settled += port.values[c]
                trades.append(self._trade(i, c, "delist", port.values[c], 0.0))
                port.units[c] = port.values[c] = 0.0
            # open: execute
            if pending is not None:
                cost_today, done, tl = self._execute(i, port, pending, spread, buys_only)
                trades += tl
                pending, buys_only = (None, False) if done else (pending, True)
            # close: mark, record, decide
            px = np.nan_to_num(md.close_idx[i])
            port.values = port.units * px
            port.equity = port.cash + port.values.sum()
            base = prev_equity + dep
            twr = port.equity / base - 1.0 if base > 0 else 0.0
            prev_equity = port.equity
            rows.append(
                (
                    md.sessions[i],
                    port.equity,
                    port.cash,
                    port.values.sum(),
                    dep,
                    cost_today,
                    twr,
                    md.rf[i],
                )
            )
            wts.append(port.values / port.equity if port.equity > 0 else np.zeros(n))
            target = strategy.decide(Context(md, i, port, deposits))
            if target is not None:
                pending, buys_only = self._clean(target, i), False
        daily = pd.DataFrame(
            rows,
            columns=["session", "equity", "cash", "invested", "deposit", "costs", "twr_ret", "rf"],
        )
        daily = daily.set_index("session")
        tr = pd.DataFrame(trades, columns=["session", "permno", "side", "value", "cost"])
        w = pd.DataFrame(wts, index=daily.index, columns=md.permnos)
        w = w.loc[:, (w > 0).any()]
        return Result(strategy.name, daily, tr, w, {"strategy": strategy.name})

    def _clean(self, target: Weights, i: int) -> Weights:
        tot = sum(max(v, 0.0) for v in target.values())
        if tot > 1.0 + 1e-9:
            raise ValueError(f"target weights sum to {tot:.4f} > 1 (no leverage)")
        return {int(p): float(v) for p, v in target.items() if v > 0}

    def _execute(self, i, port: Portfolio, target: Weights, spread, buys_only: bool):
        md, cm = self.md, self.costs
        price = md.open_idx[i]
        held_val = port.units * np.nan_to_num(price)
        equity = port.cash + held_val.sum()
        want = np.zeros_like(held_val)
        for p, w in target.items():
            want[md.col(p)] = w * equity
        delta = want - held_val
        cost, trades = 0.0, []
        if not buys_only:
            for c in np.flatnonzero((delta < -self.min_trade) & md.tradable[i]):
                val = -delta[c]
                shares = val / md.open_px[i, c]
                if not self.fractional:
                    shares = np.floor(shares)
                    val = shares * md.open_px[i, c]
                    if val <= 0:
                        continue
                if (
                    port.units[c] * price[c] - val < self.min_trade
                ):  # selling out: take the whole position
                    val = port.units[c] * price[c]
                    port.units[c] = 0.0
                else:
                    port.units[c] -= val / price[c]
                c_cost = val * spread[c] + cm.sell_fees(val, shares) + cm.commission
                port.unsettled += val - c_cost
                cost += c_cost
                trades.append(self._trade(i, c, "sell", val, c_cost))
        buy = np.flatnonzero((delta > self.min_trade) & md.tradable[i])
        need = sum(delta[c] * (1 + spread[c]) + cm.commission for c in buy)
        tol = 1e-9 * max(1.0, need)  # float noise on large balances
        scale = 1.0 if need <= port.settled + tol else max(port.settled, 0.0) / need
        for c in buy:
            val = delta[c] * scale
            if not self.fractional:
                shares = np.floor(val / (md.open_px[i, c] * (1 + spread[c])))
                val = shares * md.open_px[i, c]
            if val < self.min_trade:
                continue
            c_cost = val * spread[c] + cm.commission
            port.units[c] += val / price[c]
            port.settled -= val + c_cost
            cost += c_cost
            trades.append(self._trade(i, c, "buy", val, c_cost))
        if -tol < port.settled < 0:
            port.settled = 0.0
        done = scale >= 1.0 - 1e-9
        return cost, done, trades

    def _trade(self, i, c, side, val, cost):
        return (self.md.sessions[i], int(self.md.permnos[c]), side, float(val), float(cost))
