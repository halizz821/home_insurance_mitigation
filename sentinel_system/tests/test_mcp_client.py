"""Unit and integration tests for Environment Canada MCP client wrapper."""

import pytest
from tools.mcp_client import EnvironmentCanadaMCPClient


def test_mcp_client_initialization():
    """Verifies that MCP client instantiates with default command and args."""
    client = EnvironmentCanadaMCPClient()
    assert "-m" in client.args
    assert "environment_canada_mcp" in client.args


def test_mcp_client_sync_get_alert_summary():
    """Verifies that the MCP client can communicate with the MCP server subprocess via stdio."""
    client = EnvironmentCanadaMCPClient()
    summary = client.get_alert_summary()
    assert isinstance(summary, dict)
    assert "active_alerts_count" in summary
    assert "total_features_scanned" in summary


def test_mcp_client_sync_search_alerts():
    """Verifies that synchronous search_alerts executes properly."""
    client = EnvironmentCanadaMCPClient()
    res = client.search_alerts(alert_type="warning", include_geometry=False)
    assert isinstance(res, dict)
    assert "alerts" in res
    assert "count" in res
    assert isinstance(res["alerts"], list)
