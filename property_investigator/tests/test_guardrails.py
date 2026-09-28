"""Tests for deterministic safety guardrails and invariant validation."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from agent.nodes import safety_guardrail
from agent.state import PropertyAgentState


def test_guardrail_rule_1_ladder_roof_ban_rejected():
    """Rule 1: Ladder or roof work must be rejected when winds >= 60 km/h or thunderstorm reported."""
    state: PropertyAgentState = {
        "messages": [
            HumanMessage(content="Thunderstorm with 90 km/h wind gusts and lightning active."),
            AIMessage(
                content=(
                    "```json\n"
                    "{\n"
                    '  "property_id": "HOM-1001",\n'
                    '  "micro_actions": [\n'
                    '    {"priority": 1, "action": "Climb ladder to inspect shingles and clean roof gutters", "rationale": "Clear drainage"}\n'
                    "  ]\n"
                    "}\n"
                    "```"
                )
            ),
        ],
        "property_id": "HOM-1001",
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": False,
    }

    result = safety_guardrail(state)
    assert len(result["safety_violations"]) > 0
    assert "RULE 1 VIOLATION" in result["safety_violations"][0]
    assert result["iteration_count"] == 1
    assert result["final_advisory"] is None


def test_guardrail_rule_2_imminent_arrival_ban_rejected():
    """Rule 2: Outdoor yard work must be rejected if lead time < 20 min or Tornado Warning."""
    state: PropertyAgentState = {
        "messages": [
            HumanMessage(content="Tornado warning in effect. Lead time 10 minutes."),
            AIMessage(
                content=(
                    "```json\n"
                    "{\n"
                    '  "property_id": "HOM-1011",\n'
                    '  "micro_actions": [\n'
                    '    {"priority": 1, "action": "Spend 10 minutes in yard securing outdoor patio furniture", "rationale": "Prevent flying objects"}\n'
                    "  ]\n"
                    "}\n"
                    "```"
                )
            ),
        ],
        "property_id": "HOM-1011",
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": False,
    }

    result = safety_guardrail(state)
    assert len(result["safety_violations"]) > 0
    assert "RULE 2 VIOLATION" in result["safety_violations"][0]
    assert result["iteration_count"] == 1
    assert result["final_advisory"] is None


def test_guardrail_compliant_indoor_actions_accepted():
    """Verifies that safe, compliant indoor actions pass safety invariants."""
    state: PropertyAgentState = {
        "messages": [
            HumanMessage(content="Severe thunderstorm with 90 km/h wind gusts and nickel hail. Lead time 15 minutes."),
            AIMessage(
                content=(
                    "```json\n"
                    "{\n"
                    '  "property_id": "HOM-1001",\n'
                    '  "micro_actions": [\n'
                    '    {"priority": 1, "category": "INDOOR_WATER_PROTECTION", "action": "Elevate critical items and electronics off finished basement floor.", "rationale": "Missing sewer endorsement"},\n'
                    '    {"priority": 2, "category": "VEHICLE_PROTECTION", "action": "Park vehicles inside garage.", "rationale": "Nickel hail protection"},\n'
                    '    {"priority": 3, "category": "INDOOR_SHELTER", "action": "Shelter indoors away from exterior windows.", "rationale": "90 km/h winds"}\n'
                    "  ]\n"
                    "}\n"
                    "```"
                )
            ),
        ],
        "property_id": "HOM-1001",
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": False,
    }

    result = safety_guardrail(state)
    assert len(result["safety_violations"]) == 0
    assert result["final_advisory"] is not None
    assert result["final_advisory"]["safety_status"] == "VERIFIED_SAFE"
