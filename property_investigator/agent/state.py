"""Agent state and structured output schemas for LangGraph Property Mitigation Specialist.

Organized into:
  1. Advisory Component Schemas (Domain models for hazards, exposures, channels, and actions)
  2. LLM Structured Output Schemas (AdvisorySynthesisOutput and SafetyAuditResult)
  3. LangGraph Workflow State (PropertyAgentState TypedDict)
"""

from typing import Annotated, Any, Dict, List, Optional, TypedDict
import operator
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


# ============================================================================
# 1. Advisory Component Schemas
# ============================================================================

class MicroAction(BaseModel):
    priority: int = Field(description="Priority ranking 1, 2, or 3")
    category: str = Field(description="Category (e.g. INDOOR_WATER_PROTECTION, VEHICLE_PROTECTION, INDOOR_SHELTER, LIFE_SAFETY, POWER_PREPARATION)")
    action: str = Field(description="Direct, actionable imperative instruction")
    rationale: str = Field(description="Clear rationale linking weather peril to property exposure")


class PushNotification(BaseModel):
    title: str = Field(description="Push notification headline")
    body: str = Field(description="Concise push notification body text")


class ChannelPayload(BaseModel):
    sms: str = Field(description="Urgent, concise SMS message (<= 160 chars) highlighting highest priority micro-action and safety warning.")
    push_notification: PushNotification


class HazardSummary(BaseModel):
    event: str = Field(description="Name of the weather alert event")
    wind_gust_kmh: Optional[int] = Field(0, description="Max wind gusts in km/h if observed or 0")
    hail_detected: bool = Field(False, description="True if hail is detected")
    hail_diameter_cm: Optional[float] = Field(None, description="Hail diameter in cm")
    hail_descriptor: Optional[str] = Field(None, description="Hail descriptor, e.g. nickel-sized, golf-ball sized")
    rainfall_mm: Optional[float] = Field(0, description="Rainfall accumulation in mm")
    snowfall_cm: Optional[float] = Field(0, description="Snowfall accumulation in cm")
    tornado_risk: bool = Field(False, description="True if tornado risk is reported")
    lead_time_minutes: Optional[int] = Field(None, description="Estimated lead time in minutes before storm arrival. If no Lead time mentioned in the alert, dont assume any value and return No information available.")


class ExposureAnalysis(BaseModel):
    vulnerabilities: List[str] = Field(default_factory=list, description="List of structural vulnerabilities identified for this dwelling")
    coverage_gaps: List[str] = Field(default_factory=list, description="List of unendorsed policy coverage gaps")


class ContactInfo(BaseModel):
    phone: str = Field("", description="Phone number")
    email: str = Field("", description="Email address")


class AdvisoryPayload(BaseModel):
    property_id: str
    policyholder_name: str
    contact: ContactInfo = Field(default_factory=lambda: ContactInfo(phone="", email=""))
    hazard_summary: HazardSummary
    exposure_analysis: ExposureAnalysis
    micro_actions: List[MicroAction]
    safety_status: str = Field("PENDING_VERIFICATION", description="Safety status")
    channels: ChannelPayload


# ============================================================================
# 2. LLM Structured Output Schemas
# ============================================================================

class AdvisorySynthesisOutput(BaseModel):
    """Structured output schema directly providing deliberation scratchpad and final advisory."""
    scratchpad: str = Field(
        description="The structured working memory scratchpad containing [OBSERVED HAZARD], [TEMPORAL WINDOW], [EXPOSURE CROSS-REFERENCE], [SAFETY INVARIANT EVALUATION], and [FILTERED ADVISORY FORMULATION]."
    )
    advisory: AdvisoryPayload = Field(
        description="The complete, structured loss-mitigation advisory JSON payload."
    )


class SafetyAuditResult(BaseModel):
    """Schema for LLM-based Safety Auditor decision."""
    is_safe: bool = Field(
        description="True if all proposed actions strictly adhere to homeowner life-safety standards, False if any hazardous or reckless actions are proposed."
    )
    violations: List[str] = Field(
        default_factory=list,
        description="Detailed list of specific safety violations found. If violating Rule 1, must begin with 'RULE 1 VIOLATION (Ladder/Roof Ban): ...'. If violating Rule 2, must begin with 'RULE 2 VIOLATION (Imminent Arrival Ban): ...'."
    )
    critique_summary: Optional[str] = Field(
        None,
        description="Concise summary of safety feedback to guide the agent reasoner in self-correcting the proposal."
    )


# ============================================================================
# 3. LangGraph Workflow State
# ============================================================================

class PropertyAgentState(TypedDict):
    """LangGraph state schema for Property Mitigation Specialist."""
    messages: Annotated[List[BaseMessage], operator.add]
    property_id: str
    safety_violations: List[str]
    iteration_count: int
    final_advisory: Optional[Dict[str, Any]]
    demo_reflection_trigger: bool
    scratchpad: Optional[str]
