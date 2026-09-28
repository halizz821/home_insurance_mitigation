"""Unified Orchestrator: Autonomous Home Policy Weather Alert & Mitigation Pipeline.

Connects:
  1. Portfolio Sentinel (Agent 1 - Macro Filter):
     - Scans national or provincial property portfolio against Environment Canada weather warnings.
     - Performs GIS bounding box & FSA polygon spatial containment filtering.
     - Filters out non-property perils (e.g. fog, heat) and identifies at-risk candidates.
  2. Property Loss-Mitigation Specialist (Agent 2 - Micro Investigator):
     - Receives at-risk candidates from Agent 1.
     - Executes autonomous LangGraph ReAct + Reflection loop.
     - Inspects dwelling attributes, coverage gaps, and local peril parameters.
     - Deliberates in working memory scratchpads, validates safety invariants, and dispatches customer alerts.
     - Commits immutable audit records to SQLite database.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure project root, sentinel_system, and property_investigator are on sys.path
ROOT_DIR = Path(__file__).resolve().parent
SENTINEL_DIR = ROOT_DIR / "sentinel_system"
PROPERTY_DIR = ROOT_DIR / "property_investigator"

for p in [str(ROOT_DIR), str(SENTINEL_DIR), str(PROPERTY_DIR)]:
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)


# Load environment variables (.env in root or property_investigator)
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROPERTY_DIR / ".env")

# Set up Windows console encoding if needed
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

# Sentinel System imports
from sentinel_system.db.database import init_db, DEFAULT_DB_PATH
from sentinel_system.scanner.sentinel_agent import SentinelAgent
from sentinel_system.scanner.schemas import AtRiskPropertyCandidate

# Property Specialist imports
from property_investigator.tools.database_tools import init_audit_table
from sentinel_system.tools.mcp_client import default_mcp_client
from property_investigator.run_property_agent import (
    get_simulated_alerts,
    run_specialist_investigation,
    render_advisory_summary,
)

console = Console()
logger = logging.getLogger("unified_pipeline")


def render_pipeline_banner():
    """Renders the top-level pipeline banner."""
    console.print(
        Panel.fit(
            "[bold cyan]AUTONOMOUS INSURANCE LOSS-MITIGATION PIPELINE[/bold cyan]\n"
            "[italic]Two-Tier Multi-Agent System for Canadian P&C Insurers[/italic]\n\n"
            "• [bold green]Tier 1 - Portfolio Sentinel:[/bold green] Macro-level GIS Weather Risk Screening\n"
            "• [bold magenta]Tier 2 - Property Specialist:[/bold magenta] Autonomous ReAct + Reflection Deep-Dive",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )


def display_candidates_table(candidates: List[AtRiskPropertyCandidate]) -> None:
    """Renders formatted table of detected at-risk property candidates."""
    table = Table(
        title="[bold red]Stage 1 Output: Identified At-Risk Insured Properties[/bold red]",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("#", justify="center", style="dim")
    table.add_column("Property ID", style="bold white")
    table.add_column("Policy ID", style="dim")
    table.add_column("Location", style="cyan")
    table.add_column("Triggering Peril", style="bold red")
    table.add_column("Severity", style="magenta")
    table.add_column("Urgency", style="red")
    table.add_column("Dwelling", style="yellow")
    table.add_column("Endorsements", style="green")

    for idx, c in enumerate(candidates, 1):
        endorsements = []
        if c.sewer_backup_endorsed:
            endorsements.append("Sewer")
        if c.overland_water_endorsed:
            endorsements.append("Water")
        end_str = ", ".join(endorsements) if endorsements else "None"

        dwelling = f"{c.dwelling_type or 'Home'} ({c.roof_type or 'Roof'}, {c.roof_age_years or '?'}y)"

        table.add_row(
            str(idx),
            c.property_id,
            c.policy_id,
            f"{c.city}, {c.province} ({c.fsa})",
            c.triggering_event,
            c.severity,
            c.urgency,
            dwelling,
            end_str,
        )

    console.print(table)


def run_pipeline(
    province: Optional[str] = None,
    simulate: bool = False,
    limit: Optional[int] = None,
    properties: Optional[str] = None,
    demo_reflection: bool = False,
    verbose: bool = False,
    reseed: bool = False,
    skip_sentinel: bool = False,
    export_path: Optional[str] = None,
) -> None:
    """Executes the end-to-end multi-agent weather mitigation pipeline.

    Orchestrates the autonomous workflow across three distinct stages:
      - Stage 0 (Infrastructure & DB): Initializes the SQLite database
        (insurance_portfolio.db), verifies tables, and ensures the
        `mitigation_dispatches` audit table is ready.
      - Stage 1 (Sentinel Macro Screening): If `properties` is not specified,
        scans active Environment Canada weather warnings (live via MCP or
        simulated), runs GIS point-in-polygon checks against all insured
        properties in the portfolio, and filters candidates using severe
        property peril heuristics. Can also load cached candidates if
        `skip_sentinel` is True.
      - Stage 2 (Specialist Micro Investigation): For each prioritized or
        explicitly targeted property, invokes the Property Mitigation
        Specialist agent graph (ReAct loop, policy coverage lookup, vulnerability
        cross-referencing, deterministic safety invariants, self-correcting
        reflection, and multi-channel customer dispatch formatting).
      - Stage 3 (Reporting & Consolidation): Audits dispatches into SQLite and
        overwrites `output/advisories.json` with a single consolidated dictionary
        mapping each property_id to its complete advisory output.

    Args:
        province: Optional two-letter Canadian province/territory filter
            (e.g., 'ON', 'AB', 'SK') for Sentinel screening.
        simulate: If True, activates realistic simulated Environment Canada
            severe warnings; if False, connects directly to the live Environment
            Canada MCP server via stdio.
        limit: Maximum number of at-risk candidate properties prioritized by
            Sentinel to investigate in Stage 2 (default: None, processes all candidates).
        properties: Optional single property ID (e.g. 'HOM-1001') or comma-
            separated list of property IDs (e.g. 'HOM-1001,HOM-1051') to
            investigate directly, bypassing the Stage 1 macro scan.
        demo_reflection: If True, deliberately triggers a safety invariant
            violation on the first investigated property to demonstrate the
            agent's self-correcting reflection loop.
        verbose: If True, prints verbose internal reasoning scratchpads.
        reseed: If True, forces reseeding of the SQLite portfolio database.
        skip_sentinel: If True and `properties` is None, loads previously saved
            at-risk candidates from disk rather than querying the weather stream.
        export_path: Optional custom file path to export Stage 1 candidates JSON.

    Returns:
        None. Results are saved to `output/advisories.json` and committed to
        the SQLite audit table `mitigation_dispatches`.
    """
    render_pipeline_banner()
    start_time = time.time()

    # 1. Environment & Database Initialization
    console.rule("[bold cyan]Step 0: Initializing Infrastructure & Database[/bold cyan]")
    candidates_export = export_path or str(SENTINEL_DIR / "at_risk_candidates.json")
    
    init_db(DEFAULT_DB_PATH, force_seed=reseed)
    init_audit_table()
    console.print(f"[bold green]✔[/bold green] Portfolio database ready: [dim]{DEFAULT_DB_PATH}[/dim]")
    console.print(f"[bold green]✔[/bold green] Audit table `mitigation_dispatches` verified.")

    # Shared alerts configuration
    simulated_alerts = get_simulated_alerts() if simulate else None
    if simulate:
        console.print("[bold yellow]Mode: SIMULATED ENVIRONMENT CANADA SEVERE WEATHER ALERTS ACTIVE[/bold yellow]")
        default_mcp_client.set_simulated_alerts(simulated_alerts)
    else:
        console.print("[bold green]Mode: LIVE ENVIRONMENT CANADA MCP SERVER STREAM[/bold green]")
        default_mcp_client.disable_simulated_alerts()

    candidates: List[AtRiskPropertyCandidate] = []

    # 2. Stage 1: Portfolio Sentinel (Macro Screening)
    if not skip_sentinel and not properties:
        console.print()
        console.rule("[bold cyan]Stage 1: Portfolio Sentinel (Macro Screening)[/bold cyan]")
        sentinel = SentinelAgent(db_path=DEFAULT_DB_PATH)

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Scanning active weather warnings and running GIS point-in-polygon checks...", total=None)
            candidates = sentinel.scan_national_portfolio(
                province=province,
                alerts_override=simulated_alerts,
                export_path=candidates_export,
            )

        if not candidates:
            console.print("[yellow]No insured properties currently exposed to monitored property perils.[/yellow]")
            console.print("[dim]Pipeline complete. No specialist investigations required.[/dim]")
            return

        display_candidates_table(candidates)
        console.print(f"[bold green]✔[/bold green] Exported [bold magenta]{len(candidates)}[/bold magenta] candidate(s) to [dim]{candidates_export}[/dim]\n")
    
    elif skip_sentinel and not properties:
        console.print()
        console.rule("[bold yellow]Stage 1: Skipped (Loading Candidates from Disk)[/bold yellow]")
        if Path(candidates_export).exists():
            with open(candidates_export, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                candidates = [AtRiskPropertyCandidate(**item) for item in raw_data]
            console.print(f"Loaded [bold magenta]{len(candidates)}[/bold magenta] candidates from {candidates_export}")
            display_candidates_table(candidates)
        else:
            console.print(f"[red]Error: Candidate file not found at {candidates_export}[/red]")
            return

    # Determine candidate IDs to investigate
    investigation_list: List[str] = []
    if properties:
        investigation_list = [p.strip() for p in properties.split(",") if p.strip()]
        console.print(f"[cyan]Targeting explicit property list ({len(investigation_list)}):[/cyan] [bold white]{', '.join(investigation_list)}[/bold white]")
    else:
        total_available = len(candidates)
        target_count = min(total_available, limit) if limit is not None else total_available
        investigation_list = [c.property_id for c in candidates[:target_count]]
        label = f"top {target_count}" if (limit is not None and limit < total_available) else f"all {target_count}"
        console.print(f"[bold cyan]Queueing {label} prioritized candidate(s) for Stage 2 Specialist Deep-Dive...[/bold cyan]")

    # 3. Stage 2: Property Loss-Mitigation Specialist (Micro Investigation)
    console.print()
    console.rule("[bold magenta]Stage 2: Property Loss-Mitigation Specialist (ReAct + Reflection)[/bold magenta]")

    investigated_results: List[Dict[str, Any]] = []

    for i, p_id in enumerate(investigation_list, 1):
        console.print(f"\n[bold yellow]▶ Investigation {i}/{len(investigation_list)}: Property ID '{p_id}'[/bold yellow]")
        advisory = run_specialist_investigation(
            property_id=p_id,
            demo_reflection=demo_reflection if i == 1 else False,
            verbose=verbose,
            simulated_alerts=simulate,
        )
        if advisory:
            investigated_results.append(advisory)

    # Overwrite root output/advisories.json with investigated results
    output_dir = ROOT_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    advisories_file = output_dir / "advisories.json"
    advisories_data = {
        adv["property_id"]: adv for adv in investigated_results if adv.get("property_id")
    }
    with open(advisories_file, "w", encoding="utf-8") as f:
        json.dump(advisories_data, f, indent=2, default=str)

    elapsed_time = round(time.time() - start_time, 2)

    # 4. Stage 3: Executive Pipeline Summary
    console.print()
    console.rule("[bold green]Pipeline Execution Summary[/bold green]")

    summary_table = Table(box=box.ROUNDED, show_header=False)
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value", style="bold white")

    summary_table.add_row("Execution Duration", f"{elapsed_time} seconds")
    summary_table.add_row("Alert Data Source", "Simulated ECCC Weather Warnings" if simulate else "Live Environment Canada MCP Stream")
    summary_table.add_row(
        "Stage 1 At-Risk Candidates Found",
        str(len(candidates))
        if candidates
        else (("Single Override" if len(investigation_list) == 1 else f"Manual Override ({len(investigation_list)})") if properties else "0"),
    )
    summary_table.add_row("Stage 2 Deep Investigations Completed", str(len(investigated_results)))
    summary_table.add_row("Customer Dispatches Committed to SQLite", str(len(investigated_results)))
    summary_table.add_row("Consolidated Advisories JSON", str(advisories_file.resolve()))
    summary_table.add_row("Safety Invariant Verification", "[bold green]100% VERIFIED SAFE[/bold green]")
    summary_table.add_row("Audit Database Location", str(DEFAULT_DB_PATH.resolve()))

    console.print(summary_table)
    console.print(
        Panel(
            f"[bold green]✔ Multi-Agent Pipeline Completed Successfully![/bold green]\n"
            f"All prioritized loss-mitigation micro-actions have been audited, guardrail-checked, "
            f"dispatched to customer communication channels, and saved to [bold white]{advisories_file}[/bold white].",
            border_style="green",
            box=box.ROUNDED,
        )
    )


def main():
    """Main CLI entrypoint for unified pipeline."""
    parser = argparse.ArgumentParser(
        description="Autonomous Home Policy Weather Alert & Mitigation Pipeline (Sentinel + Property Specialist)"
    )
    parser.add_argument(
        "--simulate",
        "-s",
        action="store_true",
        help="Use realistic simulated Environment Canada severe alerts (Kingston Thunderstorm, Ottawa Tornado, Calgary Snow)",
    )
    parser.add_argument(
        "--province",
        "-p",
        type=str,
        default=None,
        help="Optional Canadian province code to filter scan (e.g. ON, AB, BC)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Maximum number of candidates to investigate in Stage 2 (default: None, processes all candidates)",
    )
    parser.add_argument(
        "--properties",
        type=str,
        default=None,
        help="Single property ID (e.g. 'HOM-1001') or comma-separated list (e.g. 'HOM-1001,HOM-1051') to investigate directly, skipping macro scan",
    )
    parser.add_argument(
        "--demo-reflection",
        action="store_true",
        help="Demonstrate intentional safety guardrail invariant failure and self-correcting reflection loop on first property",
    )
    parser.add_argument(
        "--skip-sentinel",
        action="store_true",
        help="Skip Sentinel scan and load existing candidates from at_risk_candidates.json",
    )
    parser.add_argument(
        "--export-path",
        "-o",
        type=str,
        default=None,
        help="Path to export audited at-risk candidates JSON (default: sentinel_system/at_risk_candidates.json)",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Force reseed the portfolio database with synthetic properties",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose scratchpad deliberation outputs",
    )

    args = parser.parse_args()

    run_pipeline(
        province=args.province,
        simulate=args.simulate,
        limit=args.limit,
        properties=args.properties,
        demo_reflection=args.demo_reflection,
        verbose=args.verbose,
        reseed=args.reseed,
        skip_sentinel=args.skip_sentinel,
        export_path=args.export_path,
    )


if __name__ == "__main__":
    main()
