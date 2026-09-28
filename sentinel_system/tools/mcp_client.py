"""Environment Canada Weather Alerts MCP integration using langchain.mcp."""

import asyncio
import concurrent.futures
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from langchain.mcp import MCPAdapter

logger = logging.getLogger(__name__)

# Standard Environment Canada MCP server configuration
WEATHER_MCP_CONFIG = {
    "mcpServers": {
        "environment_canada": {
            "command": sys.executable,
            "args": ["-m", "environment_canada_mcp"],
            "env": os.environ,
        }
    }
}


def _get_adapter() -> MCPAdapter:
    """Creates an MCPAdapter instance configured for Environment Canada."""
    return MCPAdapter(WEATHER_MCP_CONFIG)


# In-memory simulated alerts for offline/evaluation mode
_simulated_alerts: Optional[List[Dict[str, Any]]] = None


def set_simulated_alerts(alerts: Optional[List[Dict[str, Any]]]) -> None:
    """Activates simulated weather alert mode, bypassing live MCP."""
    global _simulated_alerts
    _simulated_alerts = alerts


def disable_simulated_alerts() -> None:
    """Disables simulated alerts and restores live MCP queries."""
    global _simulated_alerts
    _simulated_alerts = None


def is_simulated() -> bool:
    """Returns True if simulated weather alert mode is active."""
    return _simulated_alerts is not None


def _parse_tool_result(result: Any) -> Dict[str, Any]:
    """Parses tool output from MCPAdapter into a clean Python dictionary."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_text": text}
            elif hasattr(block, "text"):
                text = getattr(block, "text")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_text": text}
            elif isinstance(block, str):
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    return {"raw_text": block}
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw_text": result}
    return {}


def _run_sync(coro):
    """Executes a coroutine synchronously, handling running event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()
    else:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return asyncio.run(coro)


async def _async_call_mcp_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Invokes an MCP tool directly via MCPAdapter."""
    clean_args = {k: v for k, v in kwargs.items() if v is not None}
    async with _get_adapter() as adapter:
        tools = {t.name: t for t in await adapter.list_tools()}
        if tool_name not in tools:
            raise KeyError(f"Tool '{tool_name}' not found on MCP server. Available: {list(tools.keys())}")
        result = await tools[tool_name].ainvoke(clean_args)
        return _parse_tool_result(result)


def _call_mcp_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Synchronously invokes an MCP tool via MCPAdapter."""
    return _run_sync(_async_call_mcp_tool(tool_name, **kwargs))


# ------------------------------------------------------------------------------
# Spatial Helper for Simulated Alerts
# ------------------------------------------------------------------------------

def _point_in_polygon(lat: float, lon: float, coordinates: List[List[float]]) -> bool:
    """Ray-casting test for whether (lat, lon) is inside a GeoJSON polygon ring."""
    if not coordinates:
        return False
    inside = False
    n = len(coordinates)
    p1_lon, p1_lat = coordinates[0]
    for i in range(1, n + 1):
        p2_lon, p2_lat = coordinates[i % n]
        if min(p1_lat, p2_lat) < lat <= max(p1_lat, p2_lat):
            if lon <= max(p1_lon, p2_lon):
                if p1_lat != p2_lat:
                    x_inters = (lat - p1_lat) * (p2_lon - p1_lon) / (p2_lat - p1_lat) + p1_lon
                if p1_lon == p2_lon or lon <= x_inters:
                    inside = not inside
        p1_lon, p1_lat = p2_lon, p2_lat
    return inside


def _is_coord_in_alert(lat: float, lon: float, alert: Dict[str, Any]) -> bool:
    """Checks if coordinates (lat, lon) fall within alert geometry."""
    geom = alert.get("geometry", {})
    g_type = geom.get("type", "")
    coords = geom.get("coordinates", [])

    if g_type == "Polygon" and coords:
        ring = coords[0]
        if _point_in_polygon(lat, lon, ring):
            return True
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        if min(lats) - 0.05 <= lat <= max(lats) + 0.05 and min(lons) - 0.05 <= lon <= max(lons) + 0.05:
            return True
    elif g_type == "MultiPolygon" and coords:
        for poly in coords:
            if poly and _point_in_polygon(lat, lon, poly[0]):
                return True
    return False


# ------------------------------------------------------------------------------
# Synchronous Client Interface
# ------------------------------------------------------------------------------

class EnvironmentCanadaMCPClient:
    """Client accessing Environment Canada weather alerts via langchain.mcp."""

    def __init__(self, command: Optional[str] = None, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        self.command = command or sys.executable
        self.args = args or ["-m", "environment_canada_mcp"]
        self.env = env or os.environ

    def get_alert_summary(self, province: Optional[str] = None) -> Dict[str, Any]:
        """Fetches national or provincial weather alert summary."""
        return _call_mcp_tool("get_alert_summary", province=province.upper() if province else None)

    def search_alerts(self, **kwargs) -> Dict[str, Any]:
        """Searches active weather alerts with optional filters and geometry."""
        if is_simulated():
            alerts = _simulated_alerts or []
            p = kwargs.get("province")
            t = kwargs.get("alert_type")
            filtered = [
                a for a in alerts
                if (not p or a.get("province", "").upper() == p.upper())
                and (not t or a.get("alert_type", "").lower() == t.lower())
            ]
            return {"count": len(filtered), "alerts": filtered}
        return _call_mcp_tool("search_alerts", **kwargs)

    def get_alerts_near_coordinates(self, latitude: float, longitude: float, language: str = "en") -> Dict[str, Any]:
        """Queries weather alerts intersecting specific coordinates."""
        if is_simulated():
            matching = [a for a in (_simulated_alerts or []) if _is_coord_in_alert(latitude, longitude, a)]
            return {
                "query_location": {"latitude": latitude, "longitude": longitude},
                "count": len(matching),
                "alerts": matching,
            }
        return _call_mcp_tool("get_alerts_near_coordinates", latitude=latitude, longitude=longitude, language=language)

    def set_simulated_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Enables simulated alerts on this client."""
        set_simulated_alerts(alerts)

    def disable_simulated_alerts(self) -> None:
        """Disables simulated alerts on this client."""
        disable_simulated_alerts()


# Global singleton instance
default_mcp_client = EnvironmentCanadaMCPClient()
