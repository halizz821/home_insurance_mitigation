"""Pydantic schemas for Sentinel scanner and at-risk candidate models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AtRiskPropertyCandidate(BaseModel):
    """Pydantic model representing an audited at-risk property candidate for Agent 2."""

    property_id: str = Field(..., description="Unique property ID, e.g. 'HOM-1001'")
    policy_id: str = Field(..., description="Unique policy ID, e.g. 'POL-1001'")
    address: str = Field(..., description="Full street address of the property")
    coordinates: Dict[str, float] = Field(
        ...,
        description="Coordinates dict with 'latitude' and 'longitude'",
    )
    triggering_alert_id: str = Field(
        ...,
        description="Unique identifier of the ECCC alert triggering the exposure",
    )
    feature_id: Optional[str] = Field(
        default=None,
        description="Environment Canada weather alert forecast zone / polygon ID, e.g. '043200'",
    )
    triggering_event: str = Field(
        ...,
        description="Identified peril, e.g. 'Severe Thunderstorm Warning', 'Wind Warning'",
    )
    headline: str = Field(..., description="Alert headline or short summary description")
    urgency: str = Field(..., description="Urgency level, e.g. 'Immediate', 'Expected', 'Future'")
    severity: str = Field(..., description="Severity level, e.g. 'Extreme', 'Severe', 'Moderate'")

    # Optional enriched underwriting and policy context for Agent 2
    city: Optional[str] = Field(default=None, description="City name")
    province: Optional[str] = Field(default=None, description="Two-letter province code")
    postal_code: Optional[str] = Field(default=None, description="Canadian postal code")
    fsa: Optional[str] = Field(default=None, description="3-character Forward Sortation Area")
    dwelling_type: Optional[str] = Field(default=None, description="Dwelling type")
    roof_type: Optional[str] = Field(default=None, description="Roof material")
    roof_age_years: Optional[int] = Field(default=None, description="Age of roof in years")
    basement_type: Optional[str] = Field(default=None, description="Basement foundation type")
    has_sump_pump: Optional[bool] = Field(default=None, description="Presence of sump pump")
    has_backwater_valve: Optional[bool] = Field(default=None, description="Presence of backwater valve")
    policy_number: Optional[str] = Field(default=None, description="Policy number")
    base_deductible: Optional[float] = Field(default=None, description="Standard deductible")
    wind_hail_deductible: Optional[float] = Field(default=None, description="Wind/hail deductible")
    sewer_backup_endorsed: Optional[bool] = Field(default=None, description="Sewer backup endorsement status")
    overland_water_endorsed: Optional[bool] = Field(default=None, description="Overland water endorsement status")
    policyholder_name: Optional[str] = Field(default=None, description="Full name of insured")
    policyholder_phone: Optional[str] = Field(default=None, description="Insured contact phone")
    policyholder_email: Optional[str] = Field(default=None, description="Insured contact email")


class ScanSummary(BaseModel):
    """Summary of a Sentinel macro scan run."""

    scan_timestamp: str
    total_warnings_detected: int
    property_perils_matched: int
    impacted_fsas: List[str]
    at_risk_properties_count: int
    candidates_by_peril: Dict[str, int]
    candidates_by_city: Dict[str, int]
