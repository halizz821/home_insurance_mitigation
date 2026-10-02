"""Excel exporter for LLM Judge evaluation results with integrated side-by-side table layout."""

from pathlib import Path
import time
from typing import Any, Dict, List
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from evaluation.rubrics import RUBRICS
from evaluation.llm_judge import EvaluationJudgment


def _format_score_cell(cell, score: float):
    """Styles a score cell based on its rating."""
    cell.alignment = Alignment(horizontal="center", vertical="center")
    if score >= 4.0:
        cell.font = Font(name="Calibri", size=12, bold=True, color="006100")
        cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    elif score >= 3.0:
        cell.font = Font(name="Calibri", size=12, bold=True, color="7F6000")
        cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    else:
        cell.font = Font(name="Calibri", size=12, bold=True, color="C00000")
        cell.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")


def export_evaluation_to_excel(
    results: List[Dict[str, Any]],
    output_path: str = "agent_evaluation_results.xlsx",
) -> str:
    """Exports evaluation scores, agent output, ground truth, and rubrics into a 2-sheet styled Excel workbook."""
    wb = openpyxl.Workbook()

    # Base typography and borders
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    super_header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=10, bold=True)
    regular_font = Font(name="Calibri", size=10)

    thin_border_side = Side(style="thin", color="D9D9D9")
    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)
    summary_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    # =========================================================================
    # Group Color Fills for Distinct Header Categories
    # =========================================================================
    # 1. Target Property Info (Dark Slate / Charcoal)
    target_super_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    target_header_fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")

    # 2. Ground Truth Context (Deep Navy / Steel Blue)
    gt_super_fill = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")
    gt_header_fill = PatternFill(start_color="2980B9", end_color="2980B9", fill_type="solid")

    # 3. Agent Evaluated Output (Deep Purple / Royal Violet)
    agent_super_fill = PatternFill(start_color="4A235A", end_color="4A235A", fill_type="solid")
    agent_header_fill = PatternFill(start_color="7D3C98", end_color="7D3C98", fill_type="solid")

    # 4. LLM Judge Evaluation & Justifications (Forest Emerald Green)
    judge_super_fill = PatternFill(start_color="145A32", end_color="145A32", fill_type="solid")
    judge_header_fill = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")

    # 5. Composite Quality Score (Amber / Warm Gold)
    comp_super_fill = PatternFill(start_color="7D6608", end_color="7D6608", fill_type="solid")
    comp_header_fill = PatternFill(start_color="B7950B", end_color="B7950B", fill_type="solid")

    # =========================================================================
    # SHEET 1: Evaluation (Integrated Table: GT + Agent Output + Judge Scores)
    # =========================================================================
    ws_results = wb.active
    ws_results.title = "Evaluation"
    ws_results.views.sheetView[0].showGridLines = True

    # Title Banner
    ws_results.merge_cells("A1:T1")
    title_cell = ws_results["A1"]
    title_cell.value = "Autonomous Insurance Agent Evaluation - Benchmark Ground Truth vs Agent Dispatches vs LLM Judge"
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws_results.row_dimensions[1].height = 28

    # Summary KPI row
    total_evals = len(results)
    avg_faith = sum(r["judgment"].faithfulness_score for r in results) / total_evals if total_evals else 0
    avg_rel = sum(r["judgment"].action_relevance_score for r in results) / total_evals if total_evals else 0
    avg_corr = sum(r["judgment"].action_correctness_score for r in results) / total_evals if total_evals else 0
    avg_clar = sum(r["judgment"].clarity_score for r in results) / total_evals if total_evals else 0
    composite_avg = (avg_faith + avg_rel + avg_corr + avg_clar) / 4.0 if total_evals else 0

    kpi_labels = ["Properties Evaluated", "Avg Faithfulness (1-5)", "Avg Action Relevance (1-5)", "Avg Action Correctness (1-5)", "Avg Clarity (1-5)", "Overall Composite Quality"]
    kpi_values = [total_evals, f"{avg_faith:.2f} / 5.0", f"{avg_rel:.2f} / 5.0", f"{avg_corr:.2f} / 5.0", f"{avg_clar:.2f} / 5.0", f"{composite_avg:.2f} / 5.0"]

    for col_idx, (lbl, val) in enumerate(zip(kpi_labels, kpi_values), start=1):
        cell_lbl = ws_results.cell(row=3, column=col_idx, value=lbl)
        cell_lbl.font = Font(name="Calibri", size=9, bold=True, color="595959")
        cell_lbl.fill = summary_fill
        cell_lbl.alignment = center_align
        cell_lbl.border = cell_border

        cell_val = ws_results.cell(row=4, column=col_idx, value=val)
        cell_val.font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        cell_val.fill = summary_fill
        cell_val.alignment = center_align
        cell_val.border = cell_border

    ws_results.row_dimensions[3].height = 18
    ws_results.row_dimensions[4].height = 24

    # -------------------------------------------------------------------------
    # ROW 5: Category Super-Headers (Colored Visual Bands)
    # -------------------------------------------------------------------------
    super_headers = [
        (1, 3, "TARGET PROPERTY", target_super_fill),
        (4, 7, "GROUND TRUTH CONTEXT (BENCHMARK TRUTH)", gt_super_fill),
        (8, 11, "AGENT OUTPUT (EVALUATED ARTIFACTS)", agent_super_fill),
        (12, 19, "LLM JUDGE EVALUATION & JUSTIFICATIONS", judge_super_fill),
        (20, 20, "COMPOSITE", comp_super_fill),
    ]

    ws_results.row_dimensions[5].height = 24
    for start_c, end_c, title, fill in super_headers:
        if start_c != end_c:
            ws_results.merge_cells(start_row=5, start_column=start_c, end_row=5, end_column=end_c)
        for c in range(start_c, end_c + 1):
            cell = ws_results.cell(row=5, column=c)
            cell.fill = fill
            cell.border = cell_border
        super_cell = ws_results.cell(row=5, column=start_c)
        super_cell.value = title
        super_cell.font = super_header_font
        super_cell.alignment = center_align

    # -------------------------------------------------------------------------
    # ROW 6: Individual Column Headers (Coordinated Category Colors)
    # -------------------------------------------------------------------------
    headers_config = [
        # Target Info (Cols 1-3)
        ("Property ID", target_header_fill),
        ("Policyholder & Address", target_header_fill),
        ("City / Province", target_header_fill),
        # Ground Truth Context (Cols 4-7)
        ("GT Weather Alert & Metrics", gt_header_fill),
        ("GT Dwelling Specifications", gt_header_fill),
        ("GT Policy Coverage & Gaps", gt_header_fill),
        ("Golden Mandatory Actions", gt_header_fill),
        # Agent Evaluated Output (Cols 8-11)
        ("Agent Hazard & Risk Assessment", agent_header_fill),
        ("Agent Proposed Micro-Actions", agent_header_fill),
        ("Agent Dispatched SMS", agent_header_fill),
        ("Agent Push Notification", agent_header_fill),
        # LLM Judge Scores & Justifications (Cols 12-19)
        ("Faithfulness\n(1-5)", judge_header_fill),
        ("Faithfulness Justification", judge_header_fill),
        ("Action Relevance\n(1-5)", judge_header_fill),
        ("Action Relevance Justification", judge_header_fill),
        ("Action Correctness\n(1-5)", judge_header_fill),
        ("Action Correctness Justification", judge_header_fill),
        ("Clarity\n(1-5)", judge_header_fill),
        ("Clarity Justification", judge_header_fill),
        # Composite Score (Col 20)
        ("Composite\nQuality (1-5)", comp_header_fill),
    ]

    ws_results.row_dimensions[6].height = 30
    for col_idx, (header_text, fill) in enumerate(headers_config, start=1):
        cell = ws_results.cell(row=6, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = fill
        cell.alignment = center_align
        cell.border = cell_border

    # -------------------------------------------------------------------------
    # ROW 7+: Data Rows
    # -------------------------------------------------------------------------
    current_row = 7
    for r in results:
        j: EvaluationJudgment = r["judgment"]
        comp = (j.faithfulness_score + j.action_relevance_score + j.action_correctness_score + j.clarity_score) / 4.0
        prop = r.get("property_context", {})
        alert = r.get("alert_context", {})
        advisory = r.get("agent_advisory", {})
        channels = advisory.get("channels", {})
        actions = advisory.get("micro_actions", [])
        hazard_summary = advisory.get("hazard_summary", {})
        exposure_analysis = advisory.get("exposure_analysis", {})
        mandatory_actions = r.get("mandatory_actions", [])

        # 1. Format Ground Truth
        gt_alert_str = (
            f"Alert: {alert.get('alert_name', 'Weather Alert')}\n"
            f"Severity: {alert.get('severity', 'Severe')} ({alert.get('risk_colour', 'warning').upper()})\n"
            f"Description: {alert.get('alert_text', alert.get('headline', ''))}"
        )

        gt_dwelling_str = (
            f"Dwelling: {prop.get('dwelling_type', 'N/A')}\n"
            f"Roof: {prop.get('roof_type', 'N/A')} ({prop.get('roof_age_years', '?')}y old)\n"
            f"Basement: {prop.get('basement_type', 'N/A')}\n"
            f"Sump Pump: {'YES' if prop.get('has_sump_pump') else 'NO'}\n"
            f"Backwater Valve: {'YES' if prop.get('has_backwater_valve') else 'NO'}"
        )

        gt_policy_str = (
            f"Policy: {prop.get('policy_number', 'N/A')}\n"
            f"Sewer Backup: {'COVERED' if prop.get('sewer_backup_endorsed') else 'UNINSURED (CRITICAL GAP)'}\n"
            f"Overland Water: {'COVERED' if prop.get('overland_water_endorsed') else 'UNINSURED (CRITICAL GAP)'}\n"
            f"Base Deductible: ${prop.get('base_deductible', 1000)}\n"
            f"Wind/Hail Deductible: ${prop.get('wind_hail_deductible', 1500)}"
        )

        gt_mandatory_actions_str = "\n\n".join(f"• {act}" for act in mandatory_actions) if mandatory_actions else "No benchmark actions defined"

        # 2. Format Agent Evaluated Output
        agent_hazard_str = (
            f"Identified Event: {hazard_summary.get('event', alert.get('alert_name', 'N/A'))}\n"
            f"Wind Gust: {hazard_summary.get('wind_gust_kmh', 0)} km/h | Hail: {hazard_summary.get('hail_descriptor', 'None')} ({hazard_summary.get('hail_diameter_cm', 0)} cm)\n"
            f"Rain: {hazard_summary.get('rainfall_mm', 0)} mm | Snow: {hazard_summary.get('snowfall_cm', 0)} cm\n"
            f"Tornado Risk: {'YES' if hazard_summary.get('tornado_risk') else 'NO'}\n"
            f"Identified Vulnerabilities: {', '.join(exposure_analysis.get('vulnerabilities', [])) or 'None'}\n"
            f"Identified Gaps: {', '.join(exposure_analysis.get('coverage_gaps', [])) or 'None'}"
        )

        actions_str = "\n\n".join(
            f"[P{a.get('priority', i)}] {a.get('category', 'GENERAL')}: {a.get('action', '')}\nRationale: {a.get('rationale', '')}"
            for i, a in enumerate(actions, 1)
        )

        sms_text = channels.get("sms", "")
        sms_str = f"\"{sms_text}\"\n\n(Length: {len(sms_text)} / 160 chars)"

        push = channels.get("push_notification", {})
        push_str = f"Title: {push.get('title', '')}\n\nBody: {push.get('body', '')}"

        row_values = [
            # Target
            prop.get("id", "UNKNOWN"),
            f"{prop.get('first_name', '')} {prop.get('last_name', '')}".strip() or prop.get("policyholder_name", "Policyholder") + f"\n{prop.get('address', '')}",
            f"{prop.get('city', '')}, {prop.get('province', '')}",
            # Ground Truth
            gt_alert_str,
            gt_dwelling_str,
            gt_policy_str,
            gt_mandatory_actions_str,
            # Agent Output
            agent_hazard_str,
            actions_str,
            sms_str,
            push_str,
            # Judge Scores & Justifications
            j.faithfulness_score,
            j.faithfulness_justification,
            j.action_relevance_score,
            j.action_relevance_justification,
            j.action_correctness_score,
            j.action_correctness_justification,
            j.clarity_score,
            j.clarity_justification,
            round(comp, 2),
        ]

        ws_results.row_dimensions[current_row].height = 135
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_results.cell(row=current_row, column=col_idx, value=val)
            cell.font = regular_font
            cell.border = cell_border

            # Column-specific formatting
            if col_idx == 1:  # Property ID
                cell.font = bold_font
                cell.alignment = center_align
            elif col_idx in (2, 3):  # Address / City
                cell.alignment = center_align
            elif col_idx in (12, 14, 16, 18, 20):  # Scores
                _format_score_cell(cell, float(val))
            else:  # Text & Justifications
                cell.alignment = left_wrap

        current_row += 1


    # =========================================================================
    # SHEET 2: Rubrics (Scoring Criteria 1-5)
    # =========================================================================
    ws_rubrics = wb.create_sheet(title="Rubrics")
    ws_rubrics.views.sheetView[0].showGridLines = True

    ws_rubrics.merge_cells("A1:G1")
    rubric_title = ws_rubrics["A1"]
    rubric_title.value = "Autonomous Agent Evaluation Rubrics (1 to 5 Scoring Criteria)"
    rubric_title.font = title_font
    rubric_title.alignment = Alignment(horizontal="left", vertical="center")
    ws_rubrics.row_dimensions[1].height = 30

    rubric_headers = [
        "Metric Name",
        "Aspect Evaluated",
        "Score 5 (Exemplary)",
        "Score 4 (High)",
        "Score 3 (Moderate)",
        "Score 2 (Low)",
        "Score 1 (Critical Failure)",
    ]

    ws_rubrics.row_dimensions[3].height = 26
    for col_idx, h in enumerate(rubric_headers, start=1):
        cell = ws_rubrics.cell(row=3, column=col_idx, value=h)
        cell.font = super_header_font
        cell.fill = target_super_fill
        cell.alignment = center_align
        cell.border = cell_border

    rubric_row = 4
    for key, spec in RUBRICS.items():
        ws_rubrics.row_dimensions[rubric_row].height = 95
        cells = [
            ws_rubrics.cell(row=rubric_row, column=1, value=spec["name"]),
            ws_rubrics.cell(row=rubric_row, column=2, value=spec["description"]),
            ws_rubrics.cell(row=rubric_row, column=3, value=spec["score_5"]),
            ws_rubrics.cell(row=rubric_row, column=4, value=spec["score_4"]),
            ws_rubrics.cell(row=rubric_row, column=5, value=spec["score_3"]),
            ws_rubrics.cell(row=rubric_row, column=6, value=spec["score_2"]),
            ws_rubrics.cell(row=rubric_row, column=7, value=spec["score_1"]),
        ]
        cells[0].font = bold_font
        cells[0].alignment = center_align
        cells[0].fill = summary_fill

        for c in cells:
            c.border = cell_border
            if c != cells[0]:
                c.font = regular_font
                c.alignment = left_wrap

        rubric_row += 1

    # =========================================================================
    # Auto-adjust column widths across both sheets
    # =========================================================================
    column_widths = {
        "Evaluation": {
            1: 14,   # Property ID
            2: 24,   # Policyholder & Address
            3: 16,   # City / Prov
            4: 38,   # GT Weather Alert & Metrics
            5: 28,   # GT Dwelling Specs
            6: 30,   # GT Policy Coverage & Gaps
            7: 42,   # Golden Mandatory Actions
            8: 35,   # Agent Hazard & Risk Assessment
            9: 48,   # Agent Proposed Micro-Actions
            10: 35,  # Agent Dispatched SMS
            11: 35,  # Agent Push Notification
            12: 14,  # Faithfulness Score
            13: 42,  # Faithfulness Justification
            14: 15,  # Action Relevance Score
            15: 42,  # Action Relevance Justification
            16: 15,  # Action Correctness Score
            17: 42,  # Action Correctness Justification
            18: 14,  # Clarity Score
            19: 42,  # Clarity Justification
            20: 16,  # Composite Quality Score
        },
        "Rubrics": {
            1: 25, 2: 35, 3: 35, 4: 35, 5: 35, 6: 35, 7: 35
        },
    }

    for sheet_name, widths in column_widths.items():
        ws = wb[sheet_name]
        for col_idx, width in widths.items():
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

    # Save to destination (handling Windows file locks if file is currently open in Excel)
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(out_file)
        return str(out_file)
    except PermissionError:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        alt_file = out_file.parent / f"{out_file.stem}_{timestamp}{out_file.suffix}"
        wb.save(alt_file)
        return str(alt_file)
