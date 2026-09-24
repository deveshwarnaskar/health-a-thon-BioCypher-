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
    Image,
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

        cs = context.get("clinical_state") or {}
        patient = cs.get("patient_summary") or context.get("patient", {})
        data_quality = cs.get("data_quality") or {}
        glycemic = cs.get("glycemic_metrics") or {}
        longitudinal = cs.get("longitudinal_comparison") or {}
        patterns = cs.get("temporal_patterns") or {}
        meal_assocs = cs.get("meal_associations") or []
        lab_profile = cs.get("laboratory_profile") or {}
        cardio_profile = cs.get("cardiometabolic_profile") or {}
        screenings = cs.get("complication_screenings") or []
        med_timeline = cs.get("medication_timeline") or []
        events_timeline = cs.get("clinical_events_timeline") or []
        ai_interp = cs.get("ai_interpretation") or {}
        engine_meta = cs.get("engine_metadata") or {}

        # -------------------------------------------------------------
        # 1. Clinic/Facility Header
        # -------------------------------------------------------------
        facility_str = patient.get("facility_id") or "Central Diabetes Care Center"
        gen_time = engine_meta.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elements.append(Paragraph("THALI × P.L.A.T.E. Clinical Analytics & Evaluation Report", title_style))
        elements.append(Paragraph(f"Facility: <b>{facility_str}</b> &bull; Report Generated: <b>{gen_time}</b>", subtitle_style))

        # -------------------------------------------------------------
        # 2. Patient Demographic Block
        # -------------------------------------------------------------
        elements.append(Paragraph("1. Patient Identification & Care Team", section_style))
        care_team_str = ", ".join([c.get("clinician_name", "Doctor") for c in patient.get("care_team", [])]) or "Primary Care Clinician"
        p_info = [
            [
                Paragraph(f"<b>Patient Name:</b> {patient.get('name', 'N/A')}", cell_style),
                Paragraph(f"<b>UHID:</b> {patient.get('uh_id', 'N/A')}", cell_style),
            ],
            [
                Paragraph(f"<b>Care Team:</b> {care_team_str}", cell_style),
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
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 3. Reporting Period & Data Completeness
        # -------------------------------------------------------------
        elements.append(Paragraph("2. Reporting Period & Data Completeness (Quality Gate)", section_style))
        w_days = data_quality.get("window_days", 14)
        cov_pct = data_quality.get("coverage_pct", 0.0)
        valid_n = data_quality.get("total_valid_readings", 0)
        exp_n = data_quality.get("expected_readings", w_days * 3)
        act_days = data_quality.get("active_logging_days", 0)
        missing_count = data_quality.get("missing_days_count", 0)
        last_sync = data_quality.get("last_sync") or "N/A"
        sources_str = ", ".join(data_quality.get("data_sources", ["SMBG"])) or "SMBG"

        dq_rows = [
            [
                Paragraph(f"<b>Reporting Window:</b> {w_days} Days", cell_style),
                Paragraph(f"<b>Valid Readings:</b> {valid_n} (Expected: {exp_n})", cell_style),
                Paragraph(f"<b>Active Logging Days:</b> {act_days} / {w_days}", cell_style),
            ],
            [
                Paragraph(f"<b>Data Coverage:</b> {cov_pct}% ({'Adequate' if data_quality.get('is_adequate_coverage', True) else 'Suboptimal'})", cell_style),
                Paragraph(f"<b>Missing Days:</b> {missing_count} days", cell_style),
                Paragraph(f"<b>Data Sources:</b> {sources_str}", cell_style),
            ],
        ]
        dq_table = Table(dq_rows, colWidths=[173, 173, 174])
        dq_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(dq_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 4. Glycemic Metrics (TIR, TAR, TBR, Mean, CV, GMI, eAG)
        # -------------------------------------------------------------
        elements.append(Paragraph("3. Authoritative Glycemic Summary Metrics (Deterministic)", section_style))
        mean_g = glycemic.get("mean_glucose")
        med_g = glycemic.get("median_glucose")
        min_g = glycemic.get("min_glucose")
        max_g = glycemic.get("max_glucose")
        sd_g = glycemic.get("standard_deviation")
        cv_g = glycemic.get("coefficient_of_variation_pct")
        gmi_g = glycemic.get("gmi_pct")
        eag_g = glycemic.get("estimated_a1c_pct")
        var_cat = glycemic.get("variability_category") or "INSUFFICIENT_DATA"

        gm_data = [
            [
                Paragraph(f"<b>Mean Glucose:</b> {mean_g if mean_g is not None else '—'} mg/dL", cell_style),
                Paragraph(f"<b>Median Glucose:</b> {med_g if med_g is not None else '—'} mg/dL", cell_style),
                Paragraph(f"<b>Range (Min / Max):</b> {min_g or '—'} / {max_g or '—'} mg/dL", cell_style),
            ],
            [
                Paragraph(f"<b>Standard Deviation:</b> &plusmn;{sd_g if sd_g is not None else '—'} mg/dL", cell_style),
                Paragraph(f"<b>Coefficient of Variation (CV):</b> {cv_g if cv_g is not None else '—'}% (Target &le; 36%)", cell_style),
                Paragraph(f"<b>Variability Status:</b> <b>{var_cat}</b>", cell_style),
            ],
            [
                Paragraph(f"<b>Glucose Management Indicator (GMI):</b> {gmi_g if gmi_g is not None else '—'}%", cell_style),
                Paragraph(f"<b>Estimated A1c (eAG):</b> {eag_g if eag_g is not None else '—'}%", cell_style),
                Paragraph(f"<b>Dawn Phenomenon:</b> {'Suspected' if glycemic.get('dawn_phenomenon_suspected') else 'Not Detected'}", cell_style),
            ],
        ]
        gm_table = Table(gm_data, colWidths=[173, 173, 174])
        gm_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(gm_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 5. Glucose Visualizations / Trend Plot
        # -------------------------------------------------------------
        elements.append(Paragraph("4. Glycemic Longitudinal Trend & Target Range Shading", section_style))
        try:
            chart_renderer = PngChartRenderer()
            chart_bytes = chart_renderer.render(context)
            if chart_bytes:
                elements.append(Image(io.BytesIO(chart_bytes), width=480, height=180))
                elements.append(Spacer(1, 6))
        except Exception:
            elements.append(Paragraph("<i>Visual trend plot unavailable for this observation set.</i>", cell_style))

        # -------------------------------------------------------------
        # 6. Time in Range Breakdown
        # -------------------------------------------------------------
        elements.append(Paragraph("5. Time-in-Range (TIR) Breakdown (Consensus Targets)", section_style))
        tir_p = glycemic.get("tir_in_range_pct")
        tar_p = glycemic.get("tar_above_range_pct")
        tar_l2 = glycemic.get("tar_level2_pct")
        tbr_p = glycemic.get("tbr_below_range_pct")
        tbr_l2 = glycemic.get("tbr_level2_pct")

        tir_rows = [
            [
                Paragraph("Glycemic Range Zone", cell_bold),
                Paragraph("Threshold Definition", cell_bold),
                Paragraph("Observed %", cell_bold),
                Paragraph("Consensus Clinical Target", cell_bold),
            ],
            [
                Paragraph("<b>Time in Range (TIR)</b>", cell_style),
                Paragraph("70 - 180 mg/dL", cell_style),
                Paragraph(f"{tir_p if tir_p is not None else '—'}%", cell_style),
                Paragraph("&ge; 70% (&gt; 16h 48m daily)", cell_style),
            ],
            [
                Paragraph("Time Above Range (TAR L1)", cell_style),
                Paragraph("181 - 250 mg/dL", cell_style),
                Paragraph(f"{tar_p if tar_p is not None else '—'}%", cell_style),
                Paragraph("&lt; 25% (&lt; 6h daily)", cell_style),
            ],
            [
                Paragraph("Time Above Range (TAR L2 - Very High)", cell_style),
                Paragraph("&gt; 250 mg/dL", cell_style),
                Paragraph(f"{tar_l2 if tar_l2 is not None else '—'}%", cell_style),
                Paragraph("&lt; 5% (&lt; 1h 12m daily)", cell_style),
            ],
            [
                Paragraph("Time Below Range (TBR L1 - Hypoglycemia)", cell_style),
                Paragraph("54 - 69 mg/dL", cell_style),
                Paragraph(f"{tbr_p if tbr_p is not None else '—'}%", cell_style),
                Paragraph("&lt; 4% (&lt; 1h daily)", cell_style),
            ],
            [
                Paragraph("Time Below Range (TBR L2 - Severe Hypoglycemia)", cell_style),
                Paragraph("&lt; 54 mg/dL", cell_style),
                Paragraph(f"{tbr_l2 if tbr_l2 is not None else '—'}%", cell_style),
                Paragraph("&lt; 1% (&lt; 15m daily)", cell_style),
            ],
        ]
        tir_table = Table(tir_rows, colWidths=[150, 120, 110, 140])
        tir_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(tir_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 7. Pattern Analysis Summary
        # -------------------------------------------------------------
        elements.append(Paragraph("6. Diurnal & Time-Slot Pattern Analysis", section_style))
        morn = patterns.get("morning", {})
        aft = patterns.get("afternoon", {})
        eve = patterns.get("evening", {})
        overn = patterns.get("overnight", {})

        pat_rows = [
            [
                Paragraph("Time Slot", cell_bold),
                Paragraph("Hours Window", cell_bold),
                Paragraph("Readings Count", cell_bold),
                Paragraph("Mean Glucose", cell_bold),
                Paragraph("Pattern Observation", cell_bold),
            ],
            [
                Paragraph("Morning", cell_style),
                Paragraph("06:00 - 12:00", cell_style),
                Paragraph(str(morn.get("count", 0)), cell_style),
                Paragraph(f"{morn.get('mean_glucose') or '—'} mg/dL", cell_style),
                Paragraph(morn.get("pattern_note", "Stable fasting / morning profile."), cell_style),
            ],
            [
                Paragraph("Afternoon", cell_style),
                Paragraph("12:00 - 17:00", cell_style),
                Paragraph(str(aft.get("count", 0)), cell_style),
                Paragraph(f"{aft.get('mean_glucose') or '—'} mg/dL", cell_style),
                Paragraph(aft.get("pattern_note", "Post-lunch glycemic range."), cell_style),
            ],
            [
                Paragraph("Evening", cell_style),
                Paragraph("17:00 - 22:00", cell_style),
                Paragraph(str(eve.get("count", 0)), cell_style),
                Paragraph(f"{eve.get('mean_glucose') or '—'} mg/dL", cell_style),
                Paragraph(eve.get("pattern_note", "Dinner interval profile."), cell_style),
            ],
            [
                Paragraph("Overnight", cell_style),
                Paragraph("22:00 - 06:00", cell_style),
                Paragraph(str(overn.get("count", 0)), cell_style),
                Paragraph(f"{overn.get('mean_glucose') or '—'} mg/dL", cell_style),
                Paragraph(overn.get("pattern_note", "Basal / nocturnal glycemic state."), cell_style),
            ],
        ]
        pat_table = Table(pat_rows, colWidths=[75, 85, 75, 85, 200])
        pat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(pat_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 8. Meal-Glucose Temporal Insights
        # -------------------------------------------------------------
        elements.append(Paragraph("7. Meal ↔ Glucose Temporal Associations (Non-Causal Evidence)", section_style))
        if meal_assocs:
            ma_rows = [
                [
                    Paragraph("Meal Timestamp", cell_bold),
                    Paragraph("Food Description", cell_bold),
                    Paragraph("Pre-Meal", cell_bold),
                    Paragraph("Post Peak", cell_bold),
                    Paragraph("Delta", cell_bold),
                    Paragraph("Time to Peak", cell_bold),
                ]
            ]
            for ma in meal_assocs[:6]:
                delta_val = ma.get("observed_delta_mg_dl")
                delta_str = f"+{delta_val}" if delta_val is not None and delta_val > 0 else (str(delta_val) if delta_val is not None else "—")
                ma_rows.append([
                    Paragraph(str(ma.get("meal_timestamp", ""))[:16].replace("T", " "), cell_style),
                    Paragraph(str(ma.get("description", "Meal")), cell_style),
                    Paragraph(f"{ma.get('pre_meal_glucose_mg_dl') or '—'}", cell_style),
                    Paragraph(f"{ma.get('post_meal_peak_mg_dl') or '—'}", cell_style),
                    Paragraph(f"{delta_str} mg/dL", cell_style),
                    Paragraph(f"{ma.get('time_to_peak_minutes') or '—'} min", cell_style),
                ])
            ma_table = Table(ma_rows, colWidths=[95, 145, 70, 70, 70, 70])
            ma_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(ma_table)
        else:
            elements.append(Paragraph("<i>No meal-associated glucose excursions recorded in this window.</i>", cell_style))
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 9. Longitudinal Glycemic Comparison Table
        # -------------------------------------------------------------
        elements.append(Paragraph("8. Longitudinal Glycemic Comparison (Current vs Preceding Window)", section_style))
        has_hist = longitudinal.get("has_sufficient_history", False)
        tir_comp = longitudinal.get("tir_comparison", {})
        mean_comp = longitudinal.get("mean_comparison", {})
        cv_comp = longitudinal.get("cv_comparison", {})
        gmi_comp = longitudinal.get("gmi_comparison", {})

        long_rows = [
            [
                Paragraph("Glycemic Metric", cell_bold),
                Paragraph(f"Current ({w_days}d)", cell_bold),
                Paragraph(f"Preceding ({w_days}d)", cell_bold),
                Paragraph("Observed Delta (&Delta;)", cell_bold),
                Paragraph("Longitudinal Trend", cell_bold),
            ],
            [
                Paragraph("Time in Range (70-180)", cell_style),
                Paragraph(f"{tir_comp.get('current_value') or '—'}%", cell_style),
                Paragraph(f"{tir_comp.get('previous_value') or '—'}%", cell_style),
                Paragraph(f"{tir_comp.get('delta') or '—'}", cell_style),
                Paragraph(str(tir_comp.get("trend_direction", "insufficient_data")).upper(), cell_style),
            ],
            [
                Paragraph("Mean Glucose (mg/dL)", cell_style),
                Paragraph(f"{mean_comp.get('current_value') or '—'}", cell_style),
                Paragraph(f"{mean_comp.get('previous_value') or '—'}", cell_style),
                Paragraph(f"{mean_comp.get('delta') or '—'}", cell_style),
                Paragraph(str(mean_comp.get("trend_direction", "insufficient_data")).upper(), cell_style),
            ],
            [
                Paragraph("Coefficient of Variation (CV %)", cell_style),
                Paragraph(f"{cv_comp.get('current_value') or '—'}%", cell_style),
                Paragraph(f"{cv_comp.get('previous_value') or '—'}%", cell_style),
                Paragraph(f"{cv_comp.get('delta') or '—'}", cell_style),
                Paragraph(str(cv_comp.get("trend_direction", "insufficient_data")).upper(), cell_style),
            ],
            [
                Paragraph("Glucose Management Indicator (GMI %)", cell_style),
                Paragraph(f"{gmi_comp.get('current_value') or '—'}%", cell_style),
                Paragraph(f"{gmi_comp.get('previous_value') or '—'}%", cell_style),
                Paragraph(f"{gmi_comp.get('delta') or '—'}", cell_style),
                Paragraph(str(gmi_comp.get("trend_direction", "insufficient_data")).upper(), cell_style),
            ],
        ]
        long_table = Table(long_rows, colWidths=[160, 90, 90, 80, 100])
        long_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(long_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 10. Laboratory Snapshot (HbA1c, eGFR, Creatinine, UACR, Lipids)
        # -------------------------------------------------------------
        elements.append(Paragraph("9. Laboratory Biomarker Profile & Nephrology Markers", section_style))
        hba1c_latest = (lab_profile.get("hba1c") or {}).get("latest") or {}
        creat_latest = (lab_profile.get("creatinine") or {}).get("latest") or {}
        egfr_latest = (lab_profile.get("egfr") or {}).get("latest") or {}
        uacr_latest = (lab_profile.get("uacr") or {}).get("latest") or {}
        lipids = lab_profile.get("lipids") or {}

        lab_rows = [
            [
                Paragraph("Biomarker / Assay", cell_bold),
                Paragraph("Latest Value", cell_bold),
                Paragraph("Unit", cell_bold),
                Paragraph("Standard Reference Target", cell_bold),
                Paragraph("Collection Timestamp", cell_bold),
            ],
            [
                Paragraph("Glycated Hemoglobin (HbA1c)", cell_style),
                Paragraph(str(hba1c_latest.get("value") or "—"), cell_style),
                Paragraph("%", cell_style),
                Paragraph("&lt; 7.0% (individualized)", cell_style),
                Paragraph(str(hba1c_latest.get("observed_at", "—"))[:10], cell_style),
            ],
            [
                Paragraph("Serum Creatinine", cell_style),
                Paragraph(str(creat_latest.get("value") or "—"), cell_style),
                Paragraph("mg/dL", cell_style),
                Paragraph("0.6 - 1.2 mg/dL", cell_style),
                Paragraph(str(creat_latest.get("observed_at", "—"))[:10], cell_style),
            ],
            [
                Paragraph("Estimated GFR (2021 CKD-EPI)", cell_style),
                Paragraph(str(egfr_latest.get("value") or "—"), cell_style),
                Paragraph("mL/min/1.73m2", cell_style),
                Paragraph("&ge; 60 mL/min/1.73m2", cell_style),
                Paragraph(str(egfr_latest.get("source") or "Validated Formula"), cell_style),
            ],
            [
                Paragraph("Urine Albumin-to-Creatinine (uACR)", cell_style),
                Paragraph(str(uacr_latest.get("value") or "—"), cell_style),
                Paragraph("mg/g", cell_style),
                Paragraph("&lt; 30 mg/g (normal)", cell_style),
                Paragraph(str(uacr_latest.get("observed_at", "—"))[:10], cell_style),
            ],
            [
                Paragraph("Lipids: Total Cholesterol / LDL", cell_style),
                Paragraph(f"{(lipids.get('total_cholesterol') or {}).get('value', '—')} / {(lipids.get('ldl') or {}).get('value', '—')}", cell_style),
                Paragraph("mg/dL", cell_style),
                Paragraph("LDL &lt; 70 mg/dL (high risk)", cell_style),
                Paragraph("Lipid Panel", cell_style),
            ],
        ]
        lab_table = Table(lab_rows, colWidths=[150, 75, 75, 120, 100])
        lab_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(lab_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 11. Cardiometabolic Markers (Blood Pressure, Weight)
        # -------------------------------------------------------------
        elements.append(Paragraph("10. Cardiometabolic Markers & Anthropometrics", section_style))
        bp = cardio_profile.get("blood_pressure") or {}
        sys_bp = (bp.get("latest_systolic") or {}).get("value")
        dia_bp = (bp.get("latest_diastolic") or {}).get("value")
        wt = (cardio_profile.get("weight") or {}).get("latest") or {}
        wt_val = wt.get("value")

        cm_rows = [
            [
                Paragraph("Cardiometabolic Parameter", cell_bold),
                Paragraph("Latest Observation", cell_bold),
                Paragraph("Clinical Target", cell_bold),
                Paragraph("Observation Date", cell_bold),
            ],
            [
                Paragraph("Resting Blood Pressure", cell_style),
                Paragraph(f"{int(sys_bp) if sys_bp else '—'} / {int(dia_bp) if dia_bp else '—'} mmHg", cell_style),
                Paragraph("&lt; 130 / 80 mmHg", cell_style),
                Paragraph(str((bp.get("latest_systolic") or {}).get("observed_at", "—"))[:10], cell_style),
            ],
            [
                Paragraph("Body Weight & BMI", cell_style),
                Paragraph(f"{wt_val or '—'} kg", cell_style),
                Paragraph("Individualized BMI &lt; 23 kg/m2 (Asian Indian)", cell_style),
                Paragraph(str(wt.get("observed_at", "—"))[:10], cell_style),
            ],
        ]
        cm_table = Table(cm_rows, colWidths=[160, 120, 140, 100])
        cm_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(cm_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 12. Complication Screening Status
        # -------------------------------------------------------------
        elements.append(Paragraph("11. Preventive Complication Screening Schedule", section_style))
        scr_rows = [
            [
                Paragraph("Preventive Screening Exam", cell_bold),
                Paragraph("Frequency", cell_bold),
                Paragraph("Last Completed", cell_bold),
                Paragraph("Next Due Date", cell_bold),
                Paragraph("Status", cell_bold),
            ]
        ]
        for scr in screenings:
            st = scr.get("status", "NO_RECORD")
            st_color = "#B91C1C" if st == "OVERDUE" else ("#B45309" if st == "DUE_SOON" else "#15803D")
            scr_rows.append([
                Paragraph(scr.get("category", ""), cell_style),
                Paragraph(f"Every {scr.get('interval_months', 12)} mo", cell_style),
                Paragraph(scr.get("last_completed_at") or "No Record", cell_style),
                Paragraph(scr.get("due_date") or "Immediate", cell_style),
                Paragraph(f"<font color='{st_color}'><b>{st}</b></font>", cell_style),
            ])
        scr_table = Table(scr_rows, colWidths=[170, 70, 90, 90, 100])
        scr_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(scr_table)
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 13. Current Medication Regimen & Longitudinal Changes
        # -------------------------------------------------------------
        elements.append(Paragraph("12. Prescribed Pharmacotherapy & Medication Timeline", section_style))
        plans = med_timeline or context.get("medication_plans", [])
        if plans:
            p_rows = [[
                Paragraph("Medication Name", cell_bold),
                Paragraph("Instruction / Dosage", cell_bold),
                Paragraph("Regimen Status", cell_bold),
                Paragraph("Prescription Date", cell_bold),
            ]]
            for p in plans:
                med_name = p.get("medication") or p.get("medication_name", "")
                inst = p.get("dosage_instruction") or p.get("dosage") or p.get("instruction", "")
                st = p.get("status", "active").upper()
                s_date = str(p.get("start_date", "—"))[:10]
                p_rows.append([
                    Paragraph(med_name, cell_style),
                    Paragraph(inst, cell_style),
                    Paragraph(st, cell_style),
                    Paragraph(s_date, cell_style),
                ])
            p_table = Table(p_rows, colWidths=[160, 180, 80, 100])
            p_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(p_table)
        else:
            elements.append(Paragraph("<i>No prescribed medication plans recorded.</i>", cell_style))
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 14. Patient Timeline Summary
        # -------------------------------------------------------------
        elements.append(Paragraph("13. Unified Chronological Clinical Timeline (Latest Events)", section_style))
        if events_timeline:
            tl_rows = [[
                Paragraph("Timestamp", cell_bold),
                Paragraph("Category", cell_bold),
                Paragraph("Clinical Event", cell_bold),
                Paragraph("Observation Details", cell_bold),
            ]]
            for ev in events_timeline[:8]:
                tl_rows.append([
                    Paragraph(ev.get("timestamp", "")[:16].replace("T", " "), cell_style),
                    Paragraph(ev.get("category", "").upper(), cell_style),
                    Paragraph(ev.get("title", ""), cell_style),
                    Paragraph(ev.get("detail", ""), cell_style),
                ])
            tl_table = Table(tl_rows, colWidths=[105, 80, 155, 180])
            tl_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B4A58")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(tl_table)
        else:
            elements.append(Paragraph("<i>No timeline events recorded.</i>", cell_style))
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 15. Key Clinical Flags / Identified Glycemic Risks
        # -------------------------------------------------------------
        elements.append(Paragraph("14. Deterministic Clinical Risk Flags & Identified Alerts", section_style))
        alerts = patient.get("clinical_alerts", [])
        if alerts:
            for al in alerts:
                lvl = al.get("level", "INFO")
                msg = al.get("message", "")
                elements.append(Paragraph(f"&bull; <b>[{lvl}]</b> {msg}", cell_style))
                elements.append(Spacer(1, 2))
        else:
            elements.append(Paragraph("<i>No active critical glycemic risk flags detected in this window.</i>", cell_style))
        elements.append(Spacer(1, 6))

        # -------------------------------------------------------------
        # 16. AI-assisted Clinical Summary / Evidence Synthesis
        # -------------------------------------------------------------
        elements.append(Paragraph("15. Downstream AI-Assisted Clinical Summary & Documentation", section_style))
        artifacts = ai_interp.get("summaries") or context.get("ai_artifacts", [])
        if artifacts:
            for a in artifacts[:3]:
                st_val = a.get("state", "approved")
                sum_text = a.get("summary", "")
                model = a.get("model_name") or "sarvam_ai"
                elements.append(Paragraph(f"&bull; <b>[{st_val.upper()} | {model}]</b> {sum_text}", cell_style))
                elements.append(Spacer(1, 3))
        else:
            elements.append(Paragraph("<i>No assistive AI clinical summary generated for this period.</i>", cell_style))
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 17. Clinician Notes Section
        # -------------------------------------------------------------
        elements.append(Paragraph("16. Attending Clinician Notes & Evaluation Plan", section_style))
        note_box = Table(
            [[Paragraph("<b>Clinician Impression & Therapeutic Adjustments:</b><br/><br/><br/><br/>", cell_style)]],
            colWidths=[520],
        )
        note_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(note_box)
        elements.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 18. Attending Clinician Signature Block
        # -------------------------------------------------------------
        elements.append(Paragraph("17. Clinician Verification & Signature", section_style))
        sig_data = [
            [
                Paragraph("<b>Attending Clinician:</b> ___________________________", cell_style),
                Paragraph("<b>Medical License No.:</b> _______________________", cell_style),
            ],
            [
                Paragraph("<b>Clinician Signature:</b> ___________________________", cell_style),
                Paragraph(f"<b>Review Date:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", cell_style),
            ],
        ]
        sig_table = Table(sig_data, colWidths=[260, 260])
        sig_table.setStyle(TableStyle([
            ("PADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ]))
        elements.append(sig_table)
        elements.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 19. Generation Metadata (Engine version, Timestamp, Provenance)
        # -------------------------------------------------------------
        elements.append(Paragraph("18. Authoritative Engine Metadata & Provenance", section_style))
        eng_ver = engine_meta.get("version") or "2026.1-clinical-deterministic-ada-rssdi"
        meta_text = (
            f"<b>Calculation Engine:</b> {eng_ver} &nbsp;&bull;&nbsp; "
            f"<b>Authoritative Source:</b> Centralized Deterministic Clinical Layer &nbsp;&bull;&nbsp; "
            f"<b>Render Pipeline:</b> Gate 10N Pure ReportLab/Agg"
        )
        elements.append(Paragraph(meta_text, cell_style))
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 20. Clinical Legal Disclaimer & Medical Device Notice
        # -------------------------------------------------------------
        elements.append(Paragraph("19 & 20. Assistive Decision-Support & Medical Disclaimer", section_style))
        notice_table = Table([[Paragraph(CLINICAL_LEGAL_NOTICE, notice_style)]], colWidths=[520])
        notice_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FDBA74")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(notice_table)

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
