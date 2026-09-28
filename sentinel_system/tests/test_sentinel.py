"""Unit tests for Sentinel Agent scanner and catastrophe risk filtering."""

import json
from pathlib import Path
import tempfile
import pytest

from db.database import init_db
from scanner.sentinel_agent import SentinelAgent
from scanner.schemas import AtRiskPropertyCandidate


@pytest.fixture
def test_env():
    """Sets up a temporary SQLite database and SentinelAgent instance."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_db:
        db_path = Path(f_db.name)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_out:
        export_path = Path(f_out.name)

    init_db(db_path, force_seed=True)
    sentinel = SentinelAgent(db_path=db_path)

    yield sentinel, db_path, export_path

    if db_path.exists():
        db_path.unlink()
    if export_path.exists():
        export_path.unlink()


def test_classify_perils():
    """Verifies that only property-threatening warnings are accepted and advisories rejected."""
    # Accepted severe property perils
    severe_ts = {
        "alert_name": "Severe thunderstorm warning in effect",
        "alert_type": "warning",
        "status": "active",
    }
    ok, peril = SentinelAgent.classify_peril(severe_ts)
    assert ok is True
    assert peril == "Severe Thunderstorm Warning"

    tornado = {
        "alert_name": "Tornado warning",
        "alert_type": "warning",
        "status": "active",
    }
    ok, peril = SentinelAgent.classify_peril(tornado)
    assert ok is True
    assert peril == "Tornado Warning"

    snow = {
        "alert_name": "Snowfall warning in effect",
        "alert_type": "warning",
        "status": "active",
    }
    ok, peril = SentinelAgent.classify_peril(snow)
    assert ok is True
    assert peril == "Snowfall Warning"

    # Rejected non-structural advisories / statements
    fog = {
        "alert_name": "Fog advisory in effect",
        "alert_type": "advisory",
        "status": "active",
    }
    ok, _ = SentinelAgent.classify_peril(fog)
    assert ok is False

    ended_warning = {
        "alert_name": "Tornado warning",
        "alert_type": "warning",
        "status": "ended",
    }
    ok, _ = SentinelAgent.classify_peril(ended_warning)
    assert ok is False


def test_infer_urgency_severity():
    """Verifies standard urgency and severity inference."""
    urgency, severity = SentinelAgent.infer_urgency_severity("Tornado Warning")
    assert urgency == "Immediate"
    assert severity == "Extreme"

    urgency, severity = SentinelAgent.infer_urgency_severity("Severe Thunderstorm Warning")
    assert urgency == "Immediate"
    assert severity == "Severe"

    urgency, severity = SentinelAgent.infer_urgency_severity("Snowfall Warning", risk_colour="red")
    assert urgency == "Expected"
    assert severity == "Severe"


def test_scan_national_portfolio(test_env):
    """Verifies end-to-end macro scanning against simulated severe weather events with GIS polygons."""
    sentinel, db_path, export_path = test_env

    simulated_alerts = [
        # Kingston Thunderstorm polygon covering all 10 Kingston properties
        {
            "id": "eccc:alert:ts-kingston",
            "feature_id": "043200",
            "feature_name": "Kingston - Odessa - Frontenac Islands",
            "province": "ON",
            "alert_code": "severe_thunderstorm_warning",
            "alert_type": "warning",
            "alert_name": "Severe thunderstorm warning in effect",
            "alert_short_name": "Severe thunderstorm",
            "alert_text": "Severe thunderstorm with large hail and damaging winds.",
            "risk_colour": "red",
            "status": "active",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-76.65, 44.15],
                        [-76.35, 44.15],
                        [-76.35, 44.35],
                        [-76.65, 44.35],
                        [-76.65, 44.15],
                    ]
                ],
            },
        },
        # Ottawa Tornado Warning polygon covering all 10 Ottawa properties
        {
            "id": "eccc:alert:tor-ottawa",
            "feature_id": "043100",
            "feature_name": "Ottawa (Kanata - Orléans)",
            "province": "ON",
            "alert_code": "tornado_warning",
            "alert_type": "warning",
            "alert_name": "Tornado warning in effect",
            "alert_short_name": "Tornado",
            "alert_text": "Tornado on the ground. Seek immediate shelter.",
            "risk_colour": "red",
            "status": "active",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-75.85, 45.30],
                        [-75.50, 45.30],
                        [-75.50, 45.55],
                        [-75.85, 45.55],
                        [-75.85, 45.30],
                    ]
                ],
            },
        },
        # Toronto Fog Advisory - ignored by peril classifier
        {
            "id": "eccc:alert:fog-toronto",
            "feature_id": "043400",
            "feature_name": "City of Toronto",
            "province": "ON",
            "alert_code": "fog_advisory",
            "alert_type": "advisory",
            "alert_name": "Fog advisory in effect",
            "alert_short_name": "Fog",
            "status": "active",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-79.55, 43.55],
                        [-79.20, 43.55],
                        [-79.20, 43.75],
                        [-79.55, 43.75],
                        [-79.55, 43.55],
                    ]
                ],
            },
        },
    ]

    candidates = sentinel.scan_national_portfolio(
        alerts_override=simulated_alerts,
        export_path=str(export_path),
    )

    # 10 properties in Kingston + 10 properties in Ottawa = 20 candidates
    assert len(candidates) == 20

    # Ensure all candidates conform to the required Pydantic model
    for c in candidates:
        assert isinstance(c, AtRiskPropertyCandidate)
        assert c.property_id.startswith("HOM-")
        assert c.policy_id.startswith("POL-")
        assert c.address
        assert "latitude" in c.coordinates
        assert "longitude" in c.coordinates
        assert c.triggering_alert_id in ["eccc:alert:ts-kingston", "eccc:alert:tor-ottawa"]
        assert c.feature_id in ["043200", "043100"]
        assert c.triggering_event in ["Severe Thunderstorm Warning", "Tornado Warning"]
        assert c.urgency in ["Immediate", "Expected"]
        assert c.severity in ["Extreme", "Severe"]

    # Verify JSON export file
    assert export_path.exists()
    with open(export_path, "r", encoding="utf-8") as f:
        exported_data = json.load(f)
    assert len(exported_data) == 20
    assert exported_data[0]["property_id"] == candidates[0].property_id


def test_scan_strict_geometry_enforcement(test_env):
    """Verifies that alerts without geometry are strictly skipped without error."""
    sentinel, _, export_path = test_env

    alert_no_geom = [
        {
            "id": "eccc:alert:no-geom",
            "alert_code": "tornado_warning",
            "alert_type": "warning",
            "alert_name": "Tornado warning in effect",
            "status": "active",
            # geometry is deliberately omitted
        }
    ]

    candidates = sentinel.scan_national_portfolio(
        alerts_override=alert_no_geom,
        export_path=str(export_path),
    )
    assert len(candidates) == 0

