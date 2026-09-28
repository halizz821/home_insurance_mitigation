"""Tests for database tools and SQLite audit records."""

import json
import pytest
from tools.database_tools import (
    get_db_connection,
    tool_get_alerts_near_coordinates,
    tool_get_policy_coverage,
    tool_get_property_details,
)


def test_tool_get_property_details_existing():
    """Verifies retrieval and distillation of property details from database."""
    res = tool_get_property_details.invoke({"property_id": "HOM-1001"})
    assert "HOM-1001" in res
    assert "Kingston" in res
    assert "asphalt_shingle" in res


def test_tool_get_property_details_missing():
    """Verifies error handling for non-existent property ID."""
    res = tool_get_property_details.invoke({"property_id": "HOM-999999"})
    assert "[ERROR]" in res


def test_tool_get_policy_coverage():
    """Verifies retrieval and coverage gap detection from database."""
    res = tool_get_policy_coverage.invoke({"property_id": "HOM-1001"})
    assert "PNC-ON-2024001" in res
    assert "Sewer Backup Endorsement" in res


def test_tool_get_alerts_near_coordinates_matched(monkeypatch):
    """Verifies retrieval and immediate distillation of perils for coordinates."""
    mock_alert = {
        "id": "urn:eccc:alert:20260922:on-kingston-ts-warning",
        "alert_name": "Severe thunderstorm warning in effect",
        "alert_text": "Environment Canada meteorologists are tracking a severe thunderstorm producing 90 km/h wind gusts.",
    }
    monkeypatch.setattr(
        "tools.database_tools.default_mcp_client.get_alerts_near_coordinates",
        lambda **kwargs: {"count": 1, "alerts": [mock_alert]},
    )
    res = tool_get_alerts_near_coordinates.invoke({"latitude": 44.2012, "longitude": -76.5220})
    assert "DISTILLED ECCC METEOROLOGICAL ALERT" in res
    assert "90 km/h" in res


def test_tool_get_alerts_near_coordinates_no_match(monkeypatch):
    """Verifies response when no active alerts intersect coordinates."""
    monkeypatch.setattr(
        "tools.database_tools.default_mcp_client.get_alerts_near_coordinates",
        lambda **kwargs: {"count": 0, "alerts": []},
    )
    res = tool_get_alerts_near_coordinates.invoke({"latitude": 44.2012, "longitude": -76.5220})
    assert "No active Environment Canada weather alerts" in res
