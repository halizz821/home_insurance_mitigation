"""Seed data generator for Canadian P&C insurance portfolio."""

from typing import Any, Dict, List, Tuple


def get_seed_data() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns 50 realistic synthetic policyholders, properties, and policies.

    Covering 5 Canadian cities:
      - Kingston, ON (FSAs: K7L, K7M, K7K)
      - Ottawa, ON (FSAs: K1P, K1S, K2A)
      - Toronto, ON (FSAs: M5V, M4B, M2N)
      - Calgary, AB (FSAs: T2P, T2N, T3A)
      - Edmonton, AB (FSAs: T5J, T6G)
    """

    city_configs = [
        # Kingston, ON (10 properties)
        {
            "city": "Kingston",
            "province": "ON",
            "fsas": ["K7L", "K7M", "K7K"],
            "base_lat": 44.2312,
            "base_lon": -76.4860,
            "streets": ["Princess St", "Brock St", "King St E", "Union St", "Johnson St", "Sir John A Macdonald Blvd", "Bath Rd", "Concession St", "Division St", "Rideau St"],
            "count": 10,
        },
        # Ottawa, ON (10 properties)
        {
            "city": "Ottawa",
            "province": "ON",
            "fsas": ["K1P", "K1S", "K2A"],
            "base_lat": 45.4215,
            "base_lon": -75.6972,
            "streets": ["Wellington St", "Bank St", "Elgin St", "Richmond Rd", "Carling Ave", "Laurier Ave W", "Bronson Ave", "Preston St", "Sunnyside Ave", "Byron Ave"],
            "count": 10,
        },
        # Toronto, ON (10 properties)
        {
            "city": "Toronto",
            "province": "ON",
            "fsas": ["M5V", "M4B", "M2N"],
            "base_lat": 43.6532,
            "base_lon": -79.3832,
            "streets": ["King St W", "Front St W", "Spadina Ave", "Woodbine Ave", "O'Connor Dr", "Yonge St", "Sheppard Ave E", "Empress Ave", "Dawes Rd", "Bremner Blvd"],
            "count": 10,
        },
        # Calgary, AB (10 properties)
        {
            "city": "Calgary",
            "province": "AB",
            "fsas": ["T2P", "T2N", "T3A"],
            "base_lat": 51.0447,
            "base_lon": -114.0719,
            "streets": ["8th Ave SW", "17th Ave SW", "Crowchild Trail NW", "Kensington Rd NW", "Dalhousie Dr NW", "5th Ave SW", "10th St NW", "Varsity Dr NW", "Bow Trail SW", "Memorial Dr NW"],
            "count": 10,
        },
        # Edmonton, AB (10 properties)
        {
            "city": "Edmonton",
            "province": "AB",
            "fsas": ["T5J", "T6G"],
            "base_lat": 53.5461,
            "base_lon": -113.4938,
            "streets": ["Jasper Ave", "104th St NW", "82nd Ave NW", "Saskatchewan Dr NW", "109th St NW", "100th Ave NW", "87th Ave NW", "102nd Ave NW", "University Ave NW", "Whyte Ave"],
            "count": 10,
        },
    ]

    first_names = [
        "Liam", "Olivia", "Noah", "Emma", "Oliver", "Charlotte", "James", "Amelia", "William", "Sophia",
        "Benjamin", "Isabella", "Lucas", "Mia", "Henry", "Evelyn", "Alexander", "Harper", "Michael", "Camila",
        "Daniel", "Gianna", "Matthew", "Abigail", "Jackson", "Emily", "Sebastian", "Elizabeth", "David", "Mila",
        "Carter", "Ella", "Wyatt", "Avery", "Jayden", "Sofia", "John", "Chloe", "Owen", "Penelope",
        "Dylan", "Layla", "Luke", "Riley", "Gabriel", "Zoey", "Anthony", "Nora", "Isaac", "Lily",
    ]

    last_names = [
        "Tremblay", "Smith", "Roy", "Gagnon", "Lee", "Wilson", "Bouchard", "Johnson", "Cote", "Brown",
        "Gauthier", "Campbell", "Morin", "Martin", "Lavoie", "Anderson", "Fortin", "Taylor", "Gagné", "MacDonald",
        "Pelletier", "Thompson", "Bélanger", "White", "Lévesque", "Harris", "Simard", "Clark", "Leblanc", "Lewis",
        "Patel", "Robinson", "Boucher", "Walker", "Pétrin", "Hall", "Girard", "Young", "Poirier", "Allen",
        "Martel", "Wright", "Deschamps", "Scott", "Proulx", "Torres", "Dubois", "Nguyen", "Caron", "Baker",
    ]

    dwelling_types = ["detached", "semi_detached", "townhouse", "highrise_condo"]
    roof_types = ["asphalt_shingle", "metal", "slate", "tar_and_gravel"]
    basement_types = ["finished", "unfinished", "crawlspace", "slab_on_grade"]

    policyholders = []
    properties = []
    policies = []

    prop_idx = 1
    for config in city_configs:
        city = config["city"]
        prov = config["province"]
        fsas = config["fsas"]
        base_lat = config["base_lat"]
        base_lon = config["base_lon"]
        streets = config["streets"]

        for i in range(config["count"]):
            idx = prop_idx - 1
            fsa = fsas[i % len(fsas)]
            street_num = 100 + (i * 37) % 850
            street_name = streets[i % len(streets)]
            address = f"{street_num} {street_name}"
            # Realistic Canadian postal code format: e.g. K7L 3N6
            unit_digit = (i * 3 + 1) % 9 + 1
            alpha1 = chr(ord('A') + (i * 2) % 26)
            unit_digit2 = (i * 7 + 2) % 9 + 1
            postal_code = f"{fsa} {unit_digit}{alpha1}{unit_digit2}"

            # Coordinate jitter within ~5km
            lat = round(base_lat + ((i % 5) - 2) * 0.015 + ((i % 3) * 0.005), 4)
            lon = round(base_lon + (((i * 2) % 5) - 2) * 0.018 + ((i % 2) * 0.006), 4)

            p_id = f"HOM-{1000 + prop_idx}"
            polh_id = f"POLH-{1000 + prop_idx}"
            pol_id = f"POL-{1000 + prop_idx}"

            fname = first_names[idx]
            lname = last_names[idx]
            phone = f"+1-{613 if prov == 'ON' else 403}-555-{1000 + prop_idx}"
            email = f"{fname.lower()}.{lname.lower()}{prop_idx}@example.ca"

            policyholders.append({
                "id": polh_id,
                "first_name": fname,
                "last_name": lname,
                "phone": phone,
                "email": email,
            })

            dwelling = dwelling_types[i % len(dwelling_types)]
            roof = roof_types[i % len(roof_types)]
            roof_age = (i * 4 + 3) % 25 + 1
            basement = basement_types[i % len(basement_types)]
            has_sump = bool(i % 2 == 0)
            has_bwater = bool(i % 3 == 0)

            properties.append({
                "id": p_id,
                "policyholder_id": polh_id,
                "address": address,
                "city": city,
                "province": prov,
                "postal_code": postal_code,
                "fsa": fsa,
                "latitude": lat,
                "longitude": lon,
                "dwelling_type": dwelling,
                "roof_type": roof,
                "roof_age_years": roof_age,
                "basement_type": basement,
                "has_sump_pump": int(has_sump),
                "has_backwater_valve": int(has_bwater),
            })

            base_deductibles = [500.0, 1000.0, 1500.0, 2000.0]
            wind_deductibles = [1000.0, 1500.0, 2500.0, 5000.0]

            policies.append({
                "id": pol_id,
                "property_id": p_id,
                "policy_number": f"PNC-{prov}-{2024000 + prop_idx}",
                "effective_date": "2024-01-01",
                "expiry_date": "2025-01-01",
                "base_deductible": base_deductibles[i % len(base_deductibles)],
                "wind_hail_deductible": wind_deductibles[i % len(wind_deductibles)],
                "sewer_backup_endorsed": int(bool(i % 4 != 0)),
                "overland_water_endorsed": int(bool(i % 3 != 0)),
            })

            prop_idx += 1

    # Special Remote / Benchmark Properties
    # 1. Wood Buffalo Nat. Park near Peace Point and Lake Claire, AB
    policyholders.append({
        "id": "POLH-1051",
        "first_name": "Gordon",
        "last_name": "Cardinal",
        "phone": "+1-780-555-1051",
        "email": "gordon.cardinal@example.ca",
    })
    properties.append({
        "id": "HOM-1051",
        "policyholder_id": "POLH-1051",
        "address": "Peace Point Cabin 4, Lake Claire",
        "city": "Wood Buffalo Nat. Park near Peace Point and Lake Claire",
        "province": "AB",
        "postal_code": "T0P 1B0",
        "fsa": "T0P",
        "latitude": 58.0852,
        "longitude": -111.3846,
        "dwelling_type": "detached",
        "roof_type": "metal",
        "roof_age_years": 18,
        "basement_type": "crawlspace",
        "has_sump_pump": 0,
        "has_backwater_valve": 0,
    })
    policies.append({
        "id": "POL-1051",
        "property_id": "HOM-1051",
        "policy_number": "PNC-AB-2024051",
        "effective_date": "2024-01-01",
        "expiry_date": "2025-01-01",
        "base_deductible": 2500.0,
        "wind_hail_deductible": 2500.0,
        "sewer_backup_endorsed": 0,
        "overland_water_endorsed": 0,
    })

    # 2. Uranium City, SK
    policyholders.append({
        "id": "POLH-1052",
        "first_name": "Eileen",
        "last_name": "Auger",
        "phone": "+1-306-555-1052",
        "email": "eileen.auger@example.ca",
    })
    properties.append({
        "id": "HOM-1052",
        "policyholder_id": "POLH-1052",
        "address": "42 Hospital Rd",
        "city": "Uranium City",
        "province": "SK",
        "postal_code": "S0J 2W0",
        "fsa": "S0J",
        "latitude": 59.5684,
        "longitude": -108.6152,
        "dwelling_type": "detached",
        "roof_type": "asphalt_shingle",
        "roof_age_years": 24,
        "basement_type": "crawlspace",
        "has_sump_pump": 0,
        "has_backwater_valve": 0,
    })
    policies.append({
        "id": "POL-1052",
        "property_id": "HOM-1052",
        "policy_number": "PNC-SK-2024052",
        "effective_date": "2024-01-01",
        "expiry_date": "2025-01-01",
        "base_deductible": 1500.0,
        "wind_hail_deductible": 2500.0,
        "sewer_backup_endorsed": 1,
        "overland_water_endorsed": 0,
    })

    return policyholders, properties, policies

