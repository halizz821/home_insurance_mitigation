"""Tests for LangGraph cyclic workflow and reflection routing."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from agent.graph import build_property_agent_graph, route_reasoner, route_safety_guardrail
from agent.state import PropertyAgentState


def test_graph_compilation():
    """Verifies that the LangGraph compiles cleanly with all nodes and edges."""
    graph = build_property_agent_graph()
    assert graph is not None


def test_route_reasoner_with_tools():
    """Verifies routing to tool_node when tool calls are present."""
    msg = AIMessage(content="", tool_calls=[{"name": "tool_get_property_details", "args": {"property_id": "HOM-1001"}, "id": "call_1"}])
    state: PropertyAgentState = {
        "messages": [msg],
        "property_id": "HOM-1001",
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": False,
    }
    destination = route_reasoner(state)
    assert destination == "tool_node"


def test_route_reasoner_without_tools():
    """Verifies routing to advisory_formulator when no tools are called."""
    msg = AIMessage(content="Deliberation complete. Formulate structured advisory...")
    state: PropertyAgentState = {
        "messages": [msg],
        "property_id": "HOM-1001",
        "safety_violations": [],
        "iteration_count": 0,
        "final_advisory": None,
        "demo_reflection_trigger": False,
        "scratchpad": None,
    }
    destination = route_reasoner(state)
    assert destination == "advisory_formulator"


def test_route_safety_guardrail_reflection_loop():
    """Verifies reflection loop routes back to agent_reasoner when violations exist."""
    state: PropertyAgentState = {
        "messages": [],
        "property_id": "HOM-1001",
        "safety_violations": ["RULE 1 VIOLATION: Ladder climb prohibited in 90 km/h winds."],
        "iteration_count": 1,
        "final_advisory": None,
        "demo_reflection_trigger": False,
    }
    destination = route_safety_guardrail(state)
    assert destination == "agent_reasoner"


def test_route_safety_guardrail_dispatch_on_success():
    """Verifies transition to dispatch_node when all invariants are satisfied."""
    state: PropertyAgentState = {
        "messages": [],
        "property_id": "HOM-1001",
        "safety_violations": [],
        "iteration_count": 1,
        "final_advisory": {"safety_status": "VERIFIED_SAFE"},
        "demo_reflection_trigger": False,
    }
    destination = route_safety_guardrail(state)
    assert destination == "dispatch_node"
