"""Unit tests for GIS Spatial Engine and zone mapper."""

import pytest
from scanner.zone_mapper import (
    parse_alert_geometry,
    get_geometry_bounding_box,
    is_property_inside_alert,
    match_properties_to_alert_polygon,
    map_location_name_to_fsas,
    map_alert_to_fsas,
    CITY_FSA_MAP,
)


@pytest.fixture
def sample_polygon_geojson():
    """Simple box covering longitude [-76.60, -76.40] and latitude [44.20, 44.30]."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-76.60, 44.20],
                [-76.40, 44.20],
                [-76.40, 44.30],
                [-76.60, 44.30],
                [-76.60, 44.20],
            ]
        ],
    }


@pytest.fixture
def sample_multipolygon_geojson():
    """MultiPolygon with two separate zones."""
    return {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [-76.60, 44.20],
                    [-76.50, 44.20],
                    [-76.50, 44.30],
                    [-76.60, 44.30],
                    [-76.60, 44.20],
                ]
            ],
            [
                [
                    [-75.80, 45.30],
                    [-75.60, 45.30],
                    [-75.60, 45.50],
                    [-75.80, 45.50],
                    [-75.80, 45.30],
                ]
            ],
        ],
    }


def test_parse_alert_geometry_valid(sample_polygon_geojson, sample_multipolygon_geojson):
    """Verifies parsing of valid Polygon and MultiPolygon GeoJSON."""
    poly = parse_alert_geometry(sample_polygon_geojson)
    assert poly.geom_type == "Polygon"
    assert not poly.is_empty

    multi = parse_alert_geometry(sample_multipolygon_geojson)
    assert multi.geom_type == "MultiPolygon"
    assert not multi.is_empty


def test_parse_alert_geometry_invalid():
    """Verifies strict geometry requirement and error handling."""
    with pytest.raises(ValueError, match="geometry is required"):
        parse_alert_geometry(None)

    with pytest.raises(ValueError, match="geometry is required"):
        parse_alert_geometry({})

    with pytest.raises(ValueError, match="must be a Polygon or MultiPolygon"):
        # Point is not a valid warning polygon
        parse_alert_geometry({"type": "Point", "coordinates": [-76.48, 44.23]})


def test_get_geometry_bounding_box(sample_polygon_geojson):
    """Verifies bounding box calculation."""
    min_lon, min_lat, max_lon, max_lat = get_geometry_bounding_box(sample_polygon_geojson)
    assert min_lon == -76.60
    assert min_lat == 44.20
    assert max_lon == -76.40
    assert max_lat == 44.30


def test_is_property_inside_alert(sample_polygon_geojson):
    """Verifies point-in-polygon containment test for inside and outside coordinates."""
    # Point inside polygon
    assert is_property_inside_alert(sample_polygon_geojson, latitude=44.25, longitude=-76.50) is True

    # Point outside polygon (too far north)
    assert is_property_inside_alert(sample_polygon_geojson, latitude=44.45, longitude=-76.50) is False

    # Point outside polygon (too far east)
    assert is_property_inside_alert(sample_polygon_geojson, latitude=44.25, longitude=-75.50) is False


def test_match_properties_to_alert_polygon(sample_polygon_geojson):
    """Verifies filtering a list of candidate property dicts."""
    properties = [
        {"id": "PROP-1", "latitude": 44.25, "longitude": -76.50, "city": "Kingston"},   # Inside
        {"id": "PROP-2", "latitude": 44.22, "longitude": -76.45, "city": "Kingston"},   # Inside
        {"id": "PROP-3", "latitude": 45.42, "longitude": -75.69, "city": "Ottawa"},     # Outside
        {"id": "PROP-4", "latitude": 51.04, "longitude": -114.07, "city": "Calgary"},   # Outside
    ]

    matched = match_properties_to_alert_polygon(sample_polygon_geojson, properties)
    assert len(matched) == 2
    matched_ids = [p["id"] for p in matched]
    assert "PROP-1" in matched_ids
    assert "PROP-2" in matched_ids
    assert "PROP-3" not in matched_ids


def test_legacy_city_mapping():
    """Verifies that legacy FSA utility functions remain functional."""
    kingston_fsas = map_location_name_to_fsas("Kingston")
    assert set(kingston_fsas) == set(CITY_FSA_MAP["kingston"])

    alert = {"feature_name": "City of Calgary"}
    assert "T2P" in map_alert_to_fsas(alert)
