"""LangChain @tool definitions for property investigation and meteorological alerts.

Exposes the 3 core tools:
  - tool_get_property_details
  - tool_get_policy_coverage
  - tool_get_alerts_near_coordinates
"""

import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from sentinel_system.tools.mcp_client import default_mcp_client
from property_investigator.context.distillers import (
    distill_cap_alert,
    distill_policy_context,
    distill_property_context,
)

# Resolve path to insurance_portfolio.db
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "sentinel_system" / "db" / "insurance_portfolio.db"
DB_PATH = Path(os.getenv("INSURANCE_DB_PATH", str(DEFAULT_DB_PATH)))


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection to insurance portfolio."""
    if not DB_PATH.exists():
        # Fallback to initialize database if not yet created
        SENTINEL_ROOT = Path(__file__).resolve().parent.parent.parent / "sentinel_system"
        if str(SENTINEL_ROOT) not in sys.path:
            sys.path.insert(0, str(SENTINEL_ROOT))
        try:
            from sentinel_system.db.database import init_db
            init_db(DB_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_audit_table():
    """Ensures mitigation_dispatches table exists in database."""
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mitigation_dispatches (
                dispatch_id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                safety_status TEXT NOT NULL,
                iteration_count INTEGER NOT NULL,
                sms_text TEXT NOT NULL,
                push_title TEXT NOT NULL,
                push_body TEXT NOT NULL,
                advisory_json TEXT NOT NULL
            );
            """
        )
    conn.close()


# Ensure audit table exists upon module import
init_audit_table()


@tool
def tool_get_property_details(property_id: str) -> str:
    """Fetches dwelling attributes (roof type/age, basement finish, sump pump, backwater valve).
    
    Args:
        property_id: The unique identifier of the property (e.g. 'HOM-1001').
        
    Returns:
        A dense, distilled vulnerability profile of the dwelling and location.
    """
    clean_id = property_id.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.policyholder_id, p.address, p.city, p.province, p.postal_code, p.fsa,
               p.latitude, p.longitude, p.dwelling_type, p.roof_type, p.roof_age_years,
               p.basement_type, p.has_sump_pump, p.has_backwater_valve,
               ph.first_name, ph.last_name, ph.phone, ph.email
        FROM properties p
        JOIN policyholders ph ON p.policyholder_id = ph.id
        WHERE p.id = ?;
        """,
        (clean_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return f"[ERROR] Property '{clean_id}' not found in portfolio database."

    return distill_property_context(dict(row))


@tool
def tool_get_policy_coverage(property_id: str) -> str:
    """Fetches deductibles, sewer backup endorsements, and overland flood coverage limits.
    
    Args:
        property_id: The unique identifier of the property (e.g. 'HOM-1001').
        
    Returns:
        A distilled summary of policy coverages and highlighted protection gaps.
    """
    clean_id = property_id.strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pol.id, pol.property_id, pol.policy_number, pol.effective_date, pol.expiry_date,
               pol.base_deductible, pol.wind_hail_deductible,
               pol.sewer_backup_endorsed, pol.overland_water_endorsed
        FROM policies pol
        WHERE pol.property_id = ?;
        """,
        (clean_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return f"[ERROR] Policy for property '{clean_id}' not found in portfolio database."

    return distill_policy_context(dict(row))


@tool
def tool_get_alerts_near_coordinates(latitude: float, longitude: float) -> str:
    """Queries Environment Canada weather alerts intersecting coordinates and distills physical perils.
    
    Extracts standardized physical peril metrics (wind speed in km/h, hail diameter in cm,
    rainfall in mm, snowfall in cm, tornado risk, lead time, and physical summary).
    
    Args:
        latitude: Latitude coordinate of the property (decimal degrees).
        longitude: Longitude coordinate of the property (decimal degrees).
        
    Returns:
        Dense, semantically distilled alert description with physical peril parameters,
        or a message indicating no active alerts.
    """
    res = default_mcp_client.get_alerts_near_coordinates(latitude=latitude, longitude=longitude)
    alerts = res.get("alerts", [])
    if not alerts:
        return f"No active Environment Canada weather alerts currently intersecting coordinates ({latitude}, {longitude})."

    distilled_outputs = []
    for alert in alerts[:3]:  # Top matching alerts intersecting coordinates
        distilled_str, _ = distill_cap_alert(alert, use_llm=True)
        distilled_outputs.append(distilled_str)

    return "\n\n---\n\n".join(distilled_outputs)
