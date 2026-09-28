"""Portfolio Sentinel Agent: Macro scanner and catastrophe risk filter using GIS spatial correlation."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sentinel_system.db.database import query_properties_by_bbox, DEFAULT_DB_PATH
from .schemas import AtRiskPropertyCandidate, ScanSummary
from .zone_mapper import (
    get_geometry_bounding_box,
    match_properties_to_alert_polygon,
    parse_alert_geometry,
)
from sentinel_system.tools.mcp_client import EnvironmentCanadaMCPClient

logger = logging.getLogger(__name__)

# Property-threatening perils monitored by Portfolio Sentinel
# Ranked by catastrophe priority for deduplication
PERIL_PRIORITY: Dict[str, int] = {
    "tornado warning": 100,
    "severe thunderstorm warning": 90,
    "blizzard warning": 80,
    "winter storm warning": 75,
    "freezing rain warning": 70,
    "rainfall warning": 60,
    "wind warning": 55,
    "snowfall warning": 50,
}


class SentinelAgent:
    """Deliberative macro-scanner and database spatial correlation engine.

    Scans active warnings via Environment Canada MCP, filters for property perils,
    resolves affected areas via GIS polygon point-in-polygon containment,
    queries the portfolio database, and produces an audited list of
    AtRiskPropertyCandidate objects for downstream specialists.
    """

    def __init__(
        self,
        mcp_client: Optional[EnvironmentCanadaMCPClient] = None,
        db_path: Optional[Path] = None,
    ):
        """Initializes Sentinel Agent with MCP client and database path."""
        self.mcp_client = mcp_client or EnvironmentCanadaMCPClient()
        self.db_path = db_path or DEFAULT_DB_PATH

    @staticmethod
    def classify_peril(alert: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Determines if an alert matches property-threatening catastrophe perils.

        Filters out ended alerts and non-structural minor advisories/statements.

        Returns:
            Tuple of (is_monitored_peril, canonical_peril_name)
        """
        # 1. Filter out ended alerts
        status = str(alert.get("status") or alert.get("status_en") or "").lower()
        if status == "ended":
            return False, None

        # 2. Extract alert descriptors
        alert_name = str(alert.get("alert_name") or "").lower()
        alert_short = str(alert.get("alert_short_name") or "").lower()
        alert_code = str(alert.get("alert_code") or "").lower()
        alert_type = str(alert.get("alert_type") or "").lower()

        # Strict check: must be warning category
        combined_text = f"{alert_name} {alert_short} {alert_code}"
        if "warning" not in combined_text and "warning" not in alert_type:
            return False, None

        # Match against recognized property perils
        for peril in PERIL_PRIORITY:
            # Check full match or substring in alert name / code
            peril_tokens = peril.split()
            # E.g. 'tornado' and 'warning'
            if all(token in combined_text for token in peril_tokens):
                # Format to title case canonical peril name
                canonical = " ".join(word.capitalize() for word in peril.split())
                return True, canonical

        return False, None

    @staticmethod
    def infer_urgency_severity(peril_name: str, risk_colour: Optional[str] = None) -> Tuple[str, str]:
        """Infers standard CAP Urgency and Severity levels from peril and risk colour."""
        p_lower = peril_name.lower()
        colour = (risk_colour or "").lower()

        if "tornado" in p_lower:
            return "Immediate", "Extreme"
        if "severe thunderstorm" in p_lower:
            return "Immediate", "Severe"
        if "blizzard" in p_lower or "winter storm" in p_lower:
            return "Expected", "Severe"
        if "freezing rain" in p_lower:
            return "Expected", "Severe"
        if "rainfall" in p_lower:
            severity = "Severe" if colour in ["red", "orange"] else "Moderate"
            return "Expected", severity
        if "wind" in p_lower:
            severity = "Severe" if colour in ["red", "orange"] else "Moderate"
            return "Expected", severity
        if "snowfall" in p_lower:
            severity = "Severe" if colour in ["red", "orange"] else "Moderate"
            return "Expected", severity

        return "Expected", "Moderate"

    def scan_national_portfolio(
        self,
        province: Optional[str] = None,
        alerts_override: Optional[List[Dict[str, Any]]] = None,
        export_path: Optional[str] = "at_risk_candidates.json",
    ) -> List[AtRiskPropertyCandidate]:
        """Executes the full Macro Filter pipeline across the portfolio using GIS spatial polygons.

        1. Sweeps active warnings from Environment Canada MCP (with GeoJSON geometry).
        2. Filters out non-structural advisories to focus strictly on property-threatening perils.
        3. Enforces GeoJSON polygon geometry on each alert.
        4. Calculates geographic bounding box and queries SQLite properties within bounds.
        5. Tests exact point-in-polygon containment via Shapely.
        6. Deduplicates candidates by property ID, keeping the highest priority peril.
        7. Exports to JSON and returns candidate models.

        Args:
            province: Optional two-letter province code to filter (e.g. 'ON', 'AB').
            alerts_override: Optional list of alert dicts for testing or simulation.
            export_path: Output file path for audited JSON candidates.

        Returns:
            List of AtRiskPropertyCandidate models ready for downstream processing.
        """
        logger.info("Sentinel: Initiating GIS macro scan across insured portfolio...")

        # 1. Sweep Active Warnings
        if alerts_override is not None:
            raw_alerts = alerts_override
            logger.info(f"Sentinel: Utilizing provided alerts override ({len(raw_alerts)} alerts)")
        else:
            try:
                # Fetch national summary for executive visibility
                summary = self.mcp_client.get_alert_summary(province=province)
                logger.info(
                    f"Sentinel: ECCC Summary - Active Alerts: {summary.get('active_alerts_count', 0)}, "
                    f"Warnings: {summary.get('warnings_count', 0)}"
                )
            except Exception as e:
                logger.warning(f"Sentinel: Could not retrieve alert summary: {e}")

            # Search active warnings WITH GeoJSON geometry
            search_res = self.mcp_client.search_alerts(
                alert_type="warning",
                province=province,
                include_geometry=True,
            )
            raw_alerts = search_res.get("alerts", [])

        logger.info(f"Sentinel: Retrieved {len(raw_alerts)} total warnings from ECCC.")

        candidates_by_prop_id: Dict[str, AtRiskPropertyCandidate] = {}
        processed_warnings = 0

        # 2. Process each active warning
        for alert in raw_alerts:
            is_monitored, canonical_peril = self.classify_peril(alert)
            if not is_monitored or not canonical_peril:
                continue

            # Strict check: all alerts must include valid GeoJSON geometry
            geometry = alert.get("geometry")
            if not geometry:
                alert_ref = alert.get("id") or alert.get("alert_name") or "unknown"
                logger.warning(
                    f"Sentinel: Alert '{alert_ref}' lacks GeoJSON geometry; skipping (strict geometry required)."
                )
                continue

            try:
                min_lon, min_lat, max_lon, max_lat = get_geometry_bounding_box(geometry)
            except Exception as e:
                alert_ref = alert.get("id") or alert.get("alert_name") or "unknown"
                logger.warning(f"Sentinel: Alert '{alert_ref}' has invalid geometry ({e}); skipping.")
                continue

            processed_warnings += 1

            # 3. Fast SQL Bounding Box Query
            candidate_props = query_properties_by_bbox(
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
                db_path=self.db_path,
            )

            if not candidate_props:
                continue

            # 4. Strict Point-in-Polygon containment check
            matched_props = match_properties_to_alert_polygon(geometry, candidate_props)
            logger.info(
                f"Sentinel: Warning '{canonical_peril}' matched {len(matched_props)} properties "
                f"out of {len(candidate_props)} in bounding box."
            )

            alert_id = str(alert.get("id") or alert.get("feature_id") or "UNKNOWN_ALERT")
            feature_id = str(alert["feature_id"]) if alert.get("feature_id") else None
            headline = str(
                alert.get("alert_name")
                or alert.get("alert_short_name")
                or f"{canonical_peril} Warning"
            )
            urgency, severity = self.infer_urgency_severity(canonical_peril, alert.get("risk_colour"))

            # 5. Format and deduplicate candidates
            for rec in matched_props:
                prop_id = rec["id"]
                candidate = AtRiskPropertyCandidate(
                    property_id=prop_id,
                    policy_id=rec["policy_id"],
                    address=rec["address"],
                    coordinates={
                        "latitude": float(rec["latitude"]),
                        "longitude": float(rec["longitude"]),
                    },
                    triggering_alert_id=alert_id,
                    feature_id=feature_id,
                    triggering_event=canonical_peril,
                    headline=headline,
                    urgency=urgency,
                    severity=severity,
                    city=rec.get("city"),
                    province=rec.get("province"),
                    postal_code=rec.get("postal_code"),
                    fsa=rec.get("fsa"),
                    dwelling_type=rec.get("dwelling_type"),
                    roof_type=rec.get("roof_type"),
                    roof_age_years=rec.get("roof_age_years"),
                    basement_type=rec.get("basement_type"),
                    has_sump_pump=bool(rec.get("has_sump_pump")),
                    has_backwater_valve=bool(rec.get("has_backwater_valve")),
                    policy_number=rec.get("policy_number"),
                    base_deductible=rec.get("base_deductible"),
                    wind_hail_deductible=rec.get("wind_hail_deductible"),
                    sewer_backup_endorsed=bool(rec.get("sewer_backup_endorsed")),
                    overland_water_endorsed=bool(rec.get("overland_water_endorsed")),
                    policyholder_name=f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip() or None,
                    policyholder_phone=rec.get("phone"),
                    policyholder_email=rec.get("email"),
                )

                if prop_id not in candidates_by_prop_id:
                    candidates_by_prop_id[prop_id] = candidate
                else:
                    existing_priority = PERIL_PRIORITY.get(
                        candidates_by_prop_id[prop_id].triggering_event.lower(), 0
                    )
                    new_priority = PERIL_PRIORITY.get(canonical_peril.lower(), 0)
                    if new_priority > existing_priority:
                        candidates_by_prop_id[prop_id] = candidate

        final_candidates = list(candidates_by_prop_id.values())
        logger.info(
            f"Sentinel: Processed {processed_warnings} warnings. "
            f"Identified {len(final_candidates)} deduplicated at-risk property candidates."
        )

        # 6. Output Export
        if export_path:
            self._export_candidates(final_candidates, export_path)

        return final_candidates

    @staticmethod
    def _export_candidates(candidates: List[AtRiskPropertyCandidate], export_path: str) -> None:
        """Serializes candidate list to audited JSON file."""
        out_file = Path(export_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        data = [c.model_dump() for c in candidates]
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Sentinel: Candidate list exported to {out_file.resolve()}")
