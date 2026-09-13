"""2-page A4 doctor report built with reportlab from the report context.

Faithful port of the verified sample renderer, now fully data-driven. Every
number comes from patient-logged meals and readings. All language stays in the
descriptive voice (observed / logged / reflective) with the Assistive
Decision-Support Notice on every page.
"""
from __future__ import annotations

import os

import matplotlib
import matplotlib.pyplot as plt  # noqa: F401  (keeps font dir lookup deterministic)
import reportlab  # noqa: F401
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.lib.colors import HexColor, white

from ..core.parse import READING_TAG_LABELS

FONTDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DVS", os.path.join(FONTDIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVSB", os.path.join(FONTDIR, "DejaVuSans-Bold.ttf")))

TEAL = HexColor("#0B4A58")
TEAL2 = HexColor("#0E6E7A")
TEALBG = HexColor("#E7F1F3")
TEALTX = HexColor("#14545F")
CARD = HexColor("#FBFFFF")
BORD = HexColor("#D3E1E4")
MUTED = HexColor("#5A6F79")
TEXT = HexColor("#21343C")
ORANGE = HexColor("#D97B2C")
GREEN = HexColor("#2E8B57")
RED = HexColor("#C0392B")
AMBER = HexColor("#C99700")
GRAYL = HexColor("#F2F6F7")

PPB_COLOR = "#D9A027"
PPL_COLOR = "#3E8E6B"
PPD_COLOR = "#C0462E"
SLOT_LABELS = (("Post-Breakfast", "post_breakfast", PPB_COLOR),
               ("Post-Lunch", "post_lunch", PPL_COLOR),
               ("Post-Dinner", "post_dinner", PPD_COLOR))


def ps(name, **kw):
    base = dict(fontName="DVS", fontSize=9, leading=12, textColor=TEXT)
    base.update(kw)
    return ParagraphStyle(name, **base)


st = {
    "h1": ps("h1", fontName="DVSB", fontSize=17, leading=20, textColor=TEAL),
    "sub": ps("sub", fontSize=8.2, leading=10.4, textColor=MUTED),
    "badge_t": ps("badge_t", fontName="DVSB", fontSize=7.5, leading=9, textColor=white),
    "badge_v": ps("badge_v", fontName="DVSB", fontSize=13, leading=15, textColor=white, alignment=TA_CENTER),
    "lbl": ps("lbl", fontSize=6.2, leading=8, textColor=MUTED, fontName="DVSB"),
    "val": ps("val", fontName="DVSB", fontSize=8.2, leading=9.2, textColor=TEXT),
    "big_l": ps("big_l", fontSize=7, leading=9, textColor=MUTED),
    "big_v": ps("big_v", fontName="DVSB", fontSize=12.5, leading=14, textColor=TEAL),
    "big_u": ps("big_u", fontSize=7, leading=8.4, textColor=MUTED),
    "sh": ps("sh", fontName="DVSB", fontSize=8.6, leading=11, textColor=TEAL),
    "cardt": ps("cardt", fontName="DVSB", fontSize=7.8, leading=9.2, textColor=TEAL),
    "cardb": ps("cardb", fontSize=7.4, leading=8.4),
    "tcell": ps("tcell", fontSize=7.6, leading=8.4),
    "thead": ps("thead", fontName="DVSB", fontSize=7.2, leading=9, textColor=white),
    "note": ps("note", fontSize=6.8, leading=9, textColor=MUTED),
    "strip_t": ps("strip_t", fontName="DVSB", fontSize=8.6, leading=11, textColor=TEALTX),
    "strip_v": ps("strip_v", fontName="DVSB", fontSize=10, leading=12, textColor=TEAL),
    "mtd": ps("mtd", fontSize=7.2, leading=9.4, textColor=MUTED, alignment=TA_JUSTIFY),
}

TABLE_STYLE = [
    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
    ("GRID", (0, 0), (-1, -1), 0.4, BORD),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, TEALBG]),
    ("TOPPADDING", (0, 0), (-1, -1), 1),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
]


def table(rows, widths):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle(TABLE_STYLE))
    return t


def header(badge_label, badge_value, subtitle):
    badge = Table([[Paragraph(badge_label.upper(), st["badge_t"])],
                   [Paragraph(badge_value, st["badge_v"])]], colWidths=[118])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("BOX", (0, 0), (-1, -1), 0, white),
        ("TOPPADDING", (0, 0), (0, 0), 3),
        ("BOTTOMPADDING", (0, 1), (0, 1), 3),
        ("TOPPADDING", (0, 1), (0, 1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    row = Table([[Paragraph("CLINICAL TELEMETRY &amp;<br/>BEHAVIORAL NUTRITION REPORT", st["h1"])],
                 [badge]], colWidths=[400, 122])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    return [row, Spacer(1, 2), Paragraph(subtitle, st["sub"]), Spacer(1, 5)]


def info_strip(cells):
    rows = [[Paragraph("<b>" + label.upper() + "</b><br/>" + value, st["val"])
             for label, value in cells]]
    t = Table(rows, colWidths=["*"] * len(cells))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORD),
        ("BACKGROUND", (0, 0), (-1, -1), GRAYL),
    ]))
    return t


def num_card(label, value, unit, accent, w=150):
    inner = [[Paragraph(label.upper(), st["big_l"])],
             [Paragraph(f"{value}", st["big_v"])],
             [Paragraph(unit, st["big_u"])]]
    t = Table(inner, colWidths=[w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def dist_rows(items, cw=140):
    out = []
    tot = sum(p for (_, _, p) in items) or 1
    widths = [max(4, round(p / tot * cw)) for (_, _, p) in items]
    widths[-1] = max(4, cw - sum(widths[:-1]))
    b = Table([[""] * len(items)], colWidths=widths, rowHeights=[6])
    b.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    for k, it in enumerate(items):
        b.setStyle(TableStyle([("BACKGROUND", (k, 0), (k, 0), it[0])]))
    out.append(b)
    out.append(Spacer(1, 2))
    for color, label, pct in items:
        r = Table([[Paragraph(f'<font color="{color}">●</font>', st["tcell"]),
                    Paragraph(f"{label} — <b>{pct:g}%</b>", st["tcell"])]],
                  colWidths=[12, cw - 12])
        r.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LEFTPADDING", (0, 0), (0, 0), 2),
                               ("RIGHTPADDING", (0, 0), (0, 0), 2),
                               ("LEFTPADDING", (1, 0), (1, 0), 0)]))
        out.append(r)
    return out


def section_header(num, title, cw=140):
    chip = Table([[Paragraph(num, st["cardb"])]], colWidths=[14], rowHeights=[12])
    chip.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, -1), white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0, white),
    ]))
    row = Table([[chip, Paragraph(title.upper(), st["sh"])]], colWidths=[14, cw - 14])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (1, 0), (1, 0), 4)]))
    return row


def opcard(title, body, cw=140):
    inner = [[Paragraph(title, st["cardt"]), Spacer(1, 2), Paragraph(body, st["cardb"])]]
    tb = Table(inner, colWidths=[cw])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, TEAL2),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tb


def _n(v, digits=1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}" if isinstance(v, float) else f"{v}"


def _fdate(d: str) -> str:
    from datetime import datetime
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return d[:10]


def _pct(n, total) -> float:
    if not total:
        return 0.0
    return round(n / total * 100, 0)


def page1(ctx):
    f = []
    pie = ctx["patient"]
    glu = ctx["glucose"]
    tir = ctx["tir"]
    meals_m = ctx["meals"]
    window = ctx["window"]
    date_fmt = f"{_fdate(window['start'])} \u2013 {_fdate(window['end'])}"
    f += header("Adherence Index", f"{ctx['adherence_index']:g}%",
                "AMBULATORY GLUCOSE &amp; CONTEXTUAL DIETARY TELEMETRY · PART 1: BASELINES "
                "&amp; BEHAVIORAL METRICS")
    f.append(info_strip([
        ("Patient &amp; UHID", f"{pie['name']} (UHID: {pie['uh_id']})"),
        ("Attendant Caregiver", pie["caregiver"]),
        ("Telemetry Interval", date_fmt),
        ("Logged meals / readings", f"{ctx['meals_count']} / {ctx['readings_count']}"),
        ("Active logging days", f"{ctx['active_logging_days']} of {ctx['eligible_days']} days"),
        ("Aahaar · generated", ctx["product"]["generated"]),
    ]))
    f.append(Spacer(1, 6))

    c1 = []
    c1.append(section_header("1", "Food &amp; Glycemic Baselines", 140))
    c1.append(Spacer(1, 2))
    cards = Table([[num_card("Mean Fasting (FPG)", _n(glu["mean_fpg"]), "mg/dL", TEAL2, w=70),
                    num_card("Mean Postprandial (PPBG)", _n(glu["mean_ppbg"]), "mg/dL", ORANGE, w=70)]],
                  colWidths=[70, 70])
    cards.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (0, 0), 0),
                               ("RIGHTPADDING", (1, 0), (1, 0), 0),
                               ("LEFTPADDING", (1, 0), (1, 0), 2)]))
    c1.append(cards)
    c1.append(Spacer(1, 2))
    c1.append(Paragraph("MEAN POSTPRANDIAL BY MEAL SLOT (mg/dL)", st["cardt"]))
    c1.append(Spacer(1, 1))
    for label, slot_key, color in SLOT_LABELS:
        s = glu.get(slot_key, {})
        if s.get("mean") is None:
            continue
        c1.append(Paragraph(f'<font color="{color}">●</font> {label} — <b>{_n(s["mean"])}</b>'
                            f' &nbsp;<font size=6.4 color="#5A6F79">({s["count"]} logged)</font>',
                            st["cardb"]))
        c1.append(Spacer(1, 1))
    c1.append(Spacer(1, 1))
    c1.append(Paragraph(f"GLYCEMIC TARGET RANGE DISTRIBUTION "
                        f"<font size=7 color='#5A6F79'>(target {tir['low']:g}\u2013{tir['high']:g} mg/dL)</font>",
                        st["cardt"]))
    c1.append(Spacer(1, 2))
    c1 += dist_rows([(GREEN, "In Range", tir["in"]), (RED, "Above Range", tir["above"]),
                     (AMBER, "Below Range", tir["below"])])
    c1.append(Spacer(1, 2))
    c1.append(Paragraph("GLYCEMIC INDEX (GI) INTAKE DISTRIBUTION", st["cardt"]))
    c1.append(Spacer(1, 2))
    gc = meals_m["gi_counts"]
    tot_meals = max(1, sum(gc.values()))
    c1 += dist_rows([(GREEN, "Low GI", _pct(gc.get("low", 0), tot_meals)),
                     (AMBER, "Med GI", _pct(gc.get("med", 0), tot_meals)),
                     (RED, "High GI", _pct(gc.get("high", 0), tot_meals))])
    c1.append(Spacer(1, 2))
    c1.append(Paragraph("CALIBRATED PORTION DISTRIBUTION (KATORI)", st["cardt"]))
    c1.append(Spacer(1, 2))
    pt_rows = [[Paragraph("Size", st["thead"]), Paragraph("Volume", st["thead"]),
                Paragraph("Proportion", st["thead"])]]
    for pc in meals_m["portion_counts"]:
        pt_rows.append([Paragraph(pc["letter"], st["tcell"]),
                        Paragraph(pc["label"], st["tcell"]),
                        Paragraph(f"{_pct(pc['count'], tot_meals):g}% of meals", st["tcell"])])
    c1.append(table(pt_rows, [38, 78, 24]))
    c1.append(Spacer(1, 2))
    if ctx["avoid"]["items"]:
        c1.append(Paragraph("DOCTOR-SET AVOID LIST (REFLECTIVE COUNT)", st["cardt"]))
        c1.append(Spacer(1, 2))
        c1.append(Paragraph(
            f"Meals containing items on the doctor's avoid list"
            f" ({', '.join(ctx['avoid']['items'])}) were logged "
            f"<b>{ctx['avoid']['count']} times</b> this window — a reflective count, "
            f"no consequence implied.", st["cardb"]))
        c1.append(Spacer(1, 2))

    c2 = []
    c2.append(section_header("2", "Segments, Chronobiology &amp; Events", 168))
    c2.append(Spacer(1, 2))
    c2.append(Paragraph("WEEKDAY VS WEEKEND SEGMENTATION", st["cardt"]))
    c2.append(Spacer(1, 2))
    wk_row = [Paragraph("Metric", st["thead"]), Paragraph("Mon\u2013Fri", st["thead"]),
              Paragraph("Sat\u2013Sun", st["thead"]), Paragraph("Δ", st["thead"])]
    delta_higi = None
    if meals_m["high_gi_share"] is not None:
        delta_higi = glu.get("weekend_highgi") or meals_m.get("weekend_highgi")
    w_rows = [wk_row]
    w_rows.append([Paragraph("High-GI share", st["tcell"]),
                   Paragraph(_n(glu.get("weekday_highgi"), 0) if glu.get("weekday_highgi") is not None else "—",
                             st["tcell"]),
                   Paragraph(_n(glu.get("weekend_highgi"), 0) if glu.get("weekend_highgi") is not None else "—",
                             st["tcell"]),
                   Paragraph(_deltastr(glu.get("weekend_highgi"), glu.get("weekday_highgi")) + " pts.",
                             st["tcell"])])
    for label, slot_key, _color in SLOT_LABELS:
        s = glu.get(slot_key, {})
        w_rows.append([Paragraph(f"PPBG \u2013 {label} (mg/dL)", st["tcell"]),
                       Paragraph(_n(s.get("weekday")) if s.get("weekday") else "—", st["tcell"]),
                       Paragraph(_n(s.get("weekend")) if s.get("weekend") else "—", st["tcell"]),
                       Paragraph(_deltastr(s.get("weekend"), s.get("weekday")) + " mg/dL", st["tcell"])])
    c2.append(table(w_rows, [52, 34, 40, 42]))
    c2.append(Spacer(1, 4))
    c2.append(Paragraph("OBSERVED TIMING DISTRIBUTION (READINGS BY TAG)", st["cardt"]))
    c2.append(Spacer(1, 2))
    tag_rows = [[Paragraph("Tag", st["thead"]), Paragraph("Count", st["thead"]),
                 Paragraph("Mean (mg/dL)", st["thead"])]]
    for tag in ("fasting", "postprandial", "random"):
        vals = ctx["glucose_by_tag"].get(tag, [])
        if vals:
            label = READING_TAG_LABELS.get(tag, tag)
            tag_rows.append([Paragraph(label.capitalize(), st["tcell"]),
                             Paragraph(str(len(vals)), st["tcell"]),
                             Paragraph(_n(sum(vals) / len(vals)), st["tcell"])])
    c2.append(table(tag_rows, [52, 34, 42]))
    c2.append(Spacer(1, 4))
    c2.append(Paragraph("LOGGED MEAL COMPOSITION (TOP GENERA)", st["cardt"]))
    c2.append(Spacer(1, 2))
    gen_rows = [[Paragraph("Staple / genus", st["thead"]), Paragraph("Meals", st["thead"]),
                 Paragraph("Share", st["thead"])]]
    for genus, count, share in ctx["top_genera"]:
        gen_rows.append([Paragraph(genus.capitalize(), st["tcell"]),
                         Paragraph(str(count), st["tcell"]),
                         Paragraph(f"{share:g}%", st["tcell"])])
    c2.append(table(gen_rows, [52, 34, 42]))

    c3 = []
    c3.append(section_header("3", "Observed Patterns", 140))
    c3.append(Spacer(1, 2))
    for title, body in ctx["patterns"]:
        c3.append(opcard(title, body))
        c3.append(Spacer(1, 2))
    cols = Table([[c1, c2, c3]], colWidths=[140, 168, 140])
    cols.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    f.append(cols)
    f.append(Spacer(1, 4))
    notice = Table([[Paragraph(
        "<b>Assistive Decision-Support Notice:</b> This page presents self-reported patient "
        "telemetry, household portion estimates, and logged glucose values. It contains no "
        "clinical diagnoses, predictive ratings, counseling advice, or therapeutic directives "
        "\u2014 clinical decisions rest solely with the treating physician.", st["note"])]],
        colWidths=[528])
    notice.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAYL),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    f.append(notice)
    return f


def _deltastr(a, b) -> str:
    if a is None or b is None:
        return "—"
    d = a - b
    return f"{d:+.1f}"


def page2(ctx, top, bottom):
    f = []
    pie = ctx["patient"]
    glu = ctx["glucose"]
    window = ctx["window"]
    date_fmt = f"{_fdate(window['start'])} \u2013 {_fdate(window['end'])}"
    badge = Table([[Paragraph("LONGITUDINAL ASSESSMENT", st["badge_t"])],
                   [Paragraph(f"{len(ctx['charts']['dates'])}-Day Telemetry Stream", st["cardb"])]],
                  colWidths=[118])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("BOX", (0, 0), (-1, -1), 0, white),
        ("TOPPADDING", (0, 0), (0, 0), 3),
        ("BOTTOMPADDING", (0, 1), (0, 1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    row = Table([[Paragraph("LONGITUDINAL TELEMETRY &amp;<br/>GLYCEMIC EXCURSION CHARTS", st["h1"])],
                 [badge]], colWidths=[400, 122])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    f.append(row)
    f.append(Spacer(1, 2))
    f.append(Paragraph("AMBULATORY GLUCOSE &amp; DIETARY TELEMETRY DASHBOARD · "
                       "PART 2: VISUAL TREND ANALYSIS", st["sub"]))
    f.append(Spacer(1, 2))
    f.append(info_strip([
        ("Patient &amp; UHID", f"{pie['name']} (UHID: {pie['uh_id']})"),
        ("Caregiver", pie["caregiver"]),
        ("Telemetry Interval", date_fmt),
        ("Meals / Readings", f"{ctx['meals_count']} / {ctx['readings_count']}"),
    ]))
    f.append(Spacer(1, 6))
    from PIL import Image as PILImage
    for path, hw in ((top, None), (bottom, None)):
        width = 522
        im = PILImage.open(path)
        f.append(Image(path, width=width,
                       height=width * im.height / im.width))
        f.append(Spacer(1, 3))
    tir = ctx["tir"]
    slot_means = " &nbsp;|&nbsp; ".join(
        f"{label}: <b>{_n(glu.get(slot_key, {}).get('mean'))}</b>"
        for label, slot_key, _c in SLOT_LABELS)
    ms = Table([[Paragraph("METRIC SUMMARY", st["strip_t"])],
                [Paragraph(f"Mean Fasting: <b>{_n(glu['mean_fpg'])}</b> mg/dL &nbsp;|&nbsp; "
                           f"Mean PPBG (all meal slots): <b>{_n(glu['mean_ppbg'])}</b> mg/dL "
                           f"&nbsp;|&nbsp; {slot_means} mg/dL &nbsp;|&nbsp; "
                           f"Target TIR ({tir['low']:g}\u2013{tir['high']:g}): <b>{tir['in']:g}%</b> "
                           f"of readings &nbsp;|&nbsp; Adherence: <b>{ctx['adherence_index']:g}%</b> "
                           f"of days", st["strip_v"])]], colWidths=[522])
    ms.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEALBG),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 3, TEAL2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    f.append(ms)
    f.append(Spacer(1, 4))
    mm = ctx["meals"]
    corr_txt = []

    def pct(a, b):
        if a is None or b is None:
            return "—"
        return f"{a - b:+.1f}"

    if mm["high_gi_share"] is not None:
        corr_txt.append(f"High-GI share mean: <b>{mm['high_gi_share']:g}%</b>")
    wd = glu.get("weekday_highgi")
    we = glu.get("weekend_highgi")
    if wd is not None and we is not None:
        corr_txt.append(f"Weekend high-GI surge: <b>{we:g}%</b> ({pct(we, wd)} pts)")
    if glu["weekend_ppbg"] and glu["weekday_ppbg"]:
        corr_txt.append(f"Weekend PPBG excursion: <b>{pct(glu['weekend_ppbg'], glu['weekday_ppbg'])}"
                        f" mg/dL</b> vs weekdays")
    if ctx["charts"]["correlation"] is not None:
        corr_txt.append(f"Daily high-GI–PPBG correlation: <b>r = {ctx['charts']['correlation']:g}</b>")
    cs = Table([[Paragraph("CORRELATION SUMMARY", st["strip_t"])],
                [Paragraph(" &nbsp;&nbsp;|&nbsp;&nbsp; ".join(corr_txt) or "&nbsp;", st["strip_v"])]],
               colWidths=[522])
    cs.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEALBG),
        ("BOX", (0, 0), (-1, -1), 0.7, BORD),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ORANGE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    f.append(cs)
    f.append(Spacer(1, 4))
    n_days = len(ctx["charts"]["dates"])
    f.append(Paragraph(
        "<b>How to read this page:</b> The upper panel plots the patient's self-monitored "
        f"fasting (FPG) glucose and postprandial glucose for each meal slot \u2014 "
        "post-breakfast (amber), post-lunch (green) and post-dinner (crimson) \u2014 over "
        f"the {n_days}-day window against the target corridor "
        f"({tir['low']:g}\u2013{tir['high']:g} mg/dL). The lower panel plots the daily "
        "share of high-GI foods (bars, left axis) alongside the overall postprandial trend "
        "(line, right axis); weekend bands are shaded. All values are patient-logged data "
        "presented for the clinician's review.", st["mtd"]))
    return f


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORD)
    canvas.setLineWidth(0.6)
    canvas.line(36, 34, A4[0] - 36, 34)
    canvas.setFont("DVSB", 7.5)
    canvas.setFillColor(TEALTX)
    canvas.drawString(36, 24, "Aahaar")
    canvas.setFont("DVS", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(58, 24, "Health-a-thon 2026 · Diabetes Care · Assistive (non-diagnostic)")
    canvas.drawRightString(A4[0] - 36, 24, f"Page {doc.page} of 2")
    canvas.drawCentredString(A4[0] / 2, 24, "Prepared from patient-logged data · for clinician review")
    canvas.restoreState()


def render(ctx: dict, out_dir: str, top_png: str, bottom_png: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    fn = f"Aahaar-Doctor-Report-{ctx['patient_id']}-{ctx['window']['start']}.pdf"
    out = os.path.join(out_dir, fn)
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=36, rightMargin=36,
                          topMargin=38, bottomMargin=40,
                          title="Aahaar Doctor Report", author="Aahaar")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    story = page1(ctx) + [PageBreak()] + page2(ctx, top_png, bottom_png)
    doc.build(story)
    return out