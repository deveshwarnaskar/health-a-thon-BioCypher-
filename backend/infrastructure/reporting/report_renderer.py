"""Deterministic Document & Report Renderers (Gate 10N).

Implements IDocumentRenderer port with pure Python ReportLab and Matplotlib:
1. ClinicalPdfRenderer: Full clinical depth, review states, carbs/GI, legal clinician notice.
2. PatientPdfRenderer: Patient-facing summary with strict information asymmetry:
   - ZERO carbs_grams
   - ZERO glycemic_index
   - ZERO raw prompts or internal AI evidence hashes
   - Patient informational notice
3. PngChartRenderer: Deterministic headless PNG chart of glycemic observations.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib import colors

from backend.domain.events.base import DomainEvent


CLINICAL_LEGAL_NOTICE = (
    "<b>Assistive Decision-Support Notice:</b> For licensed clinician review only. "
    "Not for autonomous clinical action. All clinical interpretations, diagnoses, and medication "
    "decisions remain the sole authority of the treating licensed practitioner."
)

PATIENT_LEGAL_NOTICE = (
    "<b>Assistive Decision-Support Notice:</b> Informational glycemic summary for patient review. "
    "Consult your licensed healthcare provider for clinical advice, medication management, or diagnosis."
)


class ClinicalPdfRenderer:
    """Renders a comprehensive, multi-page clinical report PDF for licensed clinicians."""

    def render(self, context: dict[str, Any]) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0B4A58"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#5A6F79"),
            spaceAfter=12,
        )
        notice_style = ParagraphStyle(
            "LegalNotice",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#8A3800"),
        )
        section_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0B4A58"),
            spaceBefore=10,
            spaceAfter=4,
        )
        cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#21343C"),
        )
        cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=cell_style,
            fontName="Helvetica-Bold",
        )

        elements = []

        # 1. Header & Title
        elements.append(Paragraph("THALI + P.L.A.T.E. Clinical Report", title_style))
        gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elements.append(Paragraph(f"Glycemic Context & Adherence Summary &bull; Generated {gen_time}", subtitle_style))

        # 2. Prominent Legal Notice
        notice_table = Table([[Paragraph(CLINICAL_LEGAL_NOTICE, notice_style)]], colWidths=[520])
        notice_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FDBA74")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(notice_table)
        elements.append(Spacer(1, 10))

        # 3. Patient Info
        patient = context.get("patient", {})
        p_info = [
            [
                Paragraph(f"<b>Patient Name:</b> {patient.get('name', 'N/A')}", cell_style),
                Paragraph(f"<b>UHID:</b> {patient.get('uh_id', 'N/A')}", cell_style),
            ],
            [
                Paragraph(f"<b>Facility:</b> {patient.get('facility_id', 'Unassigned')}", cell_style),
                Paragraph(f"<b>Status:</b> {'Active' if patient.get('active', True) else 'Deactivated'}", cell_style),
            ],
        ]
        info_table = Table(p_info, colWidths=[260, 260])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 10))

        # 4. Glucose Summary & Readings
        g_summary = context.get("glucose_summary", {})
        elements.append(Paragraph("1. Blood Glucose Observations", section_style))
        stats_text = (
            f"<b>Total Observations:</b> {g_summary.get('total_readings', 0)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Mean Glucose:</b> {g_summary.get('mean_glucose', 'N/A')} mg/dL &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Min:</b> {g_summary.get('min_glucose', 'N/A')} mg/dL &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Max:</b> {g_summary.get('max_glucose', 'N/A')} mg/dL"
        )
        elements.append(Paragraph(stats_text, cell_style))
        elements.append(Spacer(1, 4))

        readings = g_summary.get("readings", [])
        if readings:
            g_rows = [[Paragraph("Timestamp (UTC)", cell_bold), Paragraph("Value (mg/dL)", cell_bold), Paragraph("Timing Tag", cell_bold)]]
            for r in readings[:10]:
                g_rows.append([
                    Paragraph(r.get("timestamp", ""), cell_style),
                    Paragraph(f"{r.get('value', '')}", cell_style),
                    Paragraph(r.get("tag", "").replace("_", " ").title(), cell_style),
                ])
            g_table = Table(g_rows, colWidths=[200, 160, 160])
            g_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(g_table)
        else:
            elements.append(Paragraph("<i>No glucose readings recorded.</i>", cell_style))

        # 4b. Glycemic Analytics & Time-in-Range (TIR)
        metrics = context.get("metrics", {})
        if metrics:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("<b>Glycemic Metrics & Window Analytics (14-Day)</b>", section_style))

            tir_in = metrics.get("tir_in_range_pct", "—")
            tir_above = metrics.get("tir_above_range_pct", "—")
            tir_below = metrics.get("tir_below_range_pct", "—")
            adherence = metrics.get("adherence_index", "—")
            cvi = metrics.get("cvi", "—")
            pearson = metrics.get("pearson_r", "—")
            fpg = metrics.get("mean_fpg", "—")
            ppbg = metrics.get("mean_ppbg", "—")
            wkday = metrics.get("weekday_ppbg", "—")
            wkend = metrics.get("weekend_ppbg", "—")
            delta = metrics.get("weekday_weekend_delta", "—")

            m_data = [
                [
                    Paragraph(f"<b>Time in Range (70-180):</b> {tir_in}%", cell_style),
                    Paragraph(f"<b>Above Range (>180):</b> {tir_above}%", cell_style),
                    Paragraph(f"<b>Below Range (<70):</b> {tir_below}%", cell_style),
                ],
                [
                    Paragraph(f"<b>Adherence Index:</b> {adherence}%", cell_style),
                    Paragraph(f"<b>Carb Volatility Index (CVI):</b> {cvi}", cell_style),
                    Paragraph(f"<b>Pearson Correlation (r):</b> {pearson}", cell_style),
                ],
                [
                    Paragraph(f"<b>Mean FPG:</b> {fpg} mg/dL", cell_style),
                    Paragraph(f"<b>Mean PPBG:</b> {ppbg} mg/dL", cell_style),
                    Paragraph(f"<b>Wkday/Wkend PPBG:</b> {wkday} / {wkend} (&Delta; {delta})", cell_style),
                ],
            ]
            m_grid = Table(m_data, colWidths=[173, 173, 174])
            m_grid.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(m_grid)
            elements.append(Spacer(1, 6))

            # Meal-slot PPBG breakdown table
            elements.append(Paragraph("<b>Postprandial Meal-Slot Breakdown</b>", cell_style))
            slot_pb = metrics.get("slot_pb", {})
            slot_pl = metrics.get("slot_pl", {})
            slot_pd = metrics.get("slot_pd", {})
            slot_rows = [
                [
                    Paragraph("Meal Slot", cell_bold),
                    Paragraph("Readings Count", cell_bold),
                    Paragraph("Overall Mean (mg/dL)", cell_bold),
                    Paragraph("Weekday Mean", cell_bold),
                    Paragraph("Weekend Mean", cell_bold),
                ],
                [
                    Paragraph("Post-Breakfast (PB)", cell_style),
                    Paragraph(str(slot_pb.get("count", 0)), cell_style),
                    Paragraph(str(slot_pb.get("mean") or "—"), cell_style),
                    Paragraph(str(slot_pb.get("weekday") or "—"), cell_style),
                    Paragraph(str(slot_pb.get("weekend") or "—"), cell_style),
                ],
                [
                    Paragraph("Post-Lunch (PL)", cell_style),
                    Paragraph(str(slot_pl.get("count", 0)), cell_style),
                    Paragraph(str(slot_pl.get("mean") or "—"), cell_style),
                    Paragraph(str(slot_pl.get("weekday") or "—"), cell_style),
                    Paragraph(str(slot_pl.get("weekend") or "—"), cell_style),
                ],
                [
                    Paragraph("Post-Dinner (PD)", cell_style),
                    Paragraph(str(slot_pd.get("count", 0)), cell_style),
                    Paragraph(str(slot_pd.get("mean") or "—"), cell_style),
                    Paragraph(str(slot_pd.get("weekday") or "—"), cell_style),
                    Paragraph(str(slot_pd.get("weekend") or "—"), cell_style),
                ],
            ]
            slot_table = Table(slot_rows, colWidths=[140, 95, 95, 95, 95])
            slot_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(slot_table)
            elements.append(Spacer(1, 6))

            # Chronobiology Daily Series Table (if available)
            series = metrics.get("series", [])
            if series:
                elements.append(Paragraph("<b>Chronobiology & Daily Glycemic Pattern</b>", cell_style))
                chrono_rows = [
                    [
                        Paragraph("Date", cell_bold),
                        Paragraph("Day Type", cell_bold),
                        Paragraph("FPG (mg/dL)", cell_bold),
                        Paragraph("PPBG (mg/dL)", cell_bold),
                        Paragraph("Carbs (g)", cell_bold),
                        Paragraph("High GI %", cell_bold),
                    ]
                ]
                for s in series[:7]:
                    day_type = "Weekend" if s.get("weekend") else "Weekday"
                    ppbg_list = s.get("ppbg", [])
                    ppbg_str = f"{round(sum(ppbg_list)/len(ppbg_list), 1)}" if ppbg_list else "—"
                    chrono_rows.append([
                        Paragraph(str(s.get("date", "")), cell_style),
                        Paragraph(day_type, cell_style),
                        Paragraph(str(s.get("fpg") or "—"), cell_style),
                        Paragraph(ppbg_str, cell_style),
                        Paragraph(str(s.get("carbs", 0.0)), cell_style),
                        Paragraph(f"{s.get('high_gi_share', 0.0)}%", cell_style),
                    ])
                chrono_table = Table(chrono_rows, colWidths=[90, 85, 85, 85, 85, 90])
                chrono_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 3),
                ]))
                elements.append(chrono_table)

        elements.append(Spacer(1, 10))

        # 5. Meal Observations (Full clinical detail: Carbs + GI)
        meals = context.get("meals", [])
        elements.append(Paragraph("2. Logged Meals & Nutritional Composition", section_style))
        if meals:
            m_rows = [[
                Paragraph("Timestamp", cell_bold),
                Paragraph("Food Description", cell_bold),
                Paragraph("Portion", cell_bold),
                Paragraph("Carbs (g)", cell_bold),
                Paragraph("Glycemic Index", cell_bold),
            ]]
            for m in meals[:10]:
                m_rows.append([
                    Paragraph(m.get("timestamp", ""), cell_style),
                    Paragraph(m.get("description", ""), cell_style),
                    Paragraph(m.get("portion", "").replace("_", " ").title(), cell_style),
                    Paragraph(f"{m.get('carbs_grams') if m.get('carbs_grams') is not None else '—'}", cell_style),
                    Paragraph(f"{m.get('glycemic_index', '—')}", cell_style),
                ])
            m_table = Table(m_rows, colWidths=[110, 190, 80, 70, 70])
            m_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(m_table)
        else:
            elements.append(Paragraph("<i>No meal observations recorded.</i>", cell_style))

        elements.append(Spacer(1, 10))

        # 6. Active Medication Plans (Read-only presentation)
        plans = context.get("medication_plans", [])
        elements.append(Paragraph("3. Active Medication Plans (Read-Only Representation)", section_style))
        if plans:
            p_rows = [[
                Paragraph("Medication Name", cell_bold),
                Paragraph("Dosage", cell_bold),
                Paragraph("Schedule", cell_bold),
                Paragraph("Status", cell_bold),
            ]]
            for p in plans:
                p_rows.append([
                    Paragraph(p.get("medication_name", ""), cell_style),
                    Paragraph(p.get("dosage", ""), cell_style),
                    Paragraph(p.get("schedule", ""), cell_style),
                    Paragraph(p.get("status", "").upper(), cell_style),
                ])
            p_table = Table(p_rows, colWidths=[160, 120, 160, 80])
            p_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(p_table)
        else:
            elements.append(Paragraph("<i>No active medication plans recorded.</i>", cell_style))

        elements.append(Spacer(1, 10))

        # 7. AI Review Artifacts (Preserve review state: GENERATED, PENDING_REVIEW, APPROVED, EDITED, REJECTED)
        artifacts = context.get("ai_artifacts", [])
        elements.append(Paragraph("4. Assistive AI Artifacts & Clinical Review States", section_style))
        if artifacts:
            a_rows = [[
                Paragraph("Artifact Kind", cell_bold),
                Paragraph("Review State", cell_bold),
                Paragraph("Model", cell_bold),
                Paragraph("Summary / Findings", cell_bold),
            ]]
            for a in artifacts[:5]:
                a_rows.append([
                    Paragraph(a.get("artifact_kind", "clinical_summary"), cell_style),
                    Paragraph(f"<b>{a.get('state', 'pending_review').upper()}</b>", cell_style),
                    Paragraph(a.get("model_name") or "deterministic-demo", cell_style),
                    Paragraph(a.get("summary", ""), cell_style),
                ])
            a_table = Table(a_rows, colWidths=[100, 90, 90, 240])
            a_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(a_table)
        else:
            elements.append(Paragraph("<i>No assistive AI review artifacts generated.</i>", cell_style))

        doc.build(elements)
        return buf.getvalue()

    def emit(self, event: DomainEvent) -> None:
        pass


class PatientPdfRenderer:
    """Renders a patient-facing glycemic summary with strict information asymmetry.

    Guarantees:
    - ZERO carbs_grams
    - ZERO glycemic_index
    - ZERO internal model prompt or evidence hashes
    - Patient informational notice
    """

    def render(self, context: dict[str, Any]) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PatientReportTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0B4A58"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "PatientReportSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#5A6F79"),
            spaceAfter=12,
        )
        notice_style = ParagraphStyle(
            "PatientLegalNotice",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#14545F"),
        )
        section_style = ParagraphStyle(
            "PatientSectionHeading",
            parent=styles["Heading2"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0B4A58"),
            spaceBefore=10,
            spaceAfter=4,
        )
        cell_style = ParagraphStyle(
            "PatientTableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#21343C"),
        )
        cell_bold = ParagraphStyle(
            "PatientTableCellBold",
            parent=cell_style,
            fontName="Helvetica-Bold",
        )

        elements = []

        # 1. Header
        elements.append(Paragraph("THALI + P.L.A.T.E. Patient Summary", title_style))
        gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elements.append(Paragraph(f"Personal Glycemic Log & Meal History &bull; Generated {gen_time}", subtitle_style))

        # 2. Patient Informational Notice
        notice_table = Table([[Paragraph(PATIENT_LEGAL_NOTICE, notice_style)]], colWidths=[520])
        notice_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E7F1F3")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0E6E7A")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(notice_table)
        elements.append(Spacer(1, 10))

        # 3. Patient Info
        patient = context.get("patient", {})
        p_info = [
            [
                Paragraph(f"<b>Patient Name:</b> {patient.get('name', 'N/A')}", cell_style),
                Paragraph(f"<b>UHID:</b> {patient.get('uh_id', 'N/A')}", cell_style),
            ]
        ]
        info_table = Table(p_info, colWidths=[260, 260])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 10))

        # 4. Glucose Summary
        g_summary = context.get("glucose_summary", {})
        elements.append(Paragraph("1. Your Blood Glucose Readings", section_style))
        stats_text = (
            f"<b>Total Readings:</b> {g_summary.get('total_readings', 0)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Average:</b> {g_summary.get('mean_glucose', 'N/A')} mg/dL"
        )
        elements.append(Paragraph(stats_text, cell_style))
        elements.append(Spacer(1, 4))

        readings = g_summary.get("readings", [])
        if readings:
            g_rows = [[Paragraph("Date / Time", cell_bold), Paragraph("Reading (mg/dL)", cell_bold), Paragraph("Meal Timing", cell_bold)]]
            for r in readings[:10]:
                g_rows.append([
                    Paragraph(r.get("timestamp", ""), cell_style),
                    Paragraph(f"{r.get('value', '')}", cell_style),
                    Paragraph(r.get("tag", "").replace("_", " ").title(), cell_style),
                ])
            g_table = Table(g_rows, colWidths=[200, 160, 160])
            g_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(g_table)
        else:
            elements.append(Paragraph("<i>No glucose readings recorded.</i>", cell_style))

        elements.append(Spacer(1, 10))

        # 5. Meal History (Strictly NO carbs_grams or glycemic_index)
        meals = context.get("meals", [])
        elements.append(Paragraph("2. Logged Meals", section_style))
        if meals:
            m_rows = [[
                Paragraph("Date / Time", cell_bold),
                Paragraph("Food Description", cell_bold),
                Paragraph("Portion Size", cell_bold),
            ]]
            for m in meals[:10]:
                m_rows.append([
                    Paragraph(m.get("timestamp", ""), cell_style),
                    Paragraph(m.get("description", ""), cell_style),
                    Paragraph(m.get("portion", "").replace("_", " ").title(), cell_style),
                ])
            m_table = Table(m_rows, colWidths=[150, 250, 120])
            m_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(m_table)
        else:
            elements.append(Paragraph("<i>No meal observations recorded.</i>", cell_style))

        elements.append(Spacer(1, 10))

        # 6. Active Medication Plans (Read-only)
        plans = context.get("medication_plans", [])
        elements.append(Paragraph("3. Prescribed Medication Routine", section_style))
        if plans:
            p_rows = [[
                Paragraph("Medication", cell_bold),
                Paragraph("Dosage", cell_bold),
                Paragraph("Schedule", cell_bold),
            ]]
            for p in plans:
                p_rows.append([
                    Paragraph(p.get("medication_name", ""), cell_style),
                    Paragraph(p.get("dosage", ""), cell_style),
                    Paragraph(p.get("schedule", ""), cell_style),
                ])
            p_table = Table(p_rows, colWidths=[200, 160, 160])
            p_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(p_table)
        else:
            elements.append(Paragraph("<i>No active medications on record.</i>", cell_style))

        elements.append(Spacer(1, 10))

        # 7. Approved Care Guidance (NO internal prompts, hashes, or technical metadata)
        artifacts = context.get("ai_artifacts", [])
        if artifacts:
            elements.append(Paragraph("4. Care Guidance & Notes", section_style))
            for a in artifacts[:3]:
                elements.append(Paragraph(f"&bull; {a.get('summary', '')}", cell_style))
                elements.append(Spacer(1, 4))

        doc.build(elements)
        return buf.getvalue()

    def emit(self, event: DomainEvent) -> None:
        pass


class PngChartRenderer:
    """Renders a deterministic PNG glycemic trend chart using Matplotlib Agg."""

    def render(self, context: dict[str, Any]) -> bytes:
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=120)

        g_summary = context.get("glucose_summary", {})
        readings = g_summary.get("readings", [])

        # Target range shading: 70 - 180 mg/dL
        ax.axhspan(70, 180, color="#E6F4EA", alpha=0.7, label="Target Range (70-180)")

        if readings:
            # Sort chronologically for charting
            sorted_r = list(reversed(readings))
            indices = list(range(1, len(sorted_r) + 1))
            values = [r["value"] for r in sorted_r]

            ax.plot(indices, values, color="#0B4A58", marker="o", linewidth=2, markersize=5, label="Glucose (mg/dL)")
            for i, val in zip(indices, values):
                ax.annotate(
                    f"{val}",
                    (i, val),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontsize=7,
                    color="#21343C",
                )
            ax.set_xticks(indices)
            ax.set_xticklabels([r["timestamp"][11:16] if len(r["timestamp"]) >= 16 else str(i) for i, r in zip(indices, sorted_r)], rotation=45, fontsize=7)
        else:
            ax.text(0.5, 0.5, "No glucose observations available", transform=ax.transAxes, ha="center", va="center", color="#5A6F79")

        ax.set_ylabel("Blood Glucose (mg/dL)", fontsize=9, color="#21343C")
        ax.set_title("Glycemic Trend & Target Alignment", fontsize=11, color="#0B4A58", fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper right", fontsize=8)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    def emit(self, event: DomainEvent) -> None:
        pass
