"""On-screen (HTML) rendering of the same report context that the 2-page PDF uses.

The dashboard injects this into the Report tab so the doctor can read the whole
report without leaving the app. Wording mirrors the PDF and stays in the same
assistive, non-diagnostic voice, with the identical decision-support notice.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as esc

PPB = "#D9A027"
PPL = "#3E8E6B"
PPD = "#C0462E"
TEAL = "#0B4A58"
TEAL2 = "#0E6E7A"
GREEN = "#2E8B57"
RED = "#C0392B"
AMBER = "#C99700"
BORD = "#D3E1E4"
MUTED = "#5A6F79"
TEXT = "#21343C"

SLOT_LABELS = (
    ("Post-Breakfast", "post_breakfast", PPB),
    ("Post-Lunch", "post_lunch", PPL),
    ("Post-Dinner", "post_dinner", PPD),
)


def _n(v, digits=1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def _fdate(d: str) -> str:
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return d[:10]


def _pct(n, total) -> float:
    if not total:
        return 0.0
    return round(n / total * 100, 0)


def _delta(a, b) -> str:
    if a is None or b is None:
        return "—"
    return f"{b - a:+.1f}"


def _dist_bar(items, total) -> str:
    """items: [(color, label, count)] -> stacked bar + inline legend."""
    segs = []
    for color, _label, count in items:
        share = _pct(count, total)
        width = max(share, 3) if share > 0 else 0
        segs.append(f'<span class="rp-seg" style="width:{width}%;background:{color}"></span>')
    legend = "".join(
        f'<span class="rp-dot"><i style="background:{color}"></i>{esc(label)} '
        f"<b>{_pct(count, total):g}%</b></span>"
        for color, label, count in items)
    return f'<div class="rp-bar">{"".join(segs)}</div><div class="rp-legend">{legend}</div>'


CSS = """
.report-sheet{font:12px/1.5 system-ui,sans-serif;color:#21343c;background:#fff;
  border:1px solid #d3e1e4;border-radius:10px;overflow:hidden;margin-top:12px}
.rp-head{background:linear-gradient(135deg,#0b4a58,#0e6e7a);color:#fff;
  padding:14px 16px 10px;display:flex;justify-content:space-between;gap:12px;align-items:center}
.rp-title{font-size:15px;font-weight:700;letter-spacing:.2px}
.rp-sub{font-size:10.5px;opacity:.85;margin-top:2px}
.rp-badge{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.4);
  border-radius:8px;padding:6px 12px;text-align:center;white-space:nowrap}
.rp-badge b{font-size:18px;display:block}
.rp-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;
  padding:10px 16px;background:#f2f6f7;border-bottom:1px solid #d3e1e4}
.rp-strip div{font-size:10.5px}
.rp-strip small{display:block;color:#5a6f79;font-size:9px;text-transform:uppercase;letter-spacing:.4px}
.rp-cols{display:grid;grid-template-columns:1fr 1.18fr 1fr;gap:12px;padding:12px 16px}
@media (max-width:1100px){.rp-cols{grid-template-columns:1fr}}
.rp-card{border:1px solid #d3e1e4;border-left:3px solid #0e6e7a;border-radius:6px;
  padding:9px 11px;background:#fbfefe;margin-bottom:9px}
.rp-card h4{margin:0 0 5px;font-size:10px;letter-spacing:.5px;text-transform:uppercase;
  color:#0b4a58}
.rp-bignum{display:flex;gap:10px;margin-bottom:7px}
.rp-bignum div{flex:1;background:#fff;border:1px solid #d3e1e4;border-radius:6px;
  padding:6px 8px;font-size:10.5px}
.rp-bignum b{font-size:18px;color:#0b4a58;display:block}
.rp-muted{color:#5a6f79;font-size:9.5px;font-weight:normal}
.rp-slot{font-size:11px;margin:2px 0}
.rp-bar{display:flex;height:10px;border-radius:5px;overflow:hidden;background:#eef3f4}
.rp-seg{height:100%}
.rp-legend{display:flex;gap:12px;flex-wrap:wrap;margin-top:4px;font-size:10.5px}
.rp-dot i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
.rp-tbl{width:100%;border-collapse:collapse;font-size:10.5px}
.rp-tbl th{background:#0b4a58;color:#fff;font-weight:600;text-align:left;
  padding:3px 6px;font-size:10px}
.rp-tbl td{border:1px solid #d3e1e4;padding:3px 6px}
.rp-tbl tr:nth-child(even) td{background:#e7f1f3}
.rp-pattern{border:1px solid #d3e1e4;border-left:2.5px solid #0e6e7a;border-radius:6px;
  padding:7px 9px;margin-bottom:7px;background:#fbfefe}
.rp-pattern b{font-size:11px;color:#0b4a58}
.rp-pattern p{margin:2px 0 0;font-size:10.5px;color:#21343c}
.rp-notice{font-size:10px;color:#5a6f79;background:#f2f6f7;border:1px solid #d3e1e4;
  border-left:3px solid #0b4a58;border-radius:6px;padding:7px 10px;margin:0 16px 12px}
.rp-chart{width:100%;height:auto;border:1px solid #d3e1e4;border-radius:8px;display:block}
.rp-strip2{background:#e7f1f3;border:1px solid #d3e1e4;border-left:3px solid #0e6e7a;
  border-radius:6px;padding:7px 11px;margin:8px 0;font-size:11px}
.rp-strip2 b{color:#0b4a58}
.rp-meta{font-size:10px;color:#5a6f79;margin:2px 16px 12px}
"""


def _page_head(title, sub, badge_label, badge_value):
    return (
        '<div class="rp-head">'
        f'<div><div class="rp-title">{esc(title)}</div>'
        f'<div class="rp-sub">{esc(sub)}</div></div>'
        f'<div class="rp-badge">{esc(badge_label)}<b>{badge_value}</b></div>'
        "</div>")


def _info_strip(cells: list[tuple[str, str]]) -> str:
    body = "".join(f"<div><small>{esc(a)}</small>{esc(b)}</div>" for a, b in cells)
    return f'<div class="rp-strip">{body}</div>'


def _page1(ctx) -> list[str]:
    pie, glu, tir, meals_m = ctx["patient"], ctx["glucose"], ctx["tir"], ctx["meals"]
    win = ctx["window"]
    date_fmt = f"{_fdate(win['start'])} – {_fdate(win['end'])}"
    parts = [_page_head(
        "Clinical Telemetry & Behavioral Nutrition Report",
        "Ambulatory glucose and contextual dietary telemetry · Part 1: baselines",
        "Adherence Index", f"{ctx['adherence_index']:g}%")]
    parts.append(_info_strip([
        ("Patient & UHID", f"{pie['name']} (UHID: {pie['uh_id']})"),
        ("Caregiver", pie["caregiver"]),
        ("Telemetry interval", date_fmt),
        ("Logged meals / readings", f"{ctx['meals_count']} / {ctx['readings_count']}"),
        ("Active logging days", f"{ctx['active_logging_days']} of {ctx['eligible_days']}"),
        ("Aahaar · generated", ctx["product"]["generated"]),
    ]))

    # column 1 — food & glycemic baselines
    c1 = ['<div><div class="rp-card"><h4>Food &amp; Glycemic Baselines</h4>']
    c1.append('<div class="rp-bignum">'
              f'<div>Mean fasting (FPG)<b>{_n(glu["mean_fpg"])}</b>mg/dL</div>'
              f'<div>Mean postprandial (PPBG)<b>{_n(glu["mean_ppbg"])}</b>mg/dL</div></div>')
    c1.append('<h4>Mean postprandial by meal slot (mg/dL)</h4>')
    for label, key, color in SLOT_LABELS:
        s = glu.get(key, {})
        if s.get("mean") is None:
            continue
        c1.append(f'<div class="rp-slot"><span style="color:{color}">●</span> {label} — '
                  f'<b>{_n(s["mean"])}</b> ({s.get("count", 0)} logged)</div>')
    c1.append('<h4>Glycemic target range distribution'
              f'<span class="rp-muted"> (target {tir["low"]:g}–{tir["high"]:g} mg/dL)</span></h4>')
    c1.append(_dist_bar([(GREEN, "In range", tir["in"]), (RED, "Above range", tir["above"]),
                         (AMBER, "Below range", tir["below"])], tir.get("total") or 100))
    gc = meals_m["gi_counts"]
    c1.append("<h4>Glycemic index (GI) intake distribution</h4>")
    c1.append(_dist_bar([(GREEN, "Low GI", gc.get("low", 0)),
                         (AMBER, "Med GI", gc.get("med", 0)),
                         (RED, "High GI", gc.get("high", 0))],
                        max(1, sum(gc.values()))))
    tot_meals = max(1, sum(gc.values()))
    c1.append("<h4>Calibrated portion distribution (katori)</h4>")
    rows = ["<tr><th>Size</th><th>Volume</th><th>Proportion</th></tr>"]
    for pc in meals_m["portion_counts"]:
        rows.append(f"<tr><td>{esc(pc['letter'])}</td><td>{esc(pc['label'])}</td>"
                    f"<td>{_pct(pc['count'], tot_meals):g}% of meals</td></tr>")
    c1.append(f'<table class="rp-tbl">{"".join(rows)}</table>')
    if ctx["avoid"]["items"]:
        c1.append("<h4>Doctor-set avoid list</h4>")
        c1.append(f'<div class="rp-meta">Meals containing '
                  f'{esc(", ".join(ctx["avoid"]["items"]))} were logged '
                  f'<b>{ctx["avoid"]["count"]}</b> times this window — a reflective count.</div>')
    c1.append("</div></div>")

    # column 2 — segments, chronobiology & events
    c2 = ['<div><div class="rp-card"><h4>Segments, Chronobiology &amp; Events</h4>']
    c2.append("<h4>Weekday vs weekend</h4>")
    w = ["<tr><th>Metric</th><th>Mon–Fri</th><th>Sat–Sun</th><th>Δ</th></tr>"]
    w.append(f"<tr><td>High-GI share</td>"
             f"<td>{_n(glu.get('weekday_highgi'), 0)}%</td>"
             f"<td>{_n(glu.get('weekend_highgi'), 0)}%</td>"
             f"<td>{_delta(glu.get('weekday_highgi'), glu.get('weekend_highgi'))} pts</td></tr>")
    for label, key, _c in SLOT_LABELS:
        s = glu.get(key, {})
        w.append(f"<tr><td>PPBG – {label} (mg/dL)</td>"
                 f"<td>{_n(s.get('weekday') or '—')}</td><td>{_n(s.get('weekend') or '—')}</td>"
                 f"<td>{_delta(s.get('weekday'), s.get('weekend'))} mg/dL</td></tr>")
    c2.append(f'<table class="rp-tbl">{"".join(w)}</table>')
    c2.append("<h4>Readings by context</h4>")
    t = ["<tr><th>Context</th><th>Count</th><th>Mean (mg/dL)</th></tr>"]
    for tag in ("fasting", "postprandial", "random"):
        vals = ctx["glucose_by_tag"].get(tag, [])
        if vals:
            t.append(f"<tr><td>{tag.capitalize().replace('Post', 'Post-')}</td>"
                     f"<td>{len(vals)}</td><td>{_n(sum(vals) / len(vals))}</td></tr>")
    c2.append(f'<table class="rp-tbl">{"".join(t)}</table>')
    c2.append("<h4>Logged meal composition (top genera)</h4>")
    g = ["<tr><th>Staple / genus</th><th>Meals</th><th>Share</th></tr>"]
    for genus, count, share in ctx["top_genera"]:
        g.append(f"<tr><td>{esc(genus)}</td><td>{count}</td><td>{share:g}%</td></tr>")
    c2.append(f'<table class="rp-tbl">{"".join(g)}</table>')
    c2.append("</div></div>")

    # column 3 — observed patterns
    c3 = ['<div><div class="rp-card"><h4>Observed patterns</h4>']
    for title, body in ctx["patterns"]:
        c3.append(f'<div class="rp-pattern"><b>{esc(title)}</b><p>{esc(body)}</p></div>')
    if not ctx["patterns"]:
        c3.append('<div class="rp-pattern"><p>No patterns recorded for this window.</p></div>')
    c3.append("</div></div>")

    parts.append(f'<div class="rp-cols">{"".join(c1 + c2 + c3)}</div>')
    parts.append('<div class="rp-notice"><b>Assistive decision-support notice:</b> '
                 "This report presents self-reported patient telemetry, household portion "
                 "estimates and logged glucose values. It contains no diagnoses, ratings or "
                 "therapeutic directives — clinical decisions rest solely with the treating "
                 "physician.</div>")
    return parts


def _page2(ctx, image_base) -> list[str]:
    pie, glu, tir = ctx["patient"], ctx["glucose"], ctx["tir"]
    win = ctx["window"]
    adjacent = ctx["charts"]
    parts = [_page_head(
        "Longitudinal Telemetry & Glycemic Excursion Charts",
        "Ambulatory glucose and dietary telemetry dashboard · Part 2: visual trends",
        "Telemetry stream", f"{len(adjacent['dates'])} days")]
    parts.append(_info_strip([
        ("Patient & UHID", f"{pie['name']} (UHID: {pie['uh_id']})"),
        ("Caregiver", pie["caregiver"]),
        ("Telemetry interval", f"{_fdate(win['start'])} – {_fdate(win['end'])}"),
        ("Meals / Readings", f"{ctx['meals_count']} / {ctx['readings_count']}"),
    ]))
    parts.append(f'<img class="rp-chart" src="{esc(image_base)}?which=top" alt="corridor chart"/>'
                 f'<img class="rp-chart" src="{esc(image_base)}?which=bottom" alt="dietary chart"/>')
    parts.append('<div class="rp-meta" style="margin-top:10px">'
                 "Glycemic corridor: fasting (FPG) and postprandial by slot (post-breakfast "
                 "amber, post-lunch green, post-dinner crimson) versus the target corridor; "
                 "lower panel plots daily high-GI share (bars) against overall postprandial "
                 "trend (line), weekend bands shaded. Patient-logged data, for clinician review."
                 "</div>")
    m = ctx["meals"]
    slots = " | ".join(f"{label}: {_n(glu.get(key, {}).get('mean'))}"
                       for label, key, _c in SLOT_LABELS)
    parts.append(f'<div class="rp-strip2"><b>Metric summary</b><br/>'
                 f"Mean fasting: <b>{_n(glu['mean_fpg'])}</b> mg/dL | "
                 f"Mean PPBG (all slots): <b>{_n(glu['mean_ppbg'])}</b> mg/dL | "
                 f"{slots} mg/dL | Target TIR ({tir['low']:g}–{tir['high']:g}): "
                 f"<b>{tir['in']:g}%</b> of readings | Adherence: <b>{ctx['adherence_index']:g}%</b>"
                 "</div>")
    corr = []
    if m["high_gi_share"] is not None:
        corr.append(f"High-GI share: <b>{m['high_gi_share']:g}%</b>")
    wd, we = glu.get("weekday_highgi"), glu.get("weekend_highgi")
    if wd is not None and we is not None:
        corr.append(f"Weekend high-GI: <b>{we:g}%</b> ({_delta(wd, we)} pts)")
    if glu["weekend_ppbg"] and glu["weekday_ppbg"]:
        corr.append(f"Weekend PPBG: <b>{_delta(glu['weekday_ppbg'], glu['weekend_ppbg'])}"
                    " mg/dL</b> vs weekdays")
    if adjacent["correlation"] is not None:
        corr.append(f"Daily high-GI–PPBG correlation: <b>r = {adjacent['correlation']:g}</b>")
    if corr:
        parts.append(f'<div class="rp-strip2"><b>Correlation summary</b><br/>'
                     f'{" &nbsp;|&nbsp; ".join(corr)}</div>')
    return parts


def render_html(ctx: dict, image_base: str) -> str:
    pieces = ["<div class=\"report-sheet\">", f"<style>{CSS}</style>"]
    pieces += _page1(ctx)
    pieces += _page2(ctx, image_base)
    pieces.append("</div>")
    return "".join(pieces)