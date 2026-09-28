-- Canadian Property & Casualty (P&C) Personal Lines Schema

CREATE TABLE IF NOT EXISTS policyholders (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id TEXT PRIMARY KEY,
    policyholder_id TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    province VARCHAR(2) NOT NULL,
    postal_code VARCHAR(7) NOT NULL,
    fsa VARCHAR(3) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    dwelling_type TEXT CHECK(dwelling_type IN ('detached', 'semi_detached', 'townhouse', 'highrise_condo')),
    roof_type TEXT NOT NULL,
    roof_age_years INTEGER NOT NULL,
    basement_type TEXT NOT NULL,
    has_sump_pump BOOLEAN NOT NULL DEFAULT 0,
    has_backwater_valve BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (policyholder_id) REFERENCES policyholders(id)
);

CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    property_id TEXT NOT NULL,
    policy_number TEXT NOT NULL UNIQUE,
    effective_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    base_deductible REAL NOT NULL DEFAULT 1000.0,
    wind_hail_deductible REAL NOT NULL DEFAULT 1500.0,
    sewer_backup_endorsed BOOLEAN NOT NULL DEFAULT 1,
    overland_water_endorsed BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE INDEX IF NOT EXISTS idx_properties_fsa ON properties(fsa);
CREATE INDEX IF NOT EXISTS idx_properties_policyholder ON properties(policyholder_id);
CREATE INDEX IF NOT EXISTS idx_properties_coords ON properties(longitude, latitude);
CREATE INDEX IF NOT EXISTS idx_policies_property ON policies(property_id);

