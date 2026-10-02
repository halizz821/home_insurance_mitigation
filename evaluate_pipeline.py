"""Evaluation Runner: LLM-as-a-Judge Evaluation Pipeline for Insurance Mitigation Agent.

Evaluates:
  1. Faithfulness & Anti-Hallucination (1-5)
  2. Action Relevance & Property Tailoring (1-5)
  3. Action Correctness & Semantic Coverage (1-5)
  4. Communication Clarity & Actionability (1-5)

Uses:
  - Agent under test: Google Gemini (unaltered in property_investigator)
  - Judge model: OpenAI (gpt-4o)
  - Exports: Comprehensive multi-tab Excel workbook with Rubrics, Scores, Justifications, and Context.
"""

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Ensure project root and agents are on sys.path
ROOT_DIR = Path(__file__).resolve().parent
SENTINEL_DIR = ROOT_DIR / "sentinel_system"
PROPERTY_DIR = ROOT_DIR / "property_investigator"

for p in [str(ROOT_DIR), str(SENTINEL_DIR), str(PROPERTY_DIR)]:
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROPERTY_DIR / ".env")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

from property_investigator.tools.database_tools import get_db_connection
from sentinel_system.tools.mcp_client import default_mcp_client
from property_investigator.run_property_agent import get_simulated_alerts
from evaluation.llm_judge import LLMJudge, EvaluationJudgment
from evaluation.excel_exporter import export_evaluation_to_excel
from evaluation.rubrics import RUBRICS

console = Console()
logger = logging.getLogger("eval_pipeline")


def get_ground_truth_property(property_id: str) -> Dict[str, Any]:
    """Retrieves full property, policy, and policyholder record from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT 
            p.id, p.address, p.city, p.province, p.postal_code, p.fsa,
            p.latitude, p.longitude, p.dwelling_type, p.roof_type, p.roof_age_years,
            p.basement_type, p.has_sump_pump, p.has_backwater_valve,
            pol.id AS policy_id, pol.policy_number,
            pol.sewer_backup_endorsed, pol.overland_water_endorsed,
            pol.base_deductible, pol.wind_hail_deductible,
            polh.first_name, polh.last_name, polh.phone, polh.email
        FROM properties p
        JOIN policies pol ON p.id = pol.property_id
        JOIN policyholders polh ON p.policyholder_id = polh.id
        WHERE p.id = ?
        """,
        (property_id,),
    ).fetchone()

    if not row:
        return {}
    return dict(row)


def get_matching_alert_for_property(property_context: Dict[str, Any], alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Finds the simulated alert corresponding to the property's coordinates, city or province."""
    lat = property_context.get("latitude")
    lon = property_context.get("longitude")
    if lat is not None and lon is not None:
        near_res = default_mcp_client.get_alerts_near_coordinates(latitude=lat, longitude=lon)
        if near_res and near_res.get("alerts"):
            return near_res["alerts"][0]

    city = property_context.get("city", "").lower()
    prov = property_context.get("province", "").lower()

    for alert in alerts:
        feature_name = str(alert.get("feature_name", "")).lower()
        alert_prov = str(alert.get("province", "")).lower()
        if city in feature_name or (prov == alert_prov and city in alert.get("id", "").lower()):
            return alert

    # Fallback to first alert if not matched
    return alerts[0] if alerts else {}


DEFAULT_ADVISORIES_FILE = ROOT_DIR / "output" / "advisories.json"
DEFAULT_GOLDEN_DATASET_FILE = ROOT_DIR / "evaluation" / "golden_dataset.json"


def evaluate_benchmark_properties(
    property_ids: Optional[List[str]] = None,
    judge_model: str = "gpt-4o",
    output_excel: str = "agent_evaluation_results.xlsx",
    alert_source: str = "live",
) -> List[Dict[str, Any]]:
    """Runs LLM Judge evaluation on pre-generated agent advisories loaded from root output/advisories.json."""

    use_simulated_alerts = (alert_source.lower() == "simulated")
    alert_source_label = "SIMULATED Severe Weather Alerts" if use_simulated_alerts else "LIVE Environment Canada Weather Alerts (MCP Server)"
    advisory_filepath = DEFAULT_ADVISORIES_FILE

    # 1. Verify Database Existence (Assuming it already exists; independently queried)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM properties;")
        prop_count = cursor.fetchone()[0]
        if prop_count == 0:
            console.print("[yellow]Warning: Connected to database but 'properties' table contains 0 records.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Database Connection Error: Could not query existing database: {e}[/bold red]")
        sys.exit(1)

    # 2. Load Consolidated Pre-generated Advisories from Single JSON File
    if not advisory_filepath.exists():
        console.print(f"[bold red]Error: Advisories file '{advisory_filepath}' not found. Please run run_pipeline.py first to generate results.[/bold red]")
        return []

    try:
        with open(advisory_filepath, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            if isinstance(raw_data, dict):
                advisories_map = raw_data
            elif isinstance(raw_data, list):
                advisories_map = {item.get("property_id"): item for item in raw_data if item.get("property_id")}
            else:
                advisories_map = {}
        console.print(f"[dim]Loaded consolidated file with [bold white]{len(advisories_map)}[/bold white] property advisories.[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]Error reading advisories file '{advisory_filepath}': {e}[/bold red]")
        return []

    # 3. Load Golden Dataset for Action Correctness Benchmark
    golden_dataset = {}
    if DEFAULT_GOLDEN_DATASET_FILE.exists():
        try:
            with open(DEFAULT_GOLDEN_DATASET_FILE, "r", encoding="utf-8") as f:
                golden_dataset = json.load(f)
            console.print(f"[dim]Loaded golden benchmark dataset with [bold white]{len(golden_dataset)}[/bold white] property references.[/dim]\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read golden dataset '{DEFAULT_GOLDEN_DATASET_FILE}': {e}[/yellow]")
    else:
        console.print(f"[yellow]Warning: Golden dataset not found at '{DEFAULT_GOLDEN_DATASET_FILE}'.[/yellow]")

    # Determine target property IDs (default: evaluate all properties in advisories.json)
    if property_ids:
        target_ids = property_ids
    else:
        target_ids = list(advisories_map.keys())

    if not target_ids:
        console.print(f"[bold red]No properties found to evaluate in '{advisory_filepath}'.[/bold red]")
        return []

    console.print(
        Panel.fit(
            "[bold cyan]AUTONOMOUS AGENT EVALUATION PIPELINE[/bold cyan]\n"
            "[italic]LLM-as-a-Judge (OpenAI) assessing Faithfulness, Action Relevance, Action Correctness & Clarity[/italic]\n\n"
            f"• [bold green]Consolidated Advisories File:[/bold green] [cyan]{advisory_filepath}[/cyan]\n"
            f"• [bold green]Golden Benchmark Dataset:[/bold green] [cyan]{DEFAULT_GOLDEN_DATASET_FILE}[/cyan]\n"
            f"• [bold magenta]Judge Model:[/bold magenta] OpenAI ({judge_model})\n"
            f"• [bold yellow]Benchmark Targets:[/bold yellow] {len(target_ids)} Residential Properties ({', '.join(target_ids)})\n"
            f"• [bold blue]Weather Alert Source:[/bold blue] [bold {'cyan' if use_simulated_alerts else 'magenta'}]{alert_source_label}[/bold {'cyan' if use_simulated_alerts else 'magenta'}]\n"
            f"• [bold blue]Database:[/bold blue] Existing SQLite (insurance_portfolio.db - independently queried)\n"
            f"• [bold blue]Output Report:[/bold blue] Excel Workbook ({output_excel})",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )

    # 4. Configure Weather Alert Source for Independent Querying (Simulated vs Live MCP)
    if use_simulated_alerts:
        simulated_alerts = get_simulated_alerts()
        default_mcp_client.set_simulated_alerts(simulated_alerts)
    else:
        default_mcp_client.disable_simulated_alerts()
        simulated_alerts = []

    judge = LLMJudge(model=judge_model)
    evaluation_results: List[Dict[str, Any]] = []

    # 5. Iterate through each property
    for idx, prop_id in enumerate(target_ids, 1):
        console.rule(f"[bold yellow]Benchmark {idx}/{len(target_ids)}: Judging Property '{prop_id}'[/bold yellow]")

        # 1. Independently query ground truth property from SQLite
        prop_gt = get_ground_truth_property(prop_id)
        if not prop_gt:
            console.print(f"[red]Error: Property ID {prop_id} not found in database.[/red]")
            continue

        # 2. Independently query weather alert ground truth
        if use_simulated_alerts:
            alert_gt = get_matching_alert_for_property(prop_gt, simulated_alerts)
        else:
            lat = prop_gt.get("latitude")
            lon = prop_gt.get("longitude")
            live_res = default_mcp_client.get_alerts_near_coordinates(latitude=lat, longitude=lon)
            live_matching = live_res.get("alerts", [])
            if live_matching:
                alert_gt = live_matching[0]
            else:
                alert_gt = {
                    "id": f"live:calm:{prop_id}",
                    "alert_name": "No Active Severe Weather Warning",
                    "severity": "None",
                    "risk_colour": "green",
                    "alert_text": f"Environment Canada reports no active meteorological warnings or watches near coordinates ({lat}, {lon}) for {prop_gt.get('city')}, {prop_gt.get('province')}.",
                    "lead_time_minutes": None,
                }

        console.print(f"  [cyan]City / Prov:[/cyan] {prop_gt.get('city')}, {prop_gt.get('province')}")
        console.print(f"  [cyan]Dwelling:[/cyan] {prop_gt.get('dwelling_type')} ({prop_gt.get('roof_type')}, {prop_gt.get('roof_age_years')}y), {prop_gt.get('basement_type')} basement")
        console.print(f"  [cyan]Endorsements:[/cyan] Sewer: {'YES' if prop_gt.get('sewer_backup_endorsed') else 'NO (GAP)'} | Water: {'YES' if prop_gt.get('overland_water_endorsed') else 'NO (GAP)'}")
        console.print(f"  [cyan]Active Alert:[/cyan] [bold {'red' if alert_gt.get('risk_colour') in ('red', 'orange') else 'green'}]{alert_gt.get('alert_name')}[/bold {'red' if alert_gt.get('risk_colour') in ('red', 'orange') else 'green'}]")

        # 3. Retrieve pre-generated Agent Advisory for this property from the merged file
        advisory = advisories_map.get(prop_id)
        if not advisory:
            console.print(
                f"[bold red]Advisory for '{prop_id}' not found in '{advisory_filepath}'.[/bold red]\n"
                f"[dim]Please run run_pipeline.py first to generate results for {prop_id}. Skipping.[/dim]"
            )
            continue
        console.print(f"  [dim]✔ Extracted advisory for {prop_id} from consolidated JSON[/dim]")

        # 4. Retrieve golden reference mandatory actions
        gold_entry = golden_dataset.get(prop_id, {})
        mandatory_actions = gold_entry.get("mandatory_actions", [])

        # 5. Run 4-Prompt LLM Judge
        console.print(f"[dim]-> Running 4-Prompt LLM Judge ({judge_model})...[/dim]")
        judgment: EvaluationJudgment = judge.evaluate(
            property_context=prop_gt,
            alert_context=alert_gt,
            agent_advisory=advisory,
            mandatory_actions=mandatory_actions,
        )

        # Print Judgment Summary Card
        composite = (
            judgment.faithfulness_score
            + judgment.action_relevance_score
            + judgment.action_correctness_score
            + judgment.clarity_score
        ) / 4.0

        card_text = (
            f"[bold cyan]Property:[/bold cyan] {prop_id} ({prop_gt.get('city')})\n"
            f"[bold red]Hazard:[/bold red] {alert_gt.get('alert_name')}\n\n"
            f"  • [bold green]Faithfulness Score:[/bold green] [bold white]{judgment.faithfulness_score} / 5[/bold white]\n"
            f"    [italic dim]{judgment.faithfulness_justification}[/italic dim]\n\n"
            f"  • [bold green]Action Relevance Score:[/bold green] [bold white]{judgment.action_relevance_score} / 5[/bold white]\n"
            f"    [italic dim]{judgment.action_relevance_justification}[/italic dim]\n\n"
            f"  • [bold green]Action Correctness Score:[/bold green] [bold white]{judgment.action_correctness_score} / 5[/bold white]\n"
            f"    [italic dim]{judgment.action_correctness_justification}[/italic dim]\n\n"
            f"  • [bold green]Clarity Score:[/bold green] [bold white]{judgment.clarity_score} / 5[/bold white]\n"
            f"    [italic dim]{judgment.clarity_justification}[/italic dim]\n\n"
            f"[bold yellow]Composite Quality Score:[/bold yellow] [bold magenta]{composite:.2f} / 5.0[/bold magenta]"
        )

        console.print(Panel(card_text, title=f"[bold]OpenAI Judge Evaluation for {prop_id}[/bold]", border_style="magenta", box=box.ROUNDED))

        evaluation_results.append({
            "property_id": prop_id,
            "property_context": prop_gt,
            "alert_context": alert_gt,
            "mandatory_actions": mandatory_actions,
            "agent_advisory": advisory,
            "judgment": judgment,
        })

    if not evaluation_results:
        console.print("[red]No evaluations completed.[/red]")
        return []

    # 3. Overall Evaluation Summary Table
    console.print()
    console.rule("[bold cyan]Executive Benchmark Evaluation Summary[/bold cyan]")

    summary_table = Table(title="[bold green]LLM-as-a-Judge Benchmark Results[/bold green]", box=box.ROUNDED)
    summary_table.add_column("Property ID", style="bold white")
    summary_table.add_column("City / Peril", style="cyan")
    summary_table.add_column("Faithfulness", justify="center", style="bold green")
    summary_table.add_column("Action Relevance", justify="center", style="bold green")
    summary_table.add_column("Action Correctness", justify="center", style="bold green")
    summary_table.add_column("Clarity", justify="center", style="bold green")
    summary_table.add_column("Composite", justify="center", style="bold magenta")

    for r in evaluation_results:
        j = r["judgment"]
        comp = (j.faithfulness_score + j.action_relevance_score + j.action_correctness_score + j.clarity_score) / 4.0
        city = r["property_context"].get("city", "")
        peril = r["alert_context"].get("alert_short_name", "Alert")
        summary_table.add_row(
            r["property_id"],
            f"{city} ({peril})",
            f"{j.faithfulness_score}/5",
            f"{j.action_relevance_score}/5",
            f"{j.action_correctness_score}/5",
            f"{j.clarity_score}/5",
            f"{comp:.2f}/5.0",
        )

    # Averages
    avg_f = sum(r["judgment"].faithfulness_score for r in evaluation_results) / len(evaluation_results)
    avg_r = sum(r["judgment"].action_relevance_score for r in evaluation_results) / len(evaluation_results)
    avg_ac = sum(r["judgment"].action_correctness_score for r in evaluation_results) / len(evaluation_results)
    avg_c = sum(r["judgment"].clarity_score for r in evaluation_results) / len(evaluation_results)
    avg_total = (avg_f + avg_r + avg_ac + avg_c) / 4.0

    summary_table.add_section()
    summary_table.add_row(
        "[bold yellow]AVERAGE[/bold yellow]",
        f"[bold yellow]{len(evaluation_results)} Properties[/bold yellow]",
        f"[bold yellow]{avg_f:.2f}/5[/bold yellow]",
        f"[bold yellow]{avg_r:.2f}/5[/bold yellow]",
        f"[bold yellow]{avg_ac:.2f}/5[/bold yellow]",
        f"[bold yellow]{avg_c:.2f}/5[/bold yellow]",
        f"[bold yellow]{avg_total:.2f}/5.0[/bold yellow]",
    )

    console.print(summary_table)

    # 4. Export to Excel
    excel_path = export_evaluation_to_excel(evaluation_results, output_path=output_excel)
    console.print(
        Panel(
            f"[bold green]✔ Evaluation Results Successfully Saved to Excel![/bold green]\n\n"
            f"File Path: [bold white]{excel_path}[/bold white]\n"
            f"Tabs Included:\n"
            f"  1. [bold cyan]Evaluation[/bold cyan]: Integrated side-by-side table combining Target, Ground Truth (including Golden Mandatory Actions), Agent Outputs, and LLM Judge Scores/Justifications across all 4 metrics.\n"
            f"  2. [bold cyan]Rubrics[/bold cyan]: Complete 1-to-5 scoring criteria and guidelines for Faithfulness, Action Relevance, Action Correctness, and Clarity.",
            border_style="green",
            box=box.ROUNDED,
        )
    )

    return evaluation_results



def main():
    parser = argparse.ArgumentParser(
        description="LLM-as-a-Judge Evaluation Pipeline for Insurance Mitigation Agent"
    )
    parser.add_argument(
        "--properties",
        type=str,
        default=None,
        help="Comma-separated list of residential property IDs to evaluate (default: all properties in output/advisories.json)",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="gpt-4o",
        help="OpenAI model to use as the impartial judge (default: gpt-4o)",
    )
    parser.add_argument(
        "--output-excel",
        "-o",
        type=str,
        default="agent_evaluation_results.xlsx",
        help="Output Excel filename (default: agent_evaluation_results.xlsx)",
    )
    parser.add_argument(
        "--alert-source",
        type=str,
        choices=["live", "simulated"],
        default="live",
        help="Weather alert source to evaluate against: 'live' or 'simulated' (default: live)",
    )
    args = parser.parse_args()

    prop_list = [p.strip() for p in args.properties.split(",") if p.strip()] if args.properties else None
    evaluate_benchmark_properties(
        property_ids=prop_list,
        judge_model=args.judge_model,
        output_excel=args.output_excel,
        alert_source=args.alert_source,
    )


if __name__ == "__main__":
    main()
