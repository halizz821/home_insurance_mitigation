"""LangGraph workflow definition for Property Mitigation Specialist.

Assembles cyclic ReAct tool execution and deterministic safety reflection loops.
"""

from typing import Literal
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import (
    AGENT_TOOLS,
    advisory_formulator,
    agent_reasoner,
    dispatch_node,
    safety_guardrail,
)
from .state import PropertyAgentState


def route_reasoner(state: PropertyAgentState) -> Literal["tool_node", "advisory_formulator"]:
    """Routes agent reasoner to tool execution if tools requested, otherwise to advisory formulator."""
    messages = state.get("messages", [])
    if not messages:
        return "advisory_formulator"

    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tool_node"

    return "advisory_formulator"


def route_safety_guardrail(state: PropertyAgentState) -> Literal["agent_reasoner", "dispatch_node"]:
    """Reflection edge: Routes back to reasoner if violations exist, otherwise proceeds to dispatch."""
    violations = state.get("safety_violations", [])
    iteration = state.get("iteration_count", 0)

    # Allow up to 3 reflection attempts to self-correct
    if violations and iteration < 3:
        return "agent_reasoner"

    return "dispatch_node"


def build_property_agent_graph():
    """Builds and compiles the Property Mitigation Specialist StateGraph."""
    workflow = StateGraph(PropertyAgentState)

    # Add workflow nodes
    workflow.add_node("agent_reasoner", agent_reasoner)
    workflow.add_node("tool_node", ToolNode(AGENT_TOOLS))
    workflow.add_node("advisory_formulator", advisory_formulator)
    workflow.add_node("safety_guardrail", safety_guardrail)
    workflow.add_node("dispatch_node", dispatch_node)

    # Initial entrypoint
    workflow.add_edge(START, "agent_reasoner")

    # Cyclic ReAct Tool execution
    workflow.add_conditional_edges(
        "agent_reasoner",
        route_reasoner,
        {
            "tool_node": "tool_node",
            "advisory_formulator": "advisory_formulator",
        },
    )
    workflow.add_edge("tool_node", "agent_reasoner")

    # From structured advisory formulation to safety guardrail
    workflow.add_edge("advisory_formulator", "safety_guardrail")

    # Safety Reflection Loop
    workflow.add_conditional_edges(
        "safety_guardrail",
        route_safety_guardrail,
        {
            "agent_reasoner": "agent_reasoner",
            "dispatch_node": "dispatch_node",
        },
    )

    # Terminal edge
    workflow.add_edge("dispatch_node", END)

    return workflow.compile()
