"""Standalone script / Jupyter interactive script to test MCP search_alerts and inspect keys."""

import json
from pathlib import Path
import sys

# Ensure sentinel_system is on path
PROJECT_ROOT = Path(__file__).resolve().parent
if (PROJECT_ROOT / "sentinel_system").exists():
    sys.path.insert(0, str(PROJECT_ROOT / "sentinel_system"))

from tools.mcp_client import EnvironmentCanadaMCPClient


def main():
    print("Connecting to Environment Canada Weather Alerts MCP client...")
    client = EnvironmentCanadaMCPClient()

    # Query active weather alerts from Environment Canada
    print("Calling search_alerts(province='ON')...\n")
    res = client.search_alerts(province="ON")

    print(f"Top-level response keys: {list(res.keys())}")
    print(f"Total alerts returned: {res.get('count', 0)}\n")

    alerts = res.get("alerts", [])
    if alerts:
        sample_alert = alerts[0]

        print("=" * 65)
        print("ALL KEYS IN AN ALERT DICTIONARY:")
        print("=" * 65)
        for key in sample_alert.keys():
            print(f" - {key}")

        print("\n" + "=" * 65)
        print("KEY-VALUE PAIRS (FIRST ALERT):")
        print("=" * 65)
        for key, value in sample_alert.items():
            if key == "alert_text" and isinstance(value, str):
                preview = value.replace("\n", " ")[:120] + "..."
                print(f"{key:22}: {preview}")
            else:
                print(f"{key:22}: {value}")

        print("\n" + "=" * 65)
        print("RAW JSON OF FIRST ALERT:")
        print("=" * 65)
        print(json.dumps(sample_alert, indent=2, ensure_ascii=False))
    else:
        print("No active alerts currently matching query.")


if __name__ == "__main__":
    main()
