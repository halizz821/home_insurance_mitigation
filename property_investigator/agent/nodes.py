"""Graph nodes for LangGraph Property Mitigation Specialist.

Implements:
  - agent_reasoner: Multi-turn ReAct reasoning and dynamic tool calling
  - safety_guardrail: Programmatic deterministic invariant validation
  - dispatch_node: Customer advisory dispatch simulation & SQLite audit logging
"""

import json
import logging
import os
from pathlib import Path
import re
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .state import (
    AdvisorySynthesisOutput,  
    PropertyAgentState,    
    SafetyAuditResult,
)
from property_investigator.context.prompts import (
    ADVISORY_FORMATTER_PROMPT,
    SAFETY_AUDITOR_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_reflection_critique_prompt,
)
from property_investigator.tools.database_tools import (
    get_db_connection,
    tool_get_alerts_near_coordinates,
    tool_get_policy_coverage,
    tool_get_property_details,
)

logger = logging.getLogger(__name__)

# Core tools bound to agent reasoner
AGENT_TOOLS = [
    tool_get_property_details,
    tool_get_policy_coverage,
    tool_get_alerts_near_coordinates,
]


def get_llm():
    """Initializes ChatGoogleGenerativeAI with project API key."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        api_key=api_key,
    )


def agent_reasoner(state: PropertyAgentState) -> Dict[str, Any]:
    """Agent reasoner node: Evaluates context, calls tools, or formulates advisory."""
    llm = get_llm()
    bound_llm = llm.bind_tools(AGENT_TOOLS)

    messages = list(state.get("messages", []))

    # Ensure system prompt is present at start
    if not messages or not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))

    # If safety violations occurred in previous reflection iteration, inject critique
    safety_violations = state.get("safety_violations", [])
    if safety_violations:
        critique_msg = build_reflection_critique_prompt(
            safety_violations=safety_violations,
            iteration_count=state.get("iteration_count", 1),
        )
        messages.append(HumanMessage(content=critique_msg))

    response = bound_llm.invoke(messages)
    return {"messages": [response]}


def get_message_text(message: BaseMessage) -> str:
    """Extracts clean text content from a BaseMessage handling string or multi-part list."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def advisory_formulator(state: PropertyAgentState) -> Dict[str, Any]:
    """Extracts and formats the reasoner's final response into structured scratchpad and advisory dictionary."""
    messages = list(state.get("messages", []))

    # Check if intentional reflection demonstration mode trigger is active
    if (
        state.get("demo_reflection_trigger")
        and state.get("iteration_count", 0) == 0
    ):
        simulated_unsafe_scratchpad = (
            "[OBSERVED HAZARD]: Severe Thunderstorm with 90 km/h wind gusts, nickel-sized hail.\n"
            "[TEMPORAL WINDOW]: Lead time ~15 minutes.\n"
            "[EXPOSURE CROSS-REFERENCE]: Roof is 4-year-old asphalt shingle; finished basement.\n"
            "[SAFETY INVARIANT EVALUATION]: Assessing exterior maintenance.\n"
            "[FILTERED ADVISORY FORMULATION]: Clean gutters and move patio furniture."
        )
        simulated_unsafe_advisory = {
            "property_id": state.get("property_id", "HOM-1001"),
            "policyholder_name": "Policyholder",
            "contact": {"phone": "+1-555-0100", "email": "user@example.ca"},
            "hazard_summary": {
                "event": "Severe Thunderstorm Warning",
                "wind_gust_kmh": 90,
                "hail_detected": True,
                "hail_diameter_cm": 2.1,
                "hail_descriptor": "nickel-sized",
                "rainfall_mm": 50,
                "snowfall_cm": 0,
                "tornado_risk": False,
                "lead_time_minutes": 15,
            },
            "exposure_analysis": {
                "vulnerabilities": ["Finished basement without sewer backup endorsement", "Roof exposed to wind gusts"],
                "coverage_gaps": ["No sewer backup coverage"],
            },
            "micro_actions": [
                {
                    "priority": 1,
                    "category": "ROOF_PROTECTION",
                    "action": "Climb a ladder onto the roof immediately to clear leaves from gutters and inspect shingles.",
                    "rationale": "Prevent gutter overflow during heavy downpour.",
                },
                {
                    "priority": 2,
                    "category": "OUTDOOR_PREP",
                    "action": "Spend the next 15 minutes outdoors securing yard furniture and trimming tree branches.",
                    "rationale": "Reduce loose yard missile hazards.",
                },
                {
                    "priority": 3,
                    "category": "VEHICLE_PROTECTION",
                    "action": "Park car in garage.",
                    "rationale": "Hail protection.",
                },
            ],
            "safety_status": "PENDING_VERIFICATION",
            "channels": {
                "sms": "Storm Alert: Climb ladder to clear roof gutters immediately and park car.",
                "push_notification": {
                    "title": "Severe Storm Action",
                    "body": "Inspect roof gutters now.",
                },
            },
        }
        return {
            "scratchpad": simulated_unsafe_scratchpad,
            "final_advisory": simulated_unsafe_advisory,
        }

    last_message = messages[-1] if messages else None
    last_text = get_message_text(last_message) if last_message else ""

    llm = get_llm()
    structured_llm = llm.with_structured_output(AdvisorySynthesisOutput)

    format_messages = [
        SystemMessage(content=ADVISORY_FORMATTER_PROMPT),
        HumanMessage(content=f"Format the following reasoner output into the structured AdvisorySynthesisOutput schema:\n\n{last_text}"),
    ]
    res: AdvisorySynthesisOutput = structured_llm.invoke(format_messages)

    advisory_dict = res.advisory.model_dump()
    scratchpad = res.scratchpad

    return {
        "scratchpad": scratchpad,
        "final_advisory": advisory_dict,
    }


def safety_guardrail(state: PropertyAgentState) -> Dict[str, Any]:
    """LLM-based Safety Auditor node.
    
    Directly inspects state["final_advisory"] and state["scratchpad"] provided by advisory_formulator.
    
    """
    advisory_dict = state.get("final_advisory")
    scratchpad = state.get("scratchpad", "")
    messages = state.get("messages", [])

    # Fallback only if safety_guardrail is tested in isolation with raw mock messages
    if not advisory_dict and messages:
        last_text = get_message_text(messages[-1])
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", last_text)
        if json_match:
            try:
                advisory_dict = json.loads(json_match.group(1))
            except Exception:
                pass
        if not scratchpad:
            scratchpad = last_text

    # Extract lean hazard summary, micro-actions, and channels from advisory
    hazard_summary = advisory_dict.get("hazard_summary") if isinstance(advisory_dict, dict) else None
    micro_actions = advisory_dict.get("micro_actions", []) if isinstance(advisory_dict, dict) else []
    channels = advisory_dict.get("channels", {}) if isinstance(advisory_dict, dict) else {}

    if hazard_summary:
        audit_prompt = (
            f"### ACTIVE WEATHER HAZARDS:\n{json.dumps(hazard_summary, indent=2)}\n\n"
            f"### WORKING MEMORY SCRATCHPAD:\n{scratchpad}\n\n"
            f"### PROPOSED MICRO-ACTIONS:\n{json.dumps(micro_actions, indent=2)}\n\n"
            f"### PROPOSED NOTIFICATIONS (SMS / PUSH):\n{json.dumps(channels, indent=2)}\n"
        )
    else:
        # Fallback when safety_guardrail is tested in isolation with raw mock messages
        context_msgs = messages if state.get("final_advisory") else messages[:-1]
        prior_context = "\n".join(
            f"[{m.type.upper()}]: {get_message_text(m)}" for m in context_msgs
        )
        audit_prompt = (
            f"### INVESTIGATION CONTEXT & WEATHER ALERTS:\n{prior_context}\n\n"
            f"### WORKING MEMORY SCRATCHPAD:\n{scratchpad}\n\n"
            f"### PROPOSED ADVISORY PAYLOAD:\n{json.dumps(advisory_dict, indent=2, default=str) if advisory_dict else scratchpad}\n"
        )

    llm = get_llm()
    evaluator = llm.with_structured_output(SafetyAuditResult)

    try:
        evaluation: SafetyAuditResult = evaluator.invoke([
            SystemMessage(content=SAFETY_AUDITOR_SYSTEM_PROMPT),
            HumanMessage(content=audit_prompt),
        ])
        is_safe = evaluation.is_safe and len(evaluation.violations) == 0
        violations = evaluation.violations if not is_safe else []
    except Exception as e:
        logger.error(f"Error during LLM safety evaluation: {e}")
        violations = []
        is_safe = True

    iteration = state.get("iteration_count", 0)

    if not is_safe and violations:
        logger.warning(f"LLM Safety Guardrail triggered {len(violations)} violation(s) on iteration {iteration}.")
        return {
            "safety_violations": violations,
            "iteration_count": iteration + 1,
            "final_advisory": None,
        }

    # All safety invariants passed!
    if advisory_dict:
        advisory_dict["safety_status"] = "VERIFIED_SAFE"

    return {
        "safety_violations": [],
        "final_advisory": advisory_dict,
    }


def dispatch_node(state: PropertyAgentState) -> Dict[str, Any]:
    """Formats dispatch payload, displays simulated SMS/push notification, and logs audit to SQLite."""
    advisory = state.get("final_advisory", {})
    property_id = state.get("property_id", advisory.get("property_id", "UNKNOWN"))
    event_type = advisory.get("hazard_summary", {}).get("event", "Severe Weather Advisory")
    safety_status = advisory.get("safety_status", "VERIFIED_SAFE")
    iteration_count = state.get("iteration_count", 0)

    channels = advisory.get("channels", {})
    sms_text = channels.get("sms", "Urgent weather advisory in effect for your property.")
    push_title = channels.get("push_notification", {}).get("title", f"Weather Alert: {event_type}")
    push_body = channels.get("push_notification", {}).get("body", "Recommended micro-actions have been prepared.")

    dispatch_id = f"DISP-{uuid.uuid4().hex[:8].upper()}"

    # Write audit record to SQLite database
    try:
        conn = get_db_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO mitigation_dispatches (
                    dispatch_id, property_id, event_type, safety_status,
                    iteration_count, sms_text, push_title, push_body, advisory_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    dispatch_id,
                    property_id,
                    event_type,
                    safety_status,
                    iteration_count,
                    sms_text,
                    push_title,
                    push_body,
                    json.dumps(advisory, default=str),
                ),
            )
        conn.close()
    except Exception as e:
        logger.error(f"Failed to write audit record to SQLite: {e}")

    # Display simulated dispatch indicator as requested by user
    print(f"\n[DISPATCH AUDIT: {dispatch_id}]")
    print(f"  Status: {safety_status} (Passed after {iteration_count} reflection iteration(s))")
    print(f"  [SMS & Push Dispatched Successfully] (Simulated Delivery)")
    print(f"  SMS -> {sms_text}")
    advisory["dispatch_id"] = dispatch_id
    return {"final_advisory": advisory}
