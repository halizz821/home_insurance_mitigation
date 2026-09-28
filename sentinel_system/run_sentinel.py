"""CLI entry point to trigger Portfolio Sentinel macro scan."""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Ensure sentinel_system root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel_system.db.database import init_db, DEFAULT_DB_PATH
from sentinel_system.scanner.sentinel_agent import SentinelAgent
from sentinel_system.scanner.schemas import AtRiskPropertyCandidate

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


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


def display_results(
    candidates: List[AtRiskPropertyCandidate],
    export_path: str,
    simulated: bool,
    province: Optional[str] = None,
) -> None:
    """Renders formatted tables of the detected warnings and at-risk property candidates."""
    mode_text = "[bold yellow]SIMULATION MODE[/bold yellow]" if simulated else "[bold green]LIVE ECCC MCP STREAM[/bold green]"
    prov_text = f" (Province: {province})" if province else " (National Scope)"

    console.print(
        Panel(
            f"[bold cyan]PORTFOLIO SENTINEL: CATASTROPHE RISK MACRO-FILTER[/bold cyan]\n"
            f"Execution Mode: {mode_text}{prov_text}\n"
            f"Audited Candidates Generated: [bold magenta]{len(candidates)}[/bold magenta]",
            box=box.DOUBLE,
            expand=False,
        )
    )

    if not candidates:
        console.print("[yellow]No insured properties currently exposed to monitored property-threatening warnings.[/yellow]")
        return

    # Table 1: At-Risk Properties Overview
    table = Table(
        title="[bold red]Identified At-Risk Properties (Candidate Dispatch List for Agent 2)[/bold red]",
        box=box.ROUNDED,
        header_style="bold cyan",
    )

    table.add_column("Property ID", style="bold white")
    table.add_column("Policy ID", style="dim")
    table.add_column("City / Prov", style="cyan")
    table.add_column("FSA", style="bold yellow")
    table.add_column("Address", style="white")
    table.add_column("Triggering Peril", style="bold red")
    table.add_column("Severity", style="magenta")
    table.add_column("Urgency", style="red")
    table.add_column("Endorsements", style="green")

    for c in candidates:
        endorsements = []
        if c.sewer_backup_endorsed:
            endorsements.append("Sewer")
        if c.overland_water_endorsed:
            endorsements.append("Water")
        end_str = ", ".join(endorsements) if endorsements else "None"

        table.add_row(
            c.property_id,
            c.policy_id,
            f"{c.city}, {c.province}",
            c.fsa or "",
            c.address,
            c.triggering_event,
            c.severity,
            c.urgency,
            end_str,
        )

    console.print(table)
    console.print(f"\n[bold green][OK][/bold green] Candidates exported to: [bold white]{Path(export_path).resolve()}[/bold white]")
    console.print("[dim]Candidate iterable is ready for downstream Agent 2 (Property Mitigation Specialist).[/dim]\n")


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Portfolio Sentinel: Canadian Weather Catastrophe Exposure Filter"
    )
    parser.add_argument(
        "--province",
        "-p",
        type=str,
        default=None,
        help="Optional Canadian province code to filter scan (e.g. ON, AB, BC)",
    )
    parser.add_argument(
        "--simulate",
        "-s",
        action="store_true",
        help="Run scan against simulated severe warnings (Kingston Thunderstorm, Ottawa Tornado, Calgary Snow)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="at_risk_candidates.json",
        help="Path to export audited at-risk candidates JSON (default: at_risk_candidates.json)",
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Force reseed the portfolio database with 50 synthetic properties",
    )

    args = parser.parse_args()

    # 1. Ensure Database & Seed Data
    console.print("[dim]Checking portfolio database...[/dim]")
    init_db(DEFAULT_DB_PATH, force_seed=args.reseed)
    console.print(f"[dim]Database ready at: {DEFAULT_DB_PATH}[/dim]")

    # 2. Run Sentinel Macro Scan
    sentinel = SentinelAgent(db_path=DEFAULT_DB_PATH)

    alerts_override = get_simulated_alerts() if args.simulate else None

    with console.status("[bold cyan]Scanning Environment Canada warnings & spatial database...", spinner="dots"):
        candidates = sentinel.scan_national_portfolio(
            province=args.province,
            alerts_override=alerts_override,
            export_path=args.output,
        )

    # 3. Display Formatted Results
    display_results(
        candidates=candidates,
        export_path=args.output,
        simulated=args.simulate,
        province=args.province,
    )


if __name__ == "__main__":
    main()
