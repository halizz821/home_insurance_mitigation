"""Live test script to inspect extract_perils_with_llm and distill_cap_alert on real-time alerts."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables and API keys
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / "property_agent" / ".env")
load_dotenv(PROJECT_ROOT / ".env")

# Ensure packages are on path
sys.path.insert(0, str(PROJECT_ROOT / "property_agent"))
sys.path.insert(0, str(PROJECT_ROOT / "sentinel_system"))

from tools.mcp_client import EnvironmentCanadaMCPClient
from context.distillers import extract_perils_with_llm, distill_cap_alert


def main():
    # 1. Fetch real-time active alerts from Environment Canada MCP
    print("Fetching active alerts from Environment Canada...")
    client = EnvironmentCanadaMCPClient()
    res = client.search_alerts(province="ON")
    alerts = res.get("alerts", [])

    if not alerts:
        print("No active alerts currently reported in ON.")
        return

    # Pick the first alert with narrative text
    alert = next((a for a in alerts if a.get("alert_text")), alerts[0])

    print("=" * 70)
    print("REAL-TIME ALERT DETAILS")
    print("=" * 70)
    print(f"ID:          {alert.get('id')}")
    print(f"Name:        {alert.get('alert_name')}")
    print(f"Zone:        {alert.get('feature_name')}")
    print(f"Description:\n{alert.get('alert_text')}\n")

    # 2. Test extract_perils_with_llm
    print("=" * 70)
    print("1. extract_perils_with_llm (STRUCTURED PYDANTIC OBJECT)")
    print("=" * 70)
    perils = extract_perils_with_llm(
        alert_text=alert.get("alert_text", ""),
        alert_name=alert.get("alert_name", ""),
        use_llm=True,
    )
    print(json.dumps(perils.model_dump(), indent=2))

    # 3. Test distill_cap_alert
    print("\n" + "=" * 70)
    print("2. distill_cap_alert (COMPACT CONTEXT INJECTED INTO PROMPT)")
    print("=" * 70)
    distilled_str, meta = distill_cap_alert(alert, use_llm=True)
    print(distilled_str)

    print("\n" + "-" * 70)
    print(f"Raw Bytes:        {meta['raw_bytes']} B")
    print(f"Distilled Bytes:  {meta['distilled_bytes']} B")
    print(f"Pruned Tokens:    {meta['compression_percent']}")
    print("-" * 70)


if __name__ == "__main__":
    main()
