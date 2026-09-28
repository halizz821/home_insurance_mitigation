"""CLI entry point for Property Loss-Mitigation Specialist (ReAct + Reflection Agent).

Demonstrates:
  1. Multi-turn ReAct tool execution loop
  2. Context distillation compression statistics
  3. Internal structured scratchpad deliberation
  4. Programmatic safety guardrail enforcement & reflection self-correction
  5. Simulated customer push/SMS dispatch & SQLite audit recording
  6. Single property investigation or batch processing from Portfolio Sentinel candidates
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Ensure property_agent root is on sys.path
AGENT_ROOT = Path(__file__).resolve().parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

# Load .env
load_dotenv(AGENT_ROOT / ".env")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .agent.graph import build_property_agent_graph
from .agent.state import PropertyAgentState

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()
logger = logging.getLogger("property_agent")


def load_sentinel_candidates() -> List[Dict[str, Any]]:
    """Loads at-risk property candidates identified by Portfolio Sentinel (Agent 1)."""
    candidates_path = AGENT_ROOT.parent / "sentinel_system" / "at_risk_candidates.json"
    if candidates_path.exists():
        try:
            with open(candidates_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {candidates_path}: {e}[/yellow]")
    return []


def get_simulated_alerts() -> List[Dict[str, Any]]:
    """Returns realistic simulated Environment Canada severe weather warnings matching the MCP format.

    Used when testing or benchmarking catastrophe filtering and mitigation advisories.
    Covers all benchmark regions including Wood Buffalo Nat. Park and Uranium City.
    """
    return [
        # 1. Wood Buffalo Nat. Park near Peace Point and Lake Claire (AB) - Severe Rainfall & Flash Flood
        {
            "id": "urn:eccc:alert:20260926:ab-wood-buffalo-rfw-warning",
            "feature_id": "fea1-2240",
            "feature_name": "Wood Buffalo Nat. Park near Peace Point and Lake Claire",
            "province": "AB",
            "alert_code": "RFW",
            "alert_type": "warning",
            "alert_name": "rainfall warning in effect",
            "alert_short_name": "Rainfall",
            "alert_text": "Heavy rain is expected.\n\nSignificant rainfall continues, with total rainfall amounts between 50 and 80 mm expected.\n\nThe rain will taper off by Sunday morning. Water will likely pool on roads and in low-lying areas. Rapid river runoff and localized washouts near rivers, creeks and culverts are possible.",
            "risk_colour": "orange",
            "status": "active",
            "publication_datetime": "2026-09-26T14:30:00Z",
            "expiration_datetime": "2026-09-27T08:30:00Z",
            "event_end_datetime": "2026-09-27T11:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.50, 57.00],
                        [-110.00, 57.00],
                        [-110.00, 58.50],
                        [-112.50, 58.50],
                        [-112.50, 57.00],
                    ]
                ],
            },
        },
        # 2. Uranium City - Camsell Portage (SK) - Blizzard & Extreme Wind
        {
            "id": "urn:eccc:alert:20260926:sk-uranium-city-blizzard-warning",
            "feature_id": "fea1-1869",
            "feature_name": "Uranium City - Camsell Portage",
            "province": "SK",
            "alert_code": "BZW",
            "alert_type": "warning",
            "alert_name": "blizzard warning in effect",
            "alert_short_name": "Blizzard",
            "alert_text": "Blizzard conditions with near-zero visibility in heavy snow and blowing snow expected.\n\nSustained winds 70 km/h with gusts up to 95 km/h, 30 to 45 cm snowfall accumulation, and wind chills dropping to -38. Rapidly accumulating heavy snow drifts pose severe roof loading stress and wind impact to aged structures. Freeze-up of exposed utility lines expected.",
            "risk_colour": "red",
            "status": "active",
            "publication_datetime": "2026-09-26T14:00:00Z",
            "expiration_datetime": "2026-09-27T12:00:00Z",
            "event_end_datetime": "2026-09-27T18:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-109.50, 59.00],
                        [-107.50, 59.00],
                        [-107.50, 60.50],
                        [-109.50, 60.50],
                        [-109.50, 59.00],
                    ]
                ],
            },
        },
        # 3. Kingston - Odessa - Frontenac Islands (ON) - Severe Thunderstorm & Hail
        {
            "id": "urn:eccc:alert:20260926:on-kingston-ts-warning",
            "feature_id": "043200",
            "feature_name": "Kingston - Odessa - Frontenac Islands",
            "province": "ON",
            "alert_code": "severe_thunderstorm_warning",
            "alert_type": "warning",
            "alert_name": "severe thunderstorm warning in effect",
            "alert_short_name": "Severe thunderstorm",
            "alert_text": "Environment Canada meteorologists are tracking a severe thunderstorm capable of producing 90 km/h wind gusts, nickel-sized hail (2.1 cm) and torrential downpours with localized amounts exceeding 50 mm.",
            "risk_colour": "red",
            "status": "active",
            "publication_datetime": "2026-09-26T14:30:00Z",
            "expiration_datetime": "2026-09-26T22:30:00Z",
            "event_end_datetime": "2026-09-26T23:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-76.65, 44.15],
                        [-76.35, 44.15],
                        [-76.35, 44.35],
                        [-76.65, 44.35],
                        [-76.65, 44.15],
                    ]
                ],
            },
        },
        # 4. Ottawa (Kanata - Orléans) (ON) - Tornado Warning
        {
            "id": "urn:eccc:alert:20260926:on-ottawa-tornado-warning",
            "feature_id": "043100",
            "feature_name": "Ottawa (Kanata - Orléans)",
            "province": "ON",
            "alert_code": "tornado_warning",
            "alert_type": "warning",
            "alert_name": "tornado warning in effect",
            "alert_short_name": "Tornado",
            "alert_text": "Environment Canada meteorologists are tracking a severe thunderstorm producing a tornado. Damaging winds up to 120 km/h and ping-pong ball size hail (3.5 cm) are occurring. Take cover immediately in an interior room or basement.",
            "risk_colour": "red",
            "status": "active",
            "publication_datetime": "2026-09-26T14:45:00Z",
            "expiration_datetime": "2026-09-26T21:45:00Z",
            "event_end_datetime": "2026-09-26T22:15:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-75.85, 45.30],
                        [-75.50, 45.30],
                        [-75.50, 45.55],
                        [-75.85, 45.55],
                        [-75.85, 45.30],
                    ]
                ],
            },
        },
        # 5. City of Calgary (AB) - Heavy Snowfall & Snow Load
        {
            "id": "urn:eccc:alert:20260926:ab-calgary-snow-warning",
            "feature_id": "021100",
            "feature_name": "City of Calgary",
            "province": "AB",
            "alert_code": "snowfall_warning",
            "alert_type": "warning",
            "alert_name": "snowfall warning in effect",
            "alert_short_name": "Snowfall",
            "alert_text": "Heavy snowfall with accumulations between 25 and 35 cm expected. Rapidly accumulating wet heavy snow will create hazardous driving conditions, significant roof load stress, and potential tree limb breakage onto power lines.",
            "risk_colour": "orange",
            "status": "active",
            "publication_datetime": "2026-09-26T14:00:00Z",
            "expiration_datetime": "2026-09-27T06:00:00Z",
            "event_end_datetime": "2026-09-27T10:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-114.25, 50.90],
                        [-113.90, 50.90],
                        [-113.90, 51.20],
                        [-114.25, 51.20],
                        [-114.25, 50.90],
                    ]
                ],
            },
        },
        # 6. City of Toronto (ON) - Torrential Downpour & Flash Flood Warning
        {
            "id": "urn:eccc:alert:20260926:on-toronto-rainfall-warning",
            "feature_id": "043400",
            "feature_name": "City of Toronto",
            "province": "ON",
            "alert_code": "rainfall_warning",
            "alert_type": "warning",
            "alert_name": "rainfall warning in effect",
            "alert_short_name": "Rainfall",
            "alert_text": "Torrential downpours giving 60 to 80 mm of rain in under 3 hours with wind gusts to 90 km/h. Localized urban flash flooding and sewer backup risk in low-lying residential areas.",
            "risk_colour": "orange",
            "status": "active",
            "publication_datetime": "2026-09-26T14:15:00Z",
            "expiration_datetime": "2026-09-26T23:15:00Z",
            "event_end_datetime": "2026-09-27T02:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-79.55, 43.55],
                        [-79.20, 43.55],
                        [-79.20, 43.75],
                        [-79.55, 43.75],
                        [-79.55, 43.55],
                    ]
                ],
            },
        },
        # 7. City of Edmonton (AB) - Severe Downpour & Flash Flood Warning
        {
            "id": "urn:eccc:alert:20260926:ab-edmonton-flash-flood-warning",
            "feature_id": "022100",
            "feature_name": "City of Edmonton",
            "province": "AB",
            "alert_code": "flash_flood_warning",
            "alert_type": "warning",
            "alert_name": "flash flood warning in effect",
            "alert_short_name": "Flash flood",
            "alert_text": "Intense torrential rainfall capable of producing 65 to 75 mm of rain in short duration. Rapid pooling of water on streets, overland surface runoff, and severe basement seepage risk.",
            "risk_colour": "red",
            "status": "active",
            "publication_datetime": "2026-09-26T14:10:00Z",
            "expiration_datetime": "2026-09-26T22:10:00Z",
            "event_end_datetime": "2026-09-27T01:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-113.70, 53.40],
                        [-113.30, 53.40],
                        [-113.30, 53.70],
                        [-113.70, 53.70],
                        [-113.70, 53.40],
                    ]
                ],
            },
        },
    ]


def run_specialist_investigation(
    property_id: str,
    demo_reflection: bool = False,
    verbose: bool = False,
    simulated_alerts: bool = False,
) -> Optional[Dict[str, Any]]:
    """Executes the autonomous ReAct + Reflection investigation for a single property."""
    console.print()
    console.rule(f"[bold cyan]Investigating Property: {property_id}[/bold cyan]")
    if demo_reflection:
        console.print("[bold yellow]>>> DEMO MODE: Intentional Safety Guardrail Trigger & Reflection Active <<<[/bold yellow]")

    from sentinel_system.tools.mcp_client import default_mcp_client
    if simulated_alerts:
        console.print("[bold cyan]>>> SIMULATED ALERT MODE ACTIVE: Bypassing live MCP; using simulated Environment Canada severe alerts <<<[/bold cyan]")
        default_mcp_client.set_simulated_alerts(get_simulated_alerts())
    else:
        default_mcp_client.disable_simulated_alerts()

    graph = build_property_agent_graph()

    initial_prompt = (
        f"Investigate at-risk property '{property_id}'. "
        f"Retrieve dwelling attributes and policy coverages, check local meteorological alerts, "
        f"proactively extract physical peril parameters (hail size, wind speeds, rain/snow), "
        f"cross-reference vulnerabilities against coverage gaps, evaluate safety invariants, "
        f"and output your deliberation scratchpad followed by the final mitigation advisory JSON."
    )

    state: PropertyAgentState = {
        "messages": [HumanMessage(content=initial_prompt)],
        "property_id": property_id,
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": demo_reflection,
    }

    step_num = 1
    final_advisory: Optional[Dict[str, Any]] = None

    for output in graph.stream(state, stream_mode="updates"):
        for node_name, node_update in output.items():
            if node_name == "agent_reasoner":
                messages = node_update.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if getattr(last_msg, "tool_calls", None):
                        tool_names = [tc["name"] for tc in last_msg.tool_calls]
                        console.print(
                            f"[bold blue]Step {step_num} [agent_reasoner][/bold blue] "
                            f"Decided to call [cyan]{len(tool_names)}[/cyan] tool(s): [green]{', '.join(tool_names)}[/green]"
                        )
                        for tc in last_msg.tool_calls:
                            console.print(f"  [dim]-> {tc['name']}({tc.get('args', {})})[/dim]")
                    else:
                        console.print(
                            f"[bold blue]Step {step_num} [agent_reasoner][/bold blue] "
                            f"[green]Tool Gathering Complete -> Proceeding to Structured Advisory Formulation[/green]"
                        )

            elif node_name == "advisory_formulator":
                scratchpad_text = node_update.get("scratchpad", "")
                console.print(
                    f"[bold blue]Step {step_num} [advisory_formulator][/bold blue] "
                    f"[green]Structured Advisory & Scratchpad Synthesized[/green]"
                )
                if scratchpad_text:
                    console.print(Panel(scratchpad_text, title="[bold]Structured Working Memory Scratchpad[/bold]", border_style="cyan"))

            elif node_name == "tool_node":
                messages = node_update.get("messages", [])
                console.print(f"[bold magenta]Step {step_num} [tool_node][/bold magenta] Executed {len(messages)} tool observation(s):")
                for msg in messages:
                    tool_name = getattr(msg, "name", "tool")
                    raw_text = str(msg.content)
                    snippet = raw_text.split("\n")[0][:100]
                    console.print(f"  [dim]- {tool_name} returned:[/dim] [white]{snippet}...[/white]")

            elif node_name == "safety_guardrail":
                violations = node_update.get("safety_violations", [])
                iteration = node_update.get("iteration_count", 0)
                if violations:
                    console.print(
                        f"[bold red]Step {step_num} [safety_guardrail][/bold red] "
                        f"[bold red]INVARIANT BREACH DETECTED! (Iteration {iteration})[/bold red]"
                    )
                    for v in violations:
                        console.print(f"  [red]CRITIQUE:[/red] {v}")
                    console.print("[yellow]-> Routing back to agent_reasoner for self-correction (Reflection Loop)...[/yellow]")
                else:
                    console.print(
                        f"[bold green]Step {step_num} [safety_guardrail][/bold green] "
                        f"[bold green]PASSED: Advisory verified safe against deterministic invariants.[/bold green]"
                    )

            elif node_name == "dispatch_node":
                final_advisory = node_update.get("final_advisory")
                console.print(
                    f"[bold green]Step {step_num} [dispatch_node][/bold green] "
                    f"Customer notification prepared and audit record committed to SQLite."
                )

            step_num += 1

    # Render summary presentation
    if final_advisory:
        render_advisory_summary(final_advisory)
    return final_advisory


def render_advisory_summary(advisory: Dict[str, Any]):
    """Renders formatted Rich tables and cards for customer dispatch payload."""
    prop_id = advisory.get("property_id", "UNKNOWN")
    policyholder = advisory.get("policyholder_name", "Policyholder")
    hazard = advisory.get("hazard_summary", {})
    exposure = advisory.get("exposure_analysis", {})
    micro_actions = advisory.get("micro_actions", [])
    channels = advisory.get("channels", {})
    safety_status = advisory.get("safety_status", "VERIFIED_SAFE")
    dispatch_id = advisory.get("dispatch_id", "DISP-LOCAL")

    # Hazard table
    hazard_table = Table(title=f"Hazard Extraction: {hazard.get('event', 'Weather Alert')}", box=box.ROUNDED)
    hazard_table.add_column("Peril Parameter", style="cyan", no_wrap=True)
    hazard_table.add_column("Observed Value", style="white")

    hazard_table.add_row("Max Wind Gusts", f"{hazard.get('wind_gust_kmh', 0)} km/h")
    hail_str = f"YES ({hazard.get('hail_descriptor') or f'{hazard.get('hail_diameter_cm')} cm'})" if hazard.get("hail_detected") else "None"
    hazard_table.add_row("Hail Detected", hail_str)
    hazard_table.add_row("Rainfall Accumulation", f"{hazard.get('rainfall_mm', 0)} mm")
    hazard_table.add_row("Snowfall Accumulation", f"{hazard.get('snowfall_cm', 0)} cm")
    hazard_table.add_row("Tornado Threat", "YES (EXTREME DANGER)" if hazard.get("tornado_risk") else "No")
    hazard_table.add_row("Estimated Lead Time", f"~{hazard.get('lead_time_minutes', 15)} minutes")

    console.print(hazard_table)

    # Actions table
    actions_table = Table(title=f"Prioritized Loss-Mitigation Micro-Actions ({prop_id})", box=box.ROUNDED)
    actions_table.add_column("Pri", justify="center", style="bold yellow")
    actions_table.add_column("Category", style="cyan")
    actions_table.add_column("Micro-Action Instruction", style="bold white")
    actions_table.add_column("Tailored Rationale", style="italic")

    for act in micro_actions:
        actions_table.add_row(
            str(act.get("priority", "-")),
            act.get("category", "GENERAL"),
            act.get("action", ""),
            act.get("rationale", ""),
        )

    console.print(actions_table)

    # Customer communication dispatch panel
    sms_text = channels.get("sms", "Urgent weather advisory in effect.")
    push = channels.get("push_notification", {})
    push_title = push.get("title", "Weather Alert")
    push_body = push.get("body", "")

    dispatch_info = (
        f"[bold cyan]Dispatch ID:[/bold cyan] {dispatch_id} | [bold green]Safety Invariant Status:[/bold green] {safety_status}\n"
        f"[bold yellow]Policyholder:[/bold yellow] {policyholder} ({advisory.get('contact', {}).get('phone', '')})\n\n"
        f"[bold green][SMS SENT][/bold green] [white]\"{sms_text}\"[/white]\n\n"
        f"[bold green][PUSH NOTIFICATION SENT][/bold green]\n"
        f"  [bold]{push_title}[/bold]: {push_body}\n\n"
        f"[bold dim]Audit Log: Committed to SQLite table `mitigation_dispatches`[/bold dim]"
    )
    console.print(Panel(dispatch_info, title="[bold]Customer Dispatch Transmission Summary[/bold]", border_style="green"))


def main():
    parser = argparse.ArgumentParser(description="Property Loss-Mitigation Specialist (ReAct + Reflection Agent)")
    parser.add_argument("--property_id", type=str, default="HOM-1001", help="Target property ID to investigate (default: HOM-1001)")
    parser.add_argument("--batch-from-sentinel", action="store_true", help="Loop through at-risk candidates generated by Portfolio Sentinel (Agent 1)")
    parser.add_argument("--limit", type=int, default=3, help="Max candidates to process in batch mode (default: 3)")
    parser.add_argument("--demo-reflection", action="store_true", help="Demonstrate intentional safety guardrail violation and reflection self-correction")
    parser.add_argument("--simulated-alerts", "--simulated", action="store_true", help="Use realistic simulated Environment Canada severe alerts instead of live MCP queries")
    parser.add_argument("--verbose", action="store_true", help="Show verbose scratchpad deliberation outputs")

    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]Property Loss-Mitigation Specialist[/bold cyan]\n"
        "[italic]Autonomous ReAct Investigation + Safety Reflection Loop[/italic]\n"
        "Powered by LangGraph, LangChain, Google Gemini, SQLite & Environment Canada MCP",
        border_style="cyan",
    ))

    if args.simulated_alerts:
        console.print("[bold yellow]Mode: Simulated Alert Mode Active (Kingston Severe TS, Ottawa Tornado, Calgary Snow)[/bold yellow]")

    if args.batch_from_sentinel:
        candidates = load_sentinel_candidates()
        if not candidates:
            console.print("[yellow]No candidates found in sentinel_system/at_risk_candidates.json. Running single property mode.[/yellow]")
            run_specialist_investigation(
                property_id=args.property_id,
                demo_reflection=args.demo_reflection,
                verbose=args.verbose,
                simulated_alerts=args.simulated_alerts,
            )
            return

        total = min(len(candidates), args.limit)
        console.print(f"[bold green]Processing {total} candidates from Portfolio Sentinel scanner...[/bold green]")
        for i, cand in enumerate(candidates[:total], 1):
            p_id = cand["property_id"]
            city = cand.get("city", "Unknown")
            event = cand.get("triggering_event", "Weather Alert")
            console.print(f"\n[bold yellow]--- Candidate {i}/{total}: {p_id} ({city} - {event}) ---[/bold yellow]")
            run_specialist_investigation(
                property_id=p_id,
                demo_reflection=False,
                verbose=args.verbose,
                simulated_alerts=args.simulated_alerts,
            )
    else:
        run_specialist_investigation(
            property_id=args.property_id,
            demo_reflection=args.demo_reflection,
            verbose=args.verbose,
            simulated_alerts=args.simulated_alerts,
        )


if __name__ == "__main__":
    main()
