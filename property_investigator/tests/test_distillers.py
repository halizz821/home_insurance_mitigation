"""Tests for semantic distillation middleware and physical peril extraction."""

import pytest
from context.distillers import (
    PhysicalPerilParameters,
    extract_perils_with_llm,
    distill_cap_alert,
    distill_policy_context,
    distill_property_context,
)


def test_peril_extraction_llm(monkeypatch):
    """Verifies that extract_perils_with_llm invokes structured output properly."""
    expected_perils = PhysicalPerilParameters(
        alert_name="Severe thunderstorm warning in effect",
        is_active=True,
        tornado_risk=False,
        hail_detected=True,
        hail_diameter_cm=2.1,
        hail_descriptor="nickel-sized",
        wind_gust_kmh=90,
        rainfall_mm=50,
        snowfall_cm=None,
        snow_description=None,
        freezing_rain=False,
        lead_time_minutes=15,
        physical_summary="90 km/h wind gusts, nickel-sized hail, 50 mm rainfall",
    )

    class MockStructuredLLM:
        def invoke(self, prompt):
            return expected_perils

    class MockChatModel:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, schema):
            return MockStructuredLLM()

    monkeypatch.setattr("langchain_google_genai.ChatGoogleGenerativeAI", MockChatModel)
    monkeypatch.setenv("GOOGLE_API_KEY", "mock-key")

    perils = extract_perils_with_llm(
        alert_text="Severe thunderstorm with 90 km/h wind gusts and nickel-sized hail.",
        alert_name="Severe thunderstorm warning in effect",
    )
    assert perils.wind_gust_kmh == 90
    assert perils.hail_detected is True
    assert perils.hail_diameter_cm == 2.1
    assert perils.hail_descriptor == "nickel-sized"
    assert perils.rainfall_mm == 50
    assert perils.tornado_risk is False
    assert perils.lead_time_minutes == 15


def test_distill_cap_alert_compression(monkeypatch):
    """Verifies token/byte compression ratio calculation with peril extraction."""
    expected_perils = PhysicalPerilParameters(
        alert_name="Severe thunderstorm warning in effect",
        is_active=True,
        tornado_risk=False,
        hail_detected=True,
        hail_diameter_cm=2.1,
        hail_descriptor="nickel-sized",
        wind_gust_kmh=90,
        rainfall_mm=None,
        snowfall_cm=None,
        snow_description=None,
        freezing_rain=False,
        lead_time_minutes=None,
        physical_summary="Severe thunderstorm capable of 90 km/h winds and nickel hail",
    )

    monkeypatch.setattr(
        "context.distillers.extract_perils_with_llm",
        lambda *args, **kwargs: expected_perils,
    )

    raw_alert = {
        "id": "urn:eccc:alert:test",
        "alert_name": "Severe thunderstorm warning in effect",
        "alert_text": (
            "Environment Canada meteorologists are tracking a severe thunderstorm capable of "
            "producing 90 km/h wind gusts, nickel-sized hail and torrential downpours."
        ),
        "extra_verbose_xml_namespace": "http://uri.eccc.gc.ca/cap/namespaces/1.2" * 10,
        "huge_coordinate_array": [[[-76.5, 44.2], [-76.4, 44.2], [-76.4, 44.3], [-76.5, 44.3]]] * 5,
    }
    distilled_str, meta = distill_cap_alert(raw_alert)
    assert "[DISTILLED ECCC METEOROLOGICAL ALERT" in distilled_str
    assert meta["distilled_bytes"] < meta["raw_bytes"]
    assert meta["compression_ratio"] > 0.3


def test_distill_property_context():
    """Verifies property row context formatting."""
    row = {
        "id": "HOM-1001",
        "address": "100 Princess St",
        "city": "Kingston",
        "province": "ON",
        "postal_code": "K7L 2A3",
        "latitude": 44.2012,
        "longitude": -76.5220,
        "dwelling_type": "detached",
        "roof_type": "asphalt_shingle",
        "roof_age_years": 4,
        "basement_type": "finished",
        "has_sump_pump": 1,
        "has_backwater_valve": 1,
        "first_name": "Liam",
        "last_name": "Tremblay",
        "phone": "+1-613-555-1001",
        "email": "liam@example.ca",
    }
    distilled = distill_property_context(row)
    assert "HOM-1001" in distilled
    assert "finished" in distilled
    assert "Roof: asphalt_shingle (4 years old)" in distilled
    assert "Sump Pump: YES" in distilled
    assert "Backwater Valve: YES" in distilled


def test_distill_property_context_missing_and_null_fields():
    """Verifies that missing or NULL structural fields are rendered as UNKNOWN."""
    row = {
        "id": "HOM-9999",
        "dwelling_type": None,
        "roof_type": None,
        "roof_age_years": None,
        "basement_type": None,
        "has_sump_pump": None,
        "has_backwater_valve": None,
    }
    distilled = distill_property_context(row)
    assert "HOM-9999" in distilled
    assert "Dwelling: UNKNOWN" in distilled
    assert "Roof: UNKNOWN (age UNKNOWN)" in distilled
    assert "Basement: UNKNOWN" in distilled
    assert "Sump Pump: UNKNOWN" in distilled
    assert "Backwater Valve: UNKNOWN" in distilled
    assert "Policyholder: UNKNOWN" in distilled


def test_distill_policy_context_gap_detection():
    """Verifies policy coverage distillation explicitly highlights uninsured endorsements."""
    row = {
        "policy_number": "PNC-ON-2024001",
        "base_deductible": 500.0,
        "wind_hail_deductible": 1000.0,
        "sewer_backup_endorsed": 0,
        "overland_water_endorsed": 0,
    }
    distilled = distill_policy_context(row)
    assert "CRITICAL GAP: Basement sewer backup damage is UNINSURED" in distilled
    assert "CRITICAL GAP: Surface overland flood runoff is UNINSURED" in distilled
