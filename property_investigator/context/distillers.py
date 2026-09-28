"""Semantic distillation middleware for meteorological alerts and property records.

Compresses verbose Environment Canada CAP JSON payloads and spatial records into dense,
standardized physical peril representations using LLM structured extraction.
"""

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple, Union
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger(__name__)


class PhysicalPerilParameters(BaseModel):
    """Standardized physical peril parameters extracted from weather alert."""
    alert_name: str = Field(description="Standardized alert name e.g. Severe Thunderstorm Warning, Tornado Warning")
    is_active: bool = Field(default=True, description="Whether alert is active")
    tornado_risk: bool = Field(default=False, description="Whether a tornado threat, rotation, or touchdown is explicitly reported or warned")
    hail_detected: bool = Field(default=False, description="Whether hail is explicitly reported or forecast")
    hail_diameter_cm: Optional[float] = Field(default=None, description="Estimated hail diameter in cm if specified, otherwise None")
    hail_descriptor: Optional[str] = Field(default=None, description="Hail descriptor (e.g. nickel-sized) if specified, otherwise None")
    wind_gust_kmh: Optional[int] = Field(default=None, description="Maximum wind gust speed in km/h if explicitly stated, otherwise None")
    rainfall_mm: Optional[int] = Field(default=None, description="Expected or recorded rainfall accumulation in mm if explicitly stated, otherwise None")
    snowfall_cm: Optional[int] = Field(default=None, description="Expected or recorded snowfall accumulation in cm if explicitly stated, otherwise None")
    snow_description: Optional[str] = Field(default=None, description="Details on snow accumulation or roof loading risk if specified, otherwise None")
    freezing_rain: bool = Field(default=False, description="Whether freezing rain, glaze, or ice pellets is explicitly reported")
    lead_time_minutes: Optional[int] = Field(default=None, description="Estimated arrival or lead time in minutes if explicitly mentioned in text, otherwise None")
    physical_summary: str = Field(description="Dense factual summary of physical threats explicitly mentioned in alert")


def extract_perils_with_llm(
    alert_text: str,
    alert_name: str = "",
    use_llm: bool = True,
) -> PhysicalPerilParameters:
    """Extracts standardized physical perils using Gemini structured output."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required for LLM peril extraction.")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            api_key=api_key,
        )
        structured_llm = llm.with_structured_output(PhysicalPerilParameters)
        prompt = (
            f"You are a Canadian meteorological peril extraction specialist. "
            f"Extract only the factual physical peril parameters explicitly mentioned in the following Environment Canada weather alert.\n\n"
            f"STRICT ANTI-HALLUCINATION INSTRUCTIONS:\n"
            f"- Do NOT assume, fabricate, or extrapolate numeric values. If wind speed, rainfall amount, snowfall accumulation, or lead time are not explicitly stated, you MUST return None for them.\n"
            f"- Do NOT assume 0 for unmentioned metrics (an unmentioned metric is None, not 0).\n"
            f"- Set tornado_risk=true ONLY if a tornado, funnel cloud, or rotation is explicitly warned or reported.\n"
            f"- Set hail_detected=true ONLY if hail is explicitly warned or forecast.\n"
            f"- Set freezing_rain=true ONLY if freezing rain, ice pellets, or glaze is explicitly reported.\n"
            f"- For lead_time_minutes, extract the number ONLY if advance warning minutes or an explicit arrival timeframe is stated (e.g. 'within 15 minutes'). Otherwise return None.\n\n"
            f"Alert Name: {alert_name}\n"
            f"Alert Description:\n{alert_text}"
        )
        res = structured_llm.invoke(prompt)
        if isinstance(res, PhysicalPerilParameters):
            return res
        elif isinstance(res, dict):
            return PhysicalPerilParameters(**res)
        raise ValueError(f"Unexpected response format from structured LLM: {type(res)}")
    except Exception as e:
        logger.error(f"LLM peril extraction failed: {e}")
        raise


def distill_cap_alert(
    raw_alert: Union[Dict[str, Any], str],
    use_llm: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """Prunes raw CAP alert dictionary or JSON into a dense, standardized peril token string.

    Returns:
        Tuple of (distilled_context_string, metadata_stats_dict)
    """
    raw_str = raw_alert if isinstance(raw_alert, str) else json.dumps(raw_alert, default=str)
    raw_bytes = len(raw_str.encode("utf-8"))

    if isinstance(raw_alert, str):
        try:
            alert_dict = json.loads(raw_alert)
        except json.JSONDecodeError:
            alert_dict = {"alert_text": raw_alert, "alert_name": "Weather Alert"}
    else:
        alert_dict = raw_alert

    # Primary MCP keys with fallback for legacy CAP format
    alert_id = alert_dict.get("id") or alert_dict.get("alert_id") or "unknown-alert-id"
    alert_name = (
        alert_dict.get("alert_name")
        or alert_dict.get("alert_short_name")
        or alert_dict.get("event")
        or "Weather Alert"
    )
    alert_text = alert_dict.get("alert_text") or alert_dict.get("description") or alert_dict.get("headline") or ""

    # Extract physical perils from narrative alert text
    perils = extract_perils_with_llm(alert_text=alert_text, alert_name=alert_name, use_llm=use_llm)

    # Lead time is parsed from text; if unspecified, do not fabricate an arbitrary number
    lead_time_str = f"~{perils.lead_time_minutes} minutes" if perils.lead_time_minutes is not None else "Unspecified in alert"

    # Format peril values with explicit "Not specified" rather than misleading 0 or fabrications
    wind_str = f"{perils.wind_gust_kmh} km/h" if perils.wind_gust_kmh is not None else "Not specified"
    rain_str = f"{perils.rainfall_mm} mm" if perils.rainfall_mm is not None else "Not specified"
    snow_str = f"{perils.snowfall_cm} cm" if perils.snowfall_cm is not None else "Not specified"
    hail_str = f"YES ({perils.hail_descriptor or f'{perils.hail_diameter_cm}cm'})" if perils.hail_detected else "NO"
    tornado_str = "YES (EXTREME DANGER)" if perils.tornado_risk else "NO"
    freezing_rain_str = "YES" if perils.freezing_rain else "NO"

    # Build concise distilled output string
    lines = [
        f"[DISTILLED ECCC METEOROLOGICAL ALERT: {alert_id}]",
        f"Event: {perils.alert_name} (Active: {perils.is_active})",
        f"Physical Summary: {perils.physical_summary}",
        (
            f"Peril Metrics: Wind={wind_str} | "
            f"Hail={hail_str} | "
            f"Rain={rain_str} | "
            f"Snow={snow_str} | "
            f"Tornado={tornado_str} | "
            f"Freezing Rain={freezing_rain_str}"
        ),
        f"Temporal Window / Lead Time: {lead_time_str}",
    ]
    distilled_str = "\n".join(lines)
    distilled_bytes = len(distilled_str.encode("utf-8"))

    compression_ratio = max(0.0, 1.0 - (distilled_bytes / max(raw_bytes, 1)))

    metadata = {
        "raw_bytes": raw_bytes,
        "distilled_bytes": distilled_bytes,
        "compression_ratio": round(compression_ratio, 4),
        "compression_percent": f"{round(compression_ratio * 100, 1)}%",
        "perils": perils.model_dump(),
    }

    return distilled_str, metadata


def distill_property_context(property_row: Dict[str, Any]) -> str:
    """Prunes property database row into a structured dwelling vulnerability profile.
    
    Avoids fabricating structural attributes when fields are missing or NULL; instead,
    explicitly labels them as UNKNOWN to prevent misleading downstream risk evaluation.
    """
    p_id = property_row.get("id") or "UNKNOWN"
    address = property_row.get("address") or ""
    city = property_row.get("city") or ""
    prov = property_row.get("province") or ""
    postal = property_row.get("postal_code") or ""
    lat = property_row.get("latitude")
    lon = property_row.get("longitude")

    dwelling = property_row.get("dwelling_type") or "UNKNOWN"
    roof_type = property_row.get("roof_type") or "UNKNOWN"
    roof_age_raw = property_row.get("roof_age_years")
    roof_age_str = f"{roof_age_raw} years old" if roof_age_raw is not None else "age UNKNOWN"
    basement = property_row.get("basement_type") or "UNKNOWN"

    raw_sump = property_row.get("has_sump_pump")
    sump_str = "YES" if raw_sump in (1, True, "1") else ("NO" if raw_sump in (0, False, "0") else "UNKNOWN")

    raw_bwater = property_row.get("has_backwater_valve")
    bwater_str = "YES" if raw_bwater in (1, True, "1") else ("NO" if raw_bwater in (0, False, "0") else "UNKNOWN")

    first_name = property_row.get("first_name") or ""
    last_name = property_row.get("last_name") or ""
    name_str = f"{first_name} {last_name}".strip() or "UNKNOWN"
    phone = property_row.get("phone") or "Unlisted"
    email = property_row.get("email") or "Unlisted"

    return (
        f"[PROPERTY VULNERABILITY PROFILE: {p_id}]\n"
        f"Location: {address}, {city}, {prov} {postal} (Coords: {lat}, {lon})\n"
        f"Dwelling: {dwelling} | Roof: {roof_type} ({roof_age_str})\n"
        f"Basement: {basement} | Sump Pump: {sump_str} | "
        f"Backwater Valve: {bwater_str}\n"
        f"Policyholder: {name_str} | Contact: {phone} | {email}"
    )


def distill_policy_context(policy_row: Dict[str, Any]) -> str:
    """Formats policy coverages and explicitly flags critical protection gaps."""
    p_num = policy_row.get("policy_number", "POL-UNKNOWN")
    base_ded = policy_row.get("base_deductible", 1000.0)
    wind_ded = policy_row.get("wind_hail_deductible", 1500.0)
    sewer_endorsed = bool(policy_row.get("sewer_backup_endorsed", 0))
    overland_endorsed = bool(policy_row.get("overland_water_endorsed", 0))

    sewer_str = "YES (Covered)" if sewer_endorsed else "NO - CRITICAL GAP: Basement sewer backup damage is UNINSURED"
    overland_str = "YES (Covered)" if overland_endorsed else "NO - CRITICAL GAP: Surface overland flood runoff is UNINSURED"

    return (
        f"[POLICY COVERAGE & ENDORSEMENTS: {p_num}]\n"
        f"Base Deductible: ${base_ded:,.2f} | Wind/Hail Deductible: ${wind_ded:,.2f}\n"
        f"Sewer Backup Endorsement: {sewer_str}\n"
        f"Overland Water Endorsement: {overland_str}"
    )
