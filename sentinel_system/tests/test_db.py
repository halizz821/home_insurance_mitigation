"""Unit tests for SQLite insurance portfolio database."""

import tempfile
from pathlib import Path
import pytest

from db.database import init_db, get_connection, query_properties_by_fsas


@pytest.fixture
def temp_db():
    """Provides a temporary test database initialized with seed data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    init_db(db_path, force_seed=True)
    yield db_path

    if db_path.exists():
        db_path.unlink()


def test_database_initialization_and_seeding(temp_db):
    """Verifies that schema and 50 properties are seeded."""
    conn = get_connection(temp_db)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM policyholders;")
    policyholder_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM properties;")
    property_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM policies;")
    policy_count = cursor.fetchone()[0]

    conn.close()

    assert policyholder_count == 52
    assert property_count == 52
    assert policy_count == 52


def test_query_properties_by_fsas(temp_db):
    """Verifies targeted spatial query against specific Canadian FSAs."""
    # Kingston FSAs
    kingston_fsas = ["K7L", "K7M", "K7K"]
    props = query_properties_by_fsas(kingston_fsas, db_path=temp_db)

    assert len(props) == 10
    for p in props:
        assert p["city"] == "Kingston"
        assert p["fsa"] in kingston_fsas
        assert p["policy_id"] is not None
        assert p["policyholder_id"] is not None
        assert p["latitude"] > 40.0
        assert p["longitude"] < -70.0


def test_empty_fsa_query(temp_db):
    """Verifies that querying with empty or non-matching FSAs returns an empty list."""
    assert query_properties_by_fsas([], db_path=temp_db) == []
    assert query_properties_by_fsas(["Z9Z"], db_path=temp_db) == []


def test_query_properties_by_bbox(temp_db):
    """Verifies spatial bounding box SQL query."""
    from db.database import query_properties_by_bbox

    # Bounding box around Kingston (lat ~ 44.23, lon ~ -76.48)
    props = query_properties_by_bbox(
        min_lon=-76.65,
        min_lat=44.15,
        max_lon=-76.35,
        max_lat=44.35,
        db_path=temp_db,
    )
    assert len(props) == 10
    for p in props:
        assert p["city"] == "Kingston"

    # Bounding box in empty ocean/remote area
    empty_props = query_properties_by_bbox(
        min_lon=0.0,
        min_lat=0.0,
        max_lon=1.0,
        max_lat=1.0,
        db_path=temp_db,
    )
    assert len(empty_props) == 0

