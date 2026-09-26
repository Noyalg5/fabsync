"""Charts for the management pack, drawn to the same design rules as the app.

Every chart is saved at 300 dpi. Colours carry the same meaning as in the app: the accent for a single
measure, the fixed system colours wherever systems are compared, grey for anything secondary, and a dashed
ink line for a target. Values are labelled at the bar end instead of through a legend, axes carry their
units, money is in pounds with thousands separators, and there are no pies, dual axes or 3D effects.
Each image also carries its title and the synthetic data statement, so it can stand alone on a slide.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from fabsync.palette import ACCENT, GRID, INK, MUTED, RULE  # noqa: E402
from fabsync.provenance import quote  # noqa: E402

DPI = 300
WIDTH = 170 / 25.4                      # inches: the text width of an A4 page with 20 mm margins
SYNTHETIC = "Demonstration prototype. All data is synthetic."
STYLE = {
    "font.family": "DejaVu Sans", "font.size": 7.5, "text.color": INK, "axes.labelcolor": INK,
    "axes.edgecolor": RULE, "axes.linewidth": 0.6, "xtick.color": RULE, "ytick.color": RULE,
    "xtick.labelcolor": INK, "ytick.labelcolor": INK, "xtick.labelsize": 7, "ytick.labelsize": 7.5,
    "axes.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.facecolor": "white",
    "figure.facecolor": "white", "axes.facecolor": "white", "hatch.color": MUTED, "hatch.linewidth": 0.5,
}
TITLE_H, FOOT_H = 0.34, 0.22            # inches reserved above and below the plot


def gbp(v: float) -> str:
    return f"-£{-v:,.0f}" if v < 0 else f"£{v:,.0f}"


def gbp_axis(v: float) -> str:
    """Compact pounds for axis ticks: £0, £20k, £1.5m."""
    sign, a = ("-" if v < 0 else ""), abs(v)
    if a >= 1_000_000:
        return f"{sign}£{a / 1_000_000:.1f}m"
    return f"{sign}£{a / 1_000:,.0f}k" if a >= 1_000 else f"{sign}£{a:,.0f}"


def wrap(text: str, width: int = 95) -> str:
    return "\n".join(textwrap.wrap(text, width))


def save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, metadata={"Software": None})
    plt.close(fig)
    return path


def frame(height: float, title: str, left: float, right: float = 0.25, bottom: float = 0.42) -> tuple[Figure, object]:
    """A figure of the page width with the title above the plot and the synthetic data statement below."""
    fig = plt.figure(figsize=(WIDTH, height))
    fig.text(0.1 / WIDTH, 1 - 0.08 / height, title, fontsize=8.5, fontweight="bold", va="top", color=INK)
    fig.text(0.1 / WIDTH, 0.05 / height, SYNTHETIC, fontsize=5.5, color=MUTED, va="bottom")
    ax = fig.add_axes([left / WIDTH, (bottom + FOOT_H * 0) / height, 1 - (left + right) / WIDTH,
                       1 - (bottom + TITLE_H) / height])
    return fig, ax


def _value_axis(ax, money: bool, bounds: tuple[float, float] | None) -> None:
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: gbp_axis(v) if money else f"{v:,.0f}"))
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=4)
    ax.tick_params(axis="x", length=2, width=0.6)
    if bounds:
        ax.spines["bottom"].set_bounds(*bounds)


def bar_h(title: str, categories: Sequence[str], values: Sequence[float], labels: Sequence[str], x_title: str,
          colours: Sequence[str] | None = None, target: float | None = None, money: bool = False,
          x_max: float | None = None, row: float = 0.24) -> Figure:
    """Horizontal bars in the order given, top to bottom, each labelled at its end; negative bars run left."""
    with plt.rc_context(STYLE):
        n = len(categories)
        left = 0.15 + 0.056 * max(len(c) for c in categories)
        x_title = wrap(x_title, int((WIDTH - left - 0.25) * 72 / (7.5 * 0.56)))
        extra = 0.12 * x_title.count("\n")
        fig, ax = frame(TITLE_H + 0.42 + extra + row * n + 0.1, title, left, bottom=0.42 + extra)
        ys = list(range(n))[::-1]
        ax.barh(ys, values, height=0.64, color=list(colours) if colours else ACCENT, linewidth=0)
        lo, hi = min(0.0, min(values)), max(0.0, max(values))
        span = (x_max or hi) - lo
        pad = 0.012 * span
        for y, v, label in zip(ys, values, labels, strict=True):
            ax.text(v + (pad if v >= 0 else -pad), y, label, va="center", ha="left" if v >= 0 else "right",
                    fontsize=7, color=INK, zorder=4,
                    bbox={"boxstyle": "square,pad=0.1", "facecolor": "white", "edgecolor": "none"})
        room = 0.34 * span
        ax.set_xlim(lo - (room if lo < 0 else 0), (x_max or hi) + room)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_yticks(ys, list(categories))
        ax.set_xlabel(x_title)
        _value_axis(ax, money, (lo, x_max or hi) if x_max else None)
        if x_max:
            ax.set_xticks([t for t in ax.get_xticks() if lo <= t <= x_max])
        if lo < 0:
            ax.axvline(0, color=RULE, linewidth=0.6)
        if target is not None:
            ax.axvline(target, color=INK, linewidth=0.8, linestyle=(0, (4, 3)), zorder=3)
        return fig


def timeline(title: str, rows: dict[str, list[str]]) -> Figure:
    """The rollout plan: phases as accent bars, dual running as grey bars, reviews as ink diamonds."""
    with plt.rc_context(STYLE):
        names = [name for name in rows if name != "Quarter"]
        n = len(names)
        left = 0.15 + 0.052 * max(len(c) for c in names)
        fig, ax = frame(TITLE_H + 0.45 + 0.24 * n, title, left, right=0.15)
        ys = list(range(n))[::-1]
        for y, name in zip(ys, names, strict=True):
            cells = rows[name]
            for month, cell in enumerate(cells, start=1):
                if cell == "■":
                    ax.add_patch(Rectangle((month - 1, y - 0.32), 1, 0.64, color=ACCENT, linewidth=0))
                elif cell == "▒":
                    ax.add_patch(Rectangle((month - 1, y - 0.32), 1, 0.64, facecolor=MUTED, linewidth=0))
                elif cell == "◆":
                    ax.plot([month - 0.5], [y], marker="D", markersize=5.5, color=INK, linestyle="none")
        for q in range(0, 19, 3):
            ax.axvline(q, color=GRID, linewidth=0.8, zorder=0)
        ax.set_xlim(0, 18)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_xticks([m - 0.5 for m in range(1, 19)], [str(m) for m in range(1, 19)])
        ax.set_yticks(ys, names)
        ax.set_xlabel("Month from mobilisation")
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0, pad=4)
        ax.tick_params(axis="x", length=0)
        return fig


BANDS = [(4, "low", 0.10), (9, "medium", 0.28), (14, "high", 0.55), (25, "very high", 0.85)]


def band(score: int) -> tuple[str, float]:
    return next((name, alpha) for top, name, alpha in BANDS if score <= top)


def heat_maps(title: str, risks: list[dict]) -> Figure:
    """Two 5 x 5 grids, before and after mitigation; shading darkens with likelihood times impact."""
    with plt.rc_context(STYLE):
        height, w, gap, left, bottom, top = 3.25, 2.3, 0.5, 0.95, 0.95, 0.62
        fig = plt.figure(figsize=(WIDTH, height))
        fig.text(0.1 / WIDTH, 1 - 0.08 / height, title, fontsize=8.5, fontweight="bold", va="top")
        fig.text(0.1 / WIDTH, 0.05 / height, SYNTHETIC, fontsize=5.5, color=MUTED, va="bottom")
        panels = [("Before mitigation (inherent)", "likelihood", "impact"),
                  ("After mitigation (residual)", "residual_likelihood", "residual_impact")]
        for k, (name, lk, ik) in enumerate(panels):
            ax = fig.add_axes([(left + k * (w + gap)) / WIDTH, bottom / height, w / WIDTH,
                               (height - bottom - top) / height])
            for li in range(1, 6):
                for ii in range(1, 6):
                    ax.add_patch(Rectangle((li - 0.5, ii - 0.5), 1, 1, facecolor=ACCENT, alpha=band(li * ii)[1],
                                           edgecolor="white", linewidth=1.2))
            cells: dict[tuple[int, int], list[str]] = {}
            for r in risks:
                cells.setdefault((r[lk], r[ik]), []).append(r["id"])
            for (li, ii), ids in cells.items():
                text = "\n".join(", ".join(ids[j:j + 2]) for j in range(0, len(ids), 2))
                ax.text(li, ii, text, ha="center", va="center", fontsize=5.8, linespacing=1.1,
                        color="white" if band(li * ii)[1] > 0.5 else INK)
            ax.set_xlim(0.5, 5.5)
            ax.set_ylim(0.5, 5.5)
            ax.set_xticks(range(1, 6), ["1\nrare", "2", "3", "4", "5\nalmost\ncertain"])
            ax.set_yticks(range(1, 6), ["1 negligible", "2", "3", "4", "5 severe"] if k == 0 else [""] * 5)
            ax.set_title(name, fontsize=7.5, color=INK, pad=4)
            ax.set_xlabel("Likelihood", labelpad=2)
            if k == 0:
                ax.set_ylabel("Impact")
            ax.tick_params(length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
        x, y = 2.3, 0.2
        fig.text(x / WIDTH, (y + 0.08) / height, "Shading shows the score, likelihood × impact:", fontsize=6.3,
                 va="center", ha="right")
        for j, (hi, name, alpha) in enumerate(BANDS):
            lo = BANDS[j - 1][0] + 1 if j else 1
            fig.patches.append(Rectangle(((x + 0.1) / WIDTH, y / height), 0.16 / WIDTH, 0.16 / height, facecolor=ACCENT,
                                         alpha=alpha, transform=fig.transFigure, figure=fig, linewidth=0))
            fig.text((x + 0.3) / WIDTH, (y + 0.08) / height,
                     quote(f"{name}, {lo} to {hi}", "document", "risk scoring bands (docs/risk-register.md)"),
                     fontsize=6.3, va="center")
            x += 1.05
        return fig
