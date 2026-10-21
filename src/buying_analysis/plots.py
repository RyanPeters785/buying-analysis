"""Static PNG charts for the report (matplotlib, light theme).

Colors follow the reference palette: categorical slots in fixed order for strategies, neutral ink for the
SPY benchmark, recessive grid. At most four strategies per chart, one y-axis, direct end labels.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.dates
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6"]  # blue, orange, aqua, violet (slots 1,2,3,7)
BENCH = "#52514e"  # text-secondary ink: the benchmark is the reference, not a competitor
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#76756f", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "lines.linewidth": 2.0, "legend.frameon": False,
})  # fmt: skip


def _end_labels(ax, series: dict[str, pd.Series], colors: dict[str, str], fmt=None) -> None:
    """Direct labels at the right end of each line, nudged apart in screen space (works on log axes too);
    text in ink, not series color."""
    to_axes = ax.transAxes.inverted()
    ends = []
    for name, s in series.items():
        s = s.dropna()
        _, fy = to_axes.transform(
            ax.transData.transform((matplotlib.dates.date2num(s.index[-1]), s.iloc[-1]))
        )
        ends.append((fy, s.iloc[-1], name))
    ends.sort(reverse=True)
    gap = 0.05
    placed: list[float] = []
    for fy, y, name in ends:
        yy = fy if not placed else min(fy, placed[-1] - gap)
        placed.append(yy)
        label = name if fmt is None else f"{name}  {fmt(y)}"
        ax.annotate(label, (1.0, yy), xycoords="axes fraction", xytext=(14, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)  # fmt: skip
        ax.plot(
            [1.0], [fy], marker="o", ms=4, color=colors[name], transform=ax.transAxes, clip_on=False
        )
        if abs(yy - fy) > 1e-6:  # leader from the line end to its nudged label
            ax.plot(
                [1.0, 1.012], [fy, yy], color=MUTED, lw=0.8, transform=ax.transAxes, clip_on=False
            )


def _colors(names, bench: str | None) -> dict[str, str]:
    out, k = {}, 0
    for n in names:
        if n == bench:
            out[n] = BENCH
        else:
            out[n] = SERIES[k % len(SERIES)]
            k += 1
    return out


def line_chart(series: dict[str, pd.Series], title: str, ylabel: str, path: Path, bench: str | None = None,
               log: bool = False, fmt=None, zero_line: bool = False, end_labels: bool = True,
               month_axis: bool = False) -> Path:  # fmt: skip
    if len([n for n in series if n != bench]) > 4:
        raise ValueError("at most four strategies per chart (plus the benchmark)")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = _colors(series, bench)
    for name, s in series.items():
        ax.plot(s.index, s.values, color=colors[name], lw=2.0 if name != bench else 1.6,
                ls="-" if name != bench else (0, (4, 2)), label=name)  # fmt: skip
    if log:
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1, 2, 5)))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    if fmt is not None:
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    if zero_line:
        ax.axhline(0, color=MUTED, lw=1)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", ncol=min(len(series), 3), fontsize=9)
    if month_axis:  # x is a dummy year: label months only
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator())
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    if end_labels:
        fig.subplots_adjust(right=0.78)
        _end_labels(ax, series, colors, fmt)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def hist_panels(values: dict[str, np.ndarray], markers: dict[str, float], title: str, xlabel: str,
                path: Path, ncols: int = 3, marker_label: str = "strategy",
                xlim: tuple[float, float] | None = None) -> Path:  # fmt: skip
    """Small multiples: one histogram per panel (single neutral fill) with the strategy's value marked."""
    n = len(values)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.6 * ncols, 2.6 * nrows), squeeze=False,
                             sharex=xlim is not None)  # fmt: skip
    bins = np.linspace(*xlim, 41) if xlim else 30
    for ax, (name, v) in zip(axes.flat, values.items()):
        v = np.clip(v, *xlim) if xlim else v  # tails beyond the range pile into the edge bins
        ax.hist(v, bins=bins, color="#c3c2b7", edgecolor=SURFACE, linewidth=1)
        if name in markers and np.isfinite(markers[name]):
            ax.axvline(markers[name], color=SERIES[0], lw=2)
            pct = (np.asarray(v) < markers[name]).mean() * 100
            ax.text(0.98, 0.92, f"{marker_label}: {pct:.0f}th pct", transform=ax.transAxes,
                    ha="right", va="top", fontsize=8, color=INK)  # fmt: skip
        ax.set_title(name, fontsize=10)
        ax.set_yticks([])
        ax.grid(axis="y", visible=False)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    fig.supxlabel(xlabel, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def strip_chart(df: pd.DataFrame, x: str, y: str, title: str, xlabel: str, path: Path) -> Path:
    """Horizontal strip + median per category (rows = strategies), zero reference line."""
    cats = list(df.groupby(y)[x].median().sort_values().index)
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(cats) + 1.4))
    rng = np.random.default_rng(0)
    for i, c in enumerate(cats):
        v = df.loc[df[y] == c, x].to_numpy()
        ax.scatter(v, i + rng.uniform(-0.18, 0.18, len(v)), s=10, color=SERIES[0], alpha=0.35, lw=0)
        ax.plot([np.median(v)] * 2, [i - 0.3, i + 0.3], color=INK, lw=2)
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(range(len(cats)), cats)
    ax.grid(axis="y", visible=False)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def grouped_bars(df: pd.DataFrame, err: pd.DataFrame | None, title: str, ylabel: str, path: Path,
                 fmt=None) -> Path:  # fmt: skip
    """Grouped bars: rows = categories (x axis), columns = series (<= 4, fixed palette order), optional
    95% CI half-widths in ``err`` (same shape). Zero baseline; one y-axis."""
    if df.shape[1] > 4:
        raise ValueError("at most four series")
    n, k = df.shape
    width = 0.8 / k
    x = np.arange(n)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for j, col in enumerate(df.columns):
        pos = x - 0.4 + width * (j + 0.5)
        ax.bar(pos, df[col].to_numpy(), width=width * 0.92, color=SERIES[j], label=col, zorder=2)
        if err is not None:
            ax.errorbar(pos, df[col].to_numpy(), yerr=err[col].to_numpy(), fmt="none", ecolor=INK,
                        elinewidth=1, capsize=2, zorder=3)  # fmt: skip
    ax.axhline(0, color=MUTED, lw=1, zorder=1)
    ax.set_xticks(x, df.index)
    ax.grid(axis="x", visible=False)
    if fmt is not None:
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    if k > 1:
        ax.legend(loc="upper left", ncol=k, fontsize=9)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _month_bands(ax) -> None:
    """Alternate light bands per month on a dummy-year (2001) date axis, month names centred."""
    for m in range(1, 13):
        a = pd.Timestamp(2001, m, 1)
        b = a + pd.offsets.MonthBegin(1)
        if m % 2 == 0:
            ax.axvspan(a, b, color=GRID, alpha=0.45, lw=0, zorder=0)
    ax.set_xlim(pd.Timestamp(2001, 1, 1), pd.Timestamp(2002, 1, 1))
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonthday=15))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
    ax.xaxis.set_minor_locator(matplotlib.dates.MonthLocator())
    ax.tick_params(axis="x", which="major", length=0)
    ax.grid(axis="x", visible=False)


def daily_seasonal(points: pd.Series | None, lines: dict[str, pd.Series], bands: dict[str, pd.Series],
                   title: str, ylabel: str, path: Path, fmt=None) -> Path:  # fmt: skip
    """365-day view on a dummy year: optional grey dots (one per calendar day), up to four smoothed lines
    with optional +/- band half-widths, alternating month shading."""
    fig, ax = plt.subplots(figsize=(12, 5))
    _month_bands(ax)
    if points is not None:
        ax.scatter(
            points.index,
            points.values,
            s=9,
            color="#b0afa8",
            lw=0,
            zorder=1,
            label="single calendar day",
        )
    for k, (name, s) in enumerate(lines.items()):
        c = SERIES[k]
        if name in bands:
            ax.fill_between(
                s.index, s - bands[name], s + bands[name], color=c, alpha=0.15, lw=0, zorder=2
            )
        ax.plot(s.index, s.values, color=c, lw=2.2, label=name, zorder=3)
    ax.axhline(0, color=MUTED, lw=1, zorder=1)
    if fmt is not None:
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", ncol=len(lines) + 1, fontsize=9)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def daily_path(lines: dict[str, pd.Series], title: str, ylabel: str, path: Path, fmt=None) -> Path:
    """Detrended path through the year (dummy-year dates) with month shading."""
    return daily_seasonal(None, lines, {}, title, ylabel, path, fmt)


def valuation_scatter(panels: dict[str, pd.DataFrame], latest: dict[str, float], title: str, ylabel: str,
                      path: Path) -> Path:  # fmt: skip
    """Side-by-side scatter panels (shared y). Each panel frame has columns x, y, group (<= 4 groups, fixed
    palette order) and fit (fitted y, sorted by x). ``latest`` marks today's x with a vertical line."""
    fig, axes = plt.subplots(
        1, len(panels), figsize=(6.2 * len(panels), 5.2), sharey=True, squeeze=False
    )
    groups = list(dict.fromkeys(g for df in panels.values() for g in df["group"]))
    for ax, (name, df) in zip(axes.flat, panels.items()):
        for k, g in enumerate(groups):
            d = df[df["group"] == g]
            ax.scatter(d["x"], d["y"], s=10, color=SERIES[k], alpha=0.55, lw=0, label=g, zorder=2)
        f = df.sort_values("x")
        ax.plot(f["x"], f["fit"], color=INK, lw=2, zorder=3, label="trend")
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1, 2, 3, 5)))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.axhline(0, color=MUTED, lw=1)
        if name in latest:
            ax.axvline(latest[name], color=INK, lw=1.5, ls=(0, (4, 2)), zorder=1)
            ax.annotate(f"latest {latest[name]:.0f}", (latest[name], 1.0), xycoords=("data", "axes fraction"),
                        xytext=(4, -12), textcoords="offset points", fontsize=9, color=INK)  # fmt: skip
        ax.set_title(name, fontsize=11)
        ax.set_xlabel(name.split(" (")[0])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    axes.flat[0].set_ylabel(ylabel)
    axes.flat[0].legend(loc="lower left", fontsize=8, ncol=1)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def heatmap(grid: pd.DataFrame, title: str, xlabel: str, ylabel: str, path: Path, fmt=None,
            cbar_label: str = "") -> Path:  # fmt: skip
    """Annotated grid with a diverging map (red = negative, neutral grey at 0, blue = positive)."""
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

    cmap = LinearSegmentedColormap.from_list("div", ["#e34948", "#f0efec", "#2a78d6"])
    v = np.nanmax(np.abs(grid.to_numpy()))
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    im = ax.imshow(grid.to_numpy(), cmap=cmap, norm=TwoSlopeNorm(0, -v, v), origin="lower")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            val = grid.iat[i, j]
            ax.text(
                j,
                i,
                fmt(val) if fmt else f"{val:.1f}",
                ha="center",
                va="center",
                fontsize=10,
                color=INK,
            )
    ax.set_xticks(range(grid.shape[1]), grid.columns)
    ax.set_yticks(range(grid.shape[0]), grid.index)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label(cbar_label)
    cb.outline.set_visible(False)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
