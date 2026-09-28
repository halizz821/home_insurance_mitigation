"""Database manager and spatial query engine for insurance portfolio."""

import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Union

from .seed_data import get_seed_data

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "insurance_portfolio.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Returns a SQLite connection configured with Row factory."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Union[str, Path]] = None, force_seed: bool = False) -> None:
    """Initializes the database schema and populates seed data if empty."""
    conn = get_connection(db_path)
    with conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM properties;")
        count = cursor.fetchone()[0]

        if count == 0 or force_seed:
            if force_seed and count > 0:
                conn.execute("DELETE FROM policies;")
                conn.execute("DELETE FROM properties;")
                conn.execute("DELETE FROM policyholders;")

            policyholders, properties, policies = get_seed_data()

            conn.executemany(
                """
                INSERT OR REPLACE INTO policyholders (id, first_name, last_name, phone, email)
                VALUES (:id, :first_name, :last_name, :phone, :email);
                """,
                policyholders,
            )

            conn.executemany(
                """
                INSERT OR REPLACE INTO properties (
                    id, policyholder_id, address, city, province, postal_code, fsa,
                    latitude, longitude, dwelling_type, roof_type, roof_age_years,
                    basement_type, has_sump_pump, has_backwater_valve
                ) VALUES (
                    :id, :policyholder_id, :address, :city, :province, :postal_code, :fsa,
                    :latitude, :longitude, :dwelling_type, :roof_type, :roof_age_years,
                    :basement_type, :has_sump_pump, :has_backwater_valve
                );
                """,
                properties,
            )

            conn.executemany(
                """
                INSERT OR REPLACE INTO policies (
                    id, property_id, policy_number, effective_date, expiry_date,
                    base_deductible, wind_hail_deductible, sewer_backup_endorsed,
                    overland_water_endorsed
                ) VALUES (
                    :id, :property_id, :policy_number, :effective_date, :expiry_date,
                    :base_deductible, :wind_hail_deductible, :sewer_backup_endorsed,
                    :overland_water_endorsed
                );
                """,
                policies,
            )

    conn.close()


def query_properties_by_fsas(
    fsa_list: List[str],
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Performs spatial database query against properties residing in affected FSAs.

    Args:
        fsa_list: List of 3-character Canadian Forward Sortation Areas (e.g., ['K7L', 'K7M']).
        db_path: Optional custom database path.

    Returns:
        List of property and policy dictionaries.
    """
    if not fsa_list:
        return []

    # Clean and uppercase FSAs
    clean_fsas = [f.strip().upper() for f in fsa_list if f.strip()]
    if not clean_fsas:
        return []

    conn = get_connection(db_path)
    placeholders = ",".join("?" for _ in clean_fsas)
    query = f"""
    SELECT p.id, p.policyholder_id, p.address, p.city, p.province, p.postal_code, p.fsa,
           p.latitude, p.longitude, p.dwelling_type, p.roof_type, p.roof_age_years,
           p.basement_type, p.has_sump_pump, p.has_backwater_valve,
           pol.id AS policy_id, pol.policy_number, pol.effective_date, pol.expiry_date,
           pol.base_deductible, pol.wind_hail_deductible,
           pol.sewer_backup_endorsed, pol.overland_water_endorsed,
           ph.first_name, ph.last_name, ph.phone, ph.email
    FROM properties p
    JOIN policies pol ON p.id = pol.property_id
    JOIN policyholders ph ON p.policyholder_id = ph.id
    WHERE p.fsa IN ({placeholders})
    ORDER BY p.city, p.id;
    """

    cursor = conn.cursor()
    cursor.execute(query, clean_fsas)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def query_properties_by_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Performs spatial database query against properties residing within a geographic bounding box.

    Args:
        min_lon: Minimum longitude (western bound).
        min_lat: Minimum latitude (southern bound).
        max_lon: Maximum longitude (eastern bound).
        max_lat: Maximum latitude (northern bound).
        db_path: Optional custom database path.

    Returns:
        List of property and policy dictionaries.
    """
    conn = get_connection(db_path)
    query = """
    SELECT p.id, p.policyholder_id, p.address, p.city, p.province, p.postal_code, p.fsa,
           p.latitude, p.longitude, p.dwelling_type, p.roof_type, p.roof_age_years,
           p.basement_type, p.has_sump_pump, p.has_backwater_valve,
           pol.id AS policy_id, pol.policy_number, pol.effective_date, pol.expiry_date,
           pol.base_deductible, pol.wind_hail_deductible,
           pol.sewer_backup_endorsed, pol.overland_water_endorsed,
           ph.first_name, ph.last_name, ph.phone, ph.email
    FROM properties p
    JOIN policies pol ON p.id = pol.property_id
    JOIN policyholders ph ON p.policyholder_id = ph.id
    WHERE p.longitude >= ? AND p.longitude <= ?
      AND p.latitude >= ? AND p.latitude <= ?
    ORDER BY p.city, p.id;
    """

    cursor = conn.cursor()
    cursor.execute(query, (min_lon, max_lon, min_lat, max_lat))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

