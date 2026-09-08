"""Chart panels for the doctor report, rendered from the report context.

Two PNGs are produced (figsize keeps them pillow-safe for reportlab):
  * top    — daily FPG + postprandial glucose split by meal slot
            (post-breakfast / post-lunch / post-dinner) against the target corridor
  * bottom — daily high-GI share (bars) + overall PPBG trend (line)

Weekend bands are shaded; both panels are *descriptive plots of patient-logged
data*. No prediction, no labels beyond target range.
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

TEAL = "#0E6E7A"
ORANGE = "#E0782C"
PB_COLOR = "#D9A027"
PL_COLOR = "#3E8E6B"
PD_COLOR = "#C0462E"
CORR = "#EDF3F4"
GRID = "#D7E3E6"
BAND = "#F4F1E8"


def _series_array(ch, day_key, val_key, n, idx):
    arr = np.full(n, np.nan, float)
    for d, v in zip(ch[day_key], ch[val_key]):
        if d in idx:
            arr[idx[d]] = v
    return arr


def _arrays(ch):
    n = len(ch["dates"])
    idx = {d: i for i, d in enumerate(ch["dates"])}
    fpg = _series_array(ch, "fpg", "fpg_values", n, idx)
    pp = _series_array(ch, "ppbg", "ppbg_values", n, idx)
    pb = _series_array(ch, "pb", "pb_values", n, idx)
    pl = _series_array(ch, "pl", "pl_values", n, idx)
    pd = _series_array(ch, "pd", "pd_values", n, idx)
    return n, fpg, pp, pb, pl, pd


def _weekend_spans(ch, n, ax):
    for i in range(n):
        if ch["weekends"] and ch["weekends"][i]:
            ax.axvspan(i + 0.5, i + 1.5, color=BAND, zorder=0)


def _style(ax, top_axis=True, right_axis=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if top_axis:
        ax.spines["left"].set_color("#A9C2C7")
    if right_axis:
        ax.spines["bottom"].set_color("#A9C2C7")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def render_top(ch, out: str):
    n, fpg, pp, pb, pl, pd = _arrays(ch)
    fig, ax = plt.subplots(figsize=(11.7, 3.9), dpi=270)
    lo, hi = ch["corridor_low"], ch["corridor_high"]
    x = np.arange(1, n + 1)
    ax.axhspan(lo, hi, color="#EDF5F0", zorder=0)
    line_kw = dict(lw=1.9, zorder=4)
    ax.plot(x, pb, color=PB_COLOR, marker="o", ms=2.8, **line_kw,
            label="Post-Breakfast")
    ax.plot(x, pl, color=PL_COLOR, marker="s", ms=2.8, **line_kw,
            label="Post-Lunch")
    ax.plot(x, pd, color=PD_COLOR, marker="^", ms=3.0, **line_kw,
            label="Post-Dinner")
    ax.plot(x, fpg, color=TEAL, marker="d", ms=2.6, **line_kw,
            label="Fasting (FPG)")
    ylab = f"Target Glycemic Range ({lo:.0f}\u2013{hi:.0f} mg/dL)"
    if n:
        ax.text(1, hi + 8, ylab, fontsize=8.5, color="#5A8A63", va="bottom")
    all_v = [v for arr in (fpg, pp, pb, pl, pd) for v in arr if not np.isnan(v)]
    ymax = max(255, np.nanmax(all_v) * 1.06)
    ax.set_ylim(50, ymax)
    ax.set_yticks(list(range(50, 251, 25)))
    ax.set_ylabel("Blood Glucose (mg/dL)", fontsize=9.5)
    if n:
        step = max(1, round(n / 10))
        ticks = list(range(1, n + 1))[::step]
        ax.set_xticks(ticks)
        if ch["dates"]:
            ax.set_xticklabels([_dshort(ch["dates"][k - 1]) for k in ticks], fontsize=8)
        ax.set_xlim(0.5, n + 0.5)
        ax.set_xlabel(f"Assessment Days ({_dshort(ch['dates'][0])} \u2013 {_dshort(ch['dates'][-1])})",
                      fontsize=9.5)
    ax.legend(loc="upper right", fontsize=8.6, frameon=False)
    _style(ax)
    plt.tight_layout()
    fig.savefig(out, dpi=270)
    plt.close(fig)
    return out


def render_bottom(ch, out: str):
    n, fpg, pp, pb, pl, pd = _arrays(ch)
    fig, ax1 = plt.subplots(figsize=(11.7, 3.9), dpi=270)
    ax2 = ax1.twinx()
    x = np.arange(1, n + 1)
    if n:
        _weekend_spans(ch, n, ax1)
        bars = ax1.bar(x, ch["high_gi_share_daily"], color=TEAL, alpha=0.85,
                       zorder=3, width=0.7, label="High-GI Dietary Share (%)")
    ax1.set_ylim(0, 100)
    ax1.set_yticks(range(0, 101, 20))
    ax1.set_ylabel("High-GI Food Share in Daily Meals (%)", fontsize=9.5, color=TEAL)
    ax1.tick_params(axis="y", colors=TEAL)
    ax2.plot(x, pp, color=ORANGE, lw=2.2, zorder=4, label="PPBG Trend Line")
    ax2.set_ylim(100, 260)
    ax2.set_yticks(range(100, 261, 40))
    ax2.set_ylabel("Postprandial Glucose (mg/dL)", fontsize=9.5, color=ORANGE)
    ax2.tick_params(axis="y", colors=ORANGE)
    if n:
        step = max(1, round(n / 10))
        ticks = list(range(1, n + 1))[::step]
        ax1.set_xticks(ticks)
        if ch["dates"]:
            ax1.set_xticklabels([_dshort(ch["dates"][k - 1]) for k in ticks], fontsize=8)
        ax1.set_xlim(0.5, n + 0.5)
        ax1.set_xlabel(f"Assessment Days ({_dshort(ch['dates'][0])} \u2013 {_dshort(ch['dates'][-1])})",
                       fontsize=9.5)
    _style(ax1)
    ax2.spines["right"].set_color("#A9C2C7")
    ax1.spines["left"].set_color(TEAL)
    if n:
        ax1.legend(handles=[bars], labels=["High-GI Dietary Share (%)"],
                   loc="upper right", fontsize=9, frameon=False)
        ax2.legend(loc="upper left", fontsize=9, frameon=False)
    plt.tight_layout()
    fig.savefig(out, dpi=270)
    plt.close(fig)
    return out


def _dshort(d: str) -> str:
    from datetime import datetime
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d-%b")
    except ValueError:
        return d[:10]


def render(ctx: dict, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    ch = ctx["charts"]
    top = os.path.join(out_dir, f"chart-top-{ctx['patient_id']}.png")
    bottom = os.path.join(out_dir, f"chart-bottom-{ctx['patient_id']}.png")
    render_top(ch, top)
    render_bottom(ch, bottom)
    return top, bottom