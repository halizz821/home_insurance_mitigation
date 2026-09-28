"""GIS Spatial Engine for Environment Canada weather alert geometry correlation.

Uses Shapely for point-in-polygon containment and spatial indexing across Canada.
All GeoJSON alerts must include valid polygon geometry.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

logger = logging.getLogger(__name__)


def parse_alert_geometry(geometry: Any) -> BaseGeometry:
    """Parses and strictly validates GeoJSON geometry into a Shapely geometry object.

    Args:
        geometry: GeoJSON geometry dictionary (e.g. {"type": "Polygon", "coordinates": [...]})
                  or existing Shapely BaseGeometry.

    Returns:
        Validated Shapely geometry object (Polygon or MultiPolygon).

    Raises:
        ValueError: If geometry is missing, empty, or not a Polygon/MultiPolygon.
    """
    if not geometry:
        raise ValueError("GeoJSON alert geometry is required and cannot be empty.")

    if isinstance(geometry, BaseGeometry):
        geom = geometry
    elif isinstance(geometry, dict):
        try:
            geom = shape(geometry)
        except Exception as e:
            raise ValueError(f"Failed to parse GeoJSON geometry: {e}") from e
    else:
        raise ValueError(f"Unsupported geometry format: {type(geometry)}")

    if geom.is_empty:
        raise ValueError("Parsed GeoJSON geometry is empty.")

    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(
            f"Alert geometry must be a Polygon or MultiPolygon, got '{geom.geom_type}'."
        )

    return geom


def get_geometry_bounding_box(geometry: Any) -> Tuple[float, float, float, float]:
    """Calculates the geographic bounding box for an alert geometry.

    Args:
        geometry: GeoJSON geometry dict or Shapely geometry.

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat).
    """
    geom = parse_alert_geometry(geometry)
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    return (float(min_lon), float(min_lat), float(max_lon), float(max_lat))


def is_property_inside_alert(
    geometry: Any,
    latitude: float,
    longitude: float,
) -> bool:
    """Checks whether a single property point is contained within an alert polygon.

    Args:
        geometry: GeoJSON geometry dict or Shapely geometry.
        latitude: Latitude in decimal degrees (WGS84).
        longitude: Longitude in decimal degrees (WGS84).

    Returns:
        True if the coordinate is strictly inside or on the boundary of the alert polygon.
    """
    geom = parse_alert_geometry(geometry)
    pt = Point(float(longitude), float(latitude))
    return geom.intersects(pt)


def match_properties_to_alert_polygon(
    geometry: Any,
    properties: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Performs spatial point-in-polygon matching against candidate properties.

    Uses Shapely prepared geometry for fast C-level GEOS point containment tests.

    Args:
        geometry: GeoJSON geometry dict or Shapely geometry of the weather warning.
        properties: List of property dictionaries containing 'latitude' and 'longitude'.

    Returns:
        List of properties residing inside the alert polygon.
    """
    if not properties:
        return []

    geom = parse_alert_geometry(geometry)
    prepared_poly = prep(geom)

    matched = []
    for prop in properties:
        try:
            lon = float(prop["longitude"])
            lat = float(prop["latitude"])
            pt = Point(lon, lat)
            if prepared_poly.intersects(pt):
                matched.append(prop)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping property due to invalid coordinates: {prop.get('id')}: {e}")
            continue

    return matched


# ---------------------------------------------------------------------------
# Legacy / Utility FSA helpers (retained for backward compatibility)
# ---------------------------------------------------------------------------

CITY_FSA_MAP: Dict[str, List[str]] = {
    "kingston": ["K7K", "K7L", "K7M", "K7P"],
    "calgary": ["T2P", "T2N", "T3A", "T2E"],
    "ottawa": ["K1P", "K1S", "K2A", "K1N"],
    "toronto": ["M5V", "M4B", "M2N", "M5R"],
    "edmonton": ["T5J", "T6G", "T5K", "T6E"],
}


def map_location_name_to_fsas(location_name: str) -> List[str]:
    """Legacy helper: Resolves an ECCC location name to FSAs."""
    if not location_name:
        return []
    import re
    norm = location_name.lower().strip()
    fsas = set()
    for city, city_fsas in CITY_FSA_MAP.items():
        if re.search(rf"\b{re.escape(city)}\b", norm):
            fsas.update(city_fsas)
    return sorted(list(fsas))


def map_alert_to_fsas(alert: Dict[str, Any]) -> List[str]:
    """Legacy helper: Maps an alert payload to FSAs."""
    matched = set()
    for key in ["feature_name", "feature_name_en", "location", "alert_name"]:
        val = alert.get(key)
        if isinstance(val, str):
            matched.update(map_location_name_to_fsas(val))
    return sorted(list(matched))
