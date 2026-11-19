"""
Generate synthetic WeatherWise demo data (deterministic, seed=42).

Writes into this folder:
  sites.csv             supply + distribution centers (with lat/lon)
  facilities.csv        hospitals + clinics (with lat/lon and serving site)
  inventory.csv         on-hand stock per site/product (same columns as before)
  shipments.csv         original columns first, then new delay / geo / patient-impact columns
  weather_forecast.csv  synthetic forecast per destination city for DEMO_DATE + 1

NOT touched (kept as the source of truth for products + SOPs):
  suppliers.csv, supplier_sops.csv

Run:  python3 data/generate_synthetic_data.py
"""

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent
rng = random.Random(42)

DEMO_DATE = date(2026, 11, 18)          # "today" for the demo
TOMORROW = DEMO_DATE + timedelta(days=1)

# SOP storage spec for every product: 2–8 °C (≈36–46 °F)
SOP_MIN_F, SOP_MAX_F = 36.0, 46.0

# --------------------------------------------------------------------------
# Products: must match supplier_sops.csv exactly (product_id, sku, name, supplier)
# origin = supplier's manufacturing / ship-from city
# --------------------------------------------------------------------------
PRODUCTS = [
    ("PROD-0001", "IMPL-A21", "Hip Implant Set", "SUP-001", ("Memphis", "TN", 35.1495, -90.0490)),
    ("PROD-0002", "STENT-C13", "Cardio Stent Kit", "SUP-002", ("Chicago", "IL", 41.8781, -87.6298)),
    ("PROD-0003", "CATH-B08", "Balloon Catheter", "SUP-003", ("Dallas", "TX", 32.7767, -96.7970)),
    ("PROD-0004", "PATCH-D02", "Hernia Patch", "SUP-004", ("Phoenix", "AZ", 33.4484, -112.0740)),
    ("PROD-0005", "VALVE-E11", "Aortic Valve", "SUP-005", ("Seattle", "WA", 47.6062, -122.3321)),
    ("PROD-0006", "IMPL-A21", "Hip Implant Set", "SUP-009", ("Cleveland", "OH", 41.4993, -81.6944)),
    ("PROD-0007", "STENT-C13", "Cardio Stent Kit", "SUP-010", ("Miami", "FL", 25.7617, -80.1918)),
    ("PROD-0008", "VALVE-E11", "Aortic Valve", "SUP-005", ("San Jose", "CA", 37.3382, -121.8863)),
    ("PROD-0009", "CATH-B08", "Balloon Catheter", "SUP-003", ("Denver", "CO", 39.7392, -104.9903)),
    ("PROD-0010", "IMPL-A21", "Hip Implant Set", "SUP-001", ("Memphis", "TN", 35.1495, -90.0490)),
]

# --------------------------------------------------------------------------
# Sites: SITE-201..210 keep their original names/cities; 211+ are new.
# --------------------------------------------------------------------------
SITES = [
    # id, name, type, city, state, lat, lon
    ("SITE-201", "New Jersey Hub", "Supply Center", "Newark", "NJ", 40.7357, -74.1724),
    ("SITE-202", "Upstate NY DC", "Distribution Center", "Albany", "NY", 42.6526, -73.7562),
    ("SITE-203", "Boston MedCenter Warehouse", "Distribution Center", "Boston", "MA", 42.3601, -71.0589),
    ("SITE-204", "Denver Surgical Depot", "Distribution Center", "Denver", "CO", 39.7392, -104.9903),
    ("SITE-205", "San Diego Clinical DC", "Distribution Center", "San Diego", "CA", 32.7157, -117.1611),
    ("SITE-206", "Miami Med DC", "Distribution Center", "Miami", "FL", 25.7617, -80.1918),
    ("SITE-207", "Seattle Ortho Hub", "Distribution Center", "Seattle", "WA", 47.6062, -122.3321),
    ("SITE-208", "Philadelphia ColdSite", "Supply Center", "Philadelphia", "PA", 39.9526, -75.1652),
    ("SITE-209", "Austin Surgical Supply", "Distribution Center", "Austin", "TX", 30.2672, -97.7431),
    ("SITE-210", "Cleveland Care DC", "Distribution Center", "Cleveland", "OH", 41.4993, -81.6944),
    ("SITE-211", "Bronx Cold Chain Center", "Supply Center", "Bronx", "NY", 40.8048, -73.8810),
    ("SITE-212", "JFK Air Cargo Hub", "Supply Center", "Queens", "NY", 40.6620, -73.7900),
    ("SITE-213", "Long Island Distribution", "Distribution Center", "Hauppauge", "NY", 40.8257, -73.2026),
    ("SITE-214", "Brooklyn Navy Yard Depot", "Distribution Center", "Brooklyn", "NY", 40.7003, -73.9708),
    ("SITE-215", "Stamford Regional DC", "Distribution Center", "Stamford", "CT", 41.0534, -73.5387),
    ("SITE-216", "Edison Pharma Logistics", "Supply Center", "Edison", "NJ", 40.5187, -74.4121),
    ("SITE-217", "Hartford Medical DC", "Distribution Center", "Hartford", "CT", 41.7658, -72.6734),
    ("SITE-218", "Baltimore Cold Hub", "Distribution Center", "Baltimore", "MD", 39.2904, -76.6122),
    ("SITE-219", "Capital Surgical Supply", "Distribution Center", "Washington", "DC", 38.9072, -77.0369),
    ("SITE-220", "Pittsburgh Med DC", "Distribution Center", "Pittsburgh", "PA", 40.4406, -79.9959),
    ("SITE-221", "Chicago Midwest Hub", "Supply Center", "Chicago", "IL", 41.8781, -87.6298),
    ("SITE-222", "Atlanta Southeast DC", "Supply Center", "Atlanta", "GA", 33.7490, -84.3880),
    ("SITE-223", "Memphis Air Gateway", "Supply Center", "Memphis", "TN", 35.0424, -89.9767),
    ("SITE-224", "Dallas Central DC", "Supply Center", "Dallas", "TX", 32.7767, -96.7970),
    ("SITE-225", "Los Angeles West DC", "Supply Center", "Los Angeles", "CA", 34.0522, -118.2437),
]

# --------------------------------------------------------------------------
# Facilities (hospitals + clinics). Synthetic names, approximate real coords.
# "metro" is the destination string used in shipments (NYC boroughs -> "New York, NY"
# so the agent's get_shipments('NYC') still matches).
# --------------------------------------------------------------------------
NYC = ("New York", "NY")
FACILITY_SEEDS = [
    # name, type, city, state, metro(city,state), lat, lon
    ("Midtown Surgical Hospital", "Hospital", "Manhattan", "NY", NYC, 40.7549, -73.9840),
    ("Upper East Side Heart Institute", "Hospital", "Manhattan", "NY", NYC, 40.7736, -73.9566),
    ("Harlem Community Medical Center", "Hospital", "Manhattan", "NY", NYC, 40.8116, -73.9465),
    ("Chelsea Orthopedic Clinic", "Clinic", "Manhattan", "NY", NYC, 40.7465, -74.0014),
    ("Lower Manhattan General Hospital", "Hospital", "Manhattan", "NY", NYC, 40.7100, -74.0050),
    ("Washington Heights Medical Center", "Hospital", "Manhattan", "NY", NYC, 40.8417, -73.9394),
    ("Murray Hill Cardiology Clinic", "Clinic", "Manhattan", "NY", NYC, 40.7479, -73.9757),
    ("Park Slope Outpatient Surgery", "Clinic", "Brooklyn", "NY", NYC, 40.6710, -73.9814),
    ("Downtown Brooklyn Medical Center", "Hospital", "Brooklyn", "NY", NYC, 40.6928, -73.9903),
    ("Bay Ridge Joint & Spine Clinic", "Clinic", "Brooklyn", "NY", NYC, 40.6264, -74.0299),
    ("Flatbush General Hospital", "Hospital", "Brooklyn", "NY", NYC, 40.6409, -73.9590),
    ("Williamsburg Vascular Clinic", "Clinic", "Brooklyn", "NY", NYC, 40.7081, -73.9571),
    ("Flushing Regional Hospital", "Hospital", "Queens", "NY", NYC, 40.7580, -73.8303),
    ("Astoria Surgical Clinic", "Clinic", "Queens", "NY", NYC, 40.7644, -73.9235),
    ("Jamaica Medical Center", "Hospital", "Queens", "NY", NYC, 40.7027, -73.7890),
    ("Forest Hills Cardiology Clinic", "Clinic", "Queens", "NY", NYC, 40.7181, -73.8448),
    ("Fordham Medical Center", "Hospital", "Bronx", "NY", NYC, 40.8610, -73.8900),
    ("Riverdale Orthopedic Clinic", "Clinic", "Bronx", "NY", NYC, 40.8900, -73.9120),
    ("South Bronx Community Hospital", "Hospital", "Bronx", "NY", NYC, 40.8160, -73.9170),
    ("Staten Island University Medical", "Hospital", "Staten Island", "NY", NYC, 40.5840, -74.0870),
    ("Hoboken Waterfront Clinic", "Clinic", "Hoboken", "NJ", ("Hoboken", "NJ"), 40.7440, -74.0324),
    ("Jersey City Medical Pavilion", "Hospital", "Jersey City", "NJ", ("Jersey City", "NJ"), 40.7178, -74.0431),
    ("Hackensack Valley Hospital", "Hospital", "Hackensack", "NJ", ("Hackensack", "NJ"), 40.8859, -74.0435),
    ("Newark Heart & Vascular", "Hospital", "Newark", "NJ", ("Newark", "NJ"), 40.7400, -74.1900),
    ("White Plains Surgical Center", "Clinic", "White Plains", "NY", ("White Plains", "NY"), 41.0340, -73.7629),
    ("Yonkers General Hospital", "Hospital", "Yonkers", "NY", ("Yonkers", "NY"), 40.9312, -73.8988),
    ("Mineola Orthopedic Institute", "Hospital", "Mineola", "NY", ("Mineola", "NY"), 40.7490, -73.6407),
    ("Garden City Ambulatory Surgery", "Clinic", "Garden City", "NY", ("Garden City", "NY"), 40.7268, -73.6343),
    ("Stamford Coastal Hospital", "Hospital", "Stamford", "CT", ("Stamford", "CT"), 41.0600, -73.5400),
    ("New Haven Cardiac Clinic", "Clinic", "New Haven", "CT", ("New Haven", "CT"), 41.3083, -72.9279),
    ("Back Bay Medical Center", "Hospital", "Boston", "MA", ("Boston", "MA"), 42.3503, -71.0810),
    ("Cambridge Surgical Clinic", "Clinic", "Cambridge", "MA", ("Cambridge", "MA"), 42.3736, -71.1097),
    ("Providence Harbor Hospital", "Hospital", "Providence", "RI", ("Providence", "RI"), 41.8240, -71.4128),
    ("Albany Capital Region Medical", "Hospital", "Albany", "NY", ("Albany", "NY"), 42.6600, -73.7800),
    ("Center City Heart Hospital", "Hospital", "Philadelphia", "PA", ("Philadelphia", "PA"), 39.9500, -75.1600),
    ("Main Line Orthopedic Clinic", "Clinic", "Bryn Mawr", "PA", ("Bryn Mawr", "PA"), 40.0218, -75.3163),
    ("Inner Harbor Medical Center", "Hospital", "Baltimore", "MD", ("Baltimore", "MD"), 39.2850, -76.6100),
    ("Capitol Hill Surgical Hospital", "Hospital", "Washington", "DC", ("Washington", "DC"), 38.8899, -76.9900),
    ("Three Rivers Medical Center", "Hospital", "Pittsburgh", "PA", ("Pittsburgh", "PA"), 40.4430, -79.9600),
    ("Lakeshore Cardiac Institute", "Hospital", "Cleveland", "OH", ("Cleveland", "OH"), 41.5030, -81.6210),
    ("Loop Surgical Clinic", "Clinic", "Chicago", "IL", ("Chicago", "IL"), 41.8800, -87.6300),
    ("North Shore Medical Center", "Hospital", "Evanston", "IL", ("Evanston", "IL"), 42.0451, -87.6877),
    ("Peachtree Heart Hospital", "Hospital", "Atlanta", "GA", ("Atlanta", "GA"), 33.7880, -84.3850),
    ("Buckhead Orthopedic Clinic", "Clinic", "Atlanta", "GA", ("Atlanta", "GA"), 33.8400, -84.3800),
    ("Biscayne Bay Medical Center", "Hospital", "Miami", "FL", ("Miami", "FL"), 25.7900, -80.1900),
    ("Coral Gables Surgical Clinic", "Clinic", "Coral Gables", "FL", ("Coral Gables", "FL"), 25.7215, -80.2684),
    ("Mile High Medical Center", "Hospital", "Denver", "CO", ("Denver", "CO"), 39.7300, -104.9700),
    ("Boulder Joint Clinic", "Clinic", "Boulder", "CO", ("Boulder", "CO"), 40.0150, -105.2705),
    ("Lone Star Heart Hospital", "Hospital", "Austin", "TX", ("Austin", "TX"), 30.2800, -97.7300),
    ("Uptown Dallas Surgical Clinic", "Clinic", "Dallas", "TX", ("Dallas", "TX"), 32.8000, -96.8000),
    ("Puget Sound Medical Center", "Hospital", "Seattle", "WA", ("Seattle", "WA"), 47.6100, -122.3200),
    ("Rose City Cardiac Clinic", "Clinic", "Portland", "OR", ("Portland", "OR"), 45.5152, -122.6784),
    ("Treasure Valley Hospital", "Hospital", "Boise", "ID", ("Boise", "ID"), 43.6150, -116.2023),
    ("La Jolla Surgical Hospital", "Hospital", "San Diego", "CA", ("San Diego", "CA"), 32.8801, -117.2340),
    ("Westside LA Orthopedic Clinic", "Clinic", "Los Angeles", "CA", ("Los Angeles", "CA"), 34.0600, -118.4400),
    ("Bay Area Heart Institute", "Hospital", "San Francisco", "CA", ("San Francisco", "CA"), 37.7630, -122.4580),
    ("Desert Valley Medical Center", "Hospital", "Phoenix", "AZ", ("Phoenix", "AZ"), 33.4800, -112.0700),
    ("Music City Surgical Clinic", "Clinic", "Nashville", "TN", ("Nashville", "TN"), 36.1627, -86.7816),
    ("Charlotte Regional Heart", "Hospital", "Charlotte", "NC", ("Charlotte", "NC"), 35.2271, -80.8431),
    ("Twin Cities Medical Center", "Hospital", "Minneapolis", "MN", ("Minneapolis", "MN"), 44.9778, -93.2650),
]

CARRIERS = ["UPS Health", "FedEx Cold", "DHL Medical Express", "Marken", "Cryoport"]

# Destination-metro synthetic forecast for TOMORROW (NYC values given by the user).
FORECAST = {
    ("New York", "NY"): (62, 44, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Bronx", "NY"): (62, 44, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Queens", "NY"): (62, 44, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Brooklyn", "NY"): (62, 44, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Hauppauge", "NY"): (60, 43, "Mostly sunny", ""),
    ("Edison", "NJ"): (63, 44, "Partly cloudy", ""),
    ("Hartford", "CT"): (56, 38, "Mostly sunny", ""),
    ("Memphis", "TN"): (66, 50, "Cloudy", ""),
    ("Newark", "NJ"): (63, 45, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Jersey City", "NJ"): (62, 45, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Hoboken", "NJ"): (62, 45, "Partly cloudy, unseasonably warm", "Warm-temperature advisory for cold chain"),
    ("Hackensack", "NJ"): (61, 42, "Partly cloudy", ""),
    ("Yonkers", "NY"): (61, 42, "Partly cloudy", ""),
    ("White Plains", "NY"): (60, 41, "Partly cloudy", ""),
    ("Mineola", "NY"): (60, 45, "Mostly sunny", ""),
    ("Garden City", "NY"): (60, 45, "Mostly sunny", ""),
    ("Stamford", "CT"): (59, 41, "Mostly sunny", ""),
    ("New Haven", "CT"): (57, 40, "Mostly sunny", ""),
    ("Boston", "MA"): (55, 40, "Breezy, clear", ""),
    ("Cambridge", "MA"): (55, 39, "Breezy, clear", ""),
    ("Providence", "RI"): (56, 39, "Clear", ""),
    ("Albany", "NY"): (50, 33, "Cloudy, rain late", ""),
    ("Philadelphia", "PA"): (64, 47, "Mild, light wind", "Warm-temperature advisory for cold chain"),
    ("Bryn Mawr", "PA"): (63, 45, "Mild", ""),
    ("Baltimore", "MD"): (66, 48, "Mild, humid", "Warm-temperature advisory for cold chain"),
    ("Washington", "DC"): (67, 49, "Mild, humid", "Warm-temperature advisory for cold chain"),
    ("Pittsburgh", "PA"): (45, 34, "Rain showers", ""),
    ("Cleveland", "OH"): (33, 27, "Lake-effect snow, 6-10 in", "Winter storm warning"),
    ("Chicago", "IL"): (34, 25, "Snow showers, gusty", "Winter weather advisory"),
    ("Evanston", "IL"): (33, 24, "Snow showers, gusty", "Winter weather advisory"),
    ("Minneapolis", "MN"): (24, 11, "Snow, blowing snow", "Winter storm warning"),
    ("Denver", "CO"): (28, 12, "Heavy snow, I-70 closures", "Winter storm warning"),
    ("Boulder", "CO"): (26, 10, "Heavy snow", "Winter storm warning"),
    ("Atlanta", "GA"): (70, 52, "Sunny", ""),
    ("Charlotte", "NC"): (68, 48, "Sunny", ""),
    ("Nashville", "TN"): (63, 44, "Thunderstorms", "Severe thunderstorm watch"),
    ("Miami", "FL"): (82, 72, "Humid, scattered storms", ""),
    ("Coral Gables", "FL"): (82, 71, "Humid, scattered storms", ""),
    ("Austin", "TX"): (78, 58, "Sunny", ""),
    ("Dallas", "TX"): (74, 55, "Windy", ""),
    ("Phoenix", "AZ"): (80, 56, "Sunny", ""),
    ("Seattle", "WA"): (49, 42, "Atmospheric river, heavy rain", "Flood watch"),
    ("Portland", "OR"): (51, 43, "Heavy rain", "Flood watch"),
    ("Boise", "ID"): (40, 28, "Cloudy", ""),
    ("San Diego", "CA"): (68, 55, "Sunny", ""),
    ("Los Angeles", "CA"): (72, 56, "Sunny", ""),
    ("San Francisco", "CA"): (60, 50, "Fog, then sun", ""),
}

# Delay reasons, picked based on where the shipment is going / coming from.
WEATHER_DELAYS_BY_ORIGIN = {
    "Chicago": "Lake-effect snow - linehaul held at Chicago hub",
    "Cleveland": "Lake-effect snow - I-90 closure near Cleveland",
    "Denver": "Winter storm - I-70 closures out of Denver",
    "Seattle": "Atmospheric river - SEA cargo ground stop",
    "San Jose": "Connecting flight cancelled via SEA (heavy rain)",
}
NYC_AREA_DELAYS = [
    "JFK cargo backlog - pallet held on warm dock",
    "Reefer unit fault on final-mile truck",
    "Missed linehaul connection at Newark hub",
    "Dock congestion at Bronx cold chain center",
    "Warm-dock hold - temperature excursion review",
    "Driver hours-of-service limit - handoff delayed",
]
GENERIC_DELAYS = [
    "Carrier capacity shortage",
    "Missed connection at Memphis air gateway",
    "Documentation hold - lot certificate missing",
    "Address correction at receiving dock",
    "Thunderstorms - ATL ground delay",
]


def haversine_mi(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_site(lat, lon):
    return min(SITES, key=lambda s: haversine_mi(lat, lon, s[5], s[6]))


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name:22s} {len(rows):4d} rows")


def main():
    print(f"Generating synthetic data (demo date {DEMO_DATE}, forecast for {TOMORROW})")

    # ---- sites ----------------------------------------------------------
    write_csv(
        "sites.csv",
        ["site_id", "site_name", "site_type", "city", "state", "latitude", "longitude"],
        SITES,
    )

    # ---- facilities -----------------------------------------------------
    facilities = []
    for i, (name, ftype, city, state, metro, lat, lon) in enumerate(FACILITY_SEEDS, start=1):
        site = nearest_site(lat, lon)
        beds = rng.randint(180, 1100) if ftype == "Hospital" else 0
        or_rooms = rng.randint(12, 48) if ftype == "Hospital" else rng.randint(2, 8)
        facilities.append({
            "facility_id": f"FAC-{i:03d}",
            "facility_name": name,
            "facility_type": ftype,
            "city": city,
            "state": state,
            "metro": f"{metro[0]}, {metro[1]}",
            "latitude": lat,
            "longitude": lon,
            "serving_site_id": site[0],
            "beds": beds,
            "operating_rooms": or_rooms,
        })
    write_csv("facilities.csv", list(facilities[0].keys()), [list(f.values()) for f in facilities])

    # ---- inventory (same columns as the original file) -------------------
    inventory = []
    nyc_sites = {"SITE-201", "SITE-211", "SITE-212", "SITE-213", "SITE-214", "SITE-216"}
    for site in SITES:
        n = rng.randint(4, 7) if site[0] in nyc_sites else rng.randint(3, 5)
        for prod in rng.sample(PRODUCTS, n):
            pid, sku, pname, sup, _ = prod
            qty = rng.randint(2, 60)
            # Aortic valves are scarce around NYC -> makes backup sourcing interesting
            if sku == "VALVE-E11" and site[0] in nyc_sites:
                qty = rng.randint(0, 4)
            # A few lots expire within ~2 weeks of the demo date
            days = rng.randint(6, 16) if rng.random() < 0.12 else rng.randint(30, 300)
            inventory.append([site[0], site[1], site[3], site[4], pid, sku, pname, sup, qty,
                              (DEMO_DATE + timedelta(days=days)).isoformat()])
    write_csv(
        "inventory.csv",
        ["site_id", "site_name", "city", "state", "product_id", "sku", "product_name",
         "supplier_id", "on_hand_qty", "lot_expiry"],
        inventory,
    )

    # ---- shipments --------------------------------------------------------
    nyc_area = [f for f in facilities if f["serving_site_id"] in nyc_sites or f["metro"] == "New York, NY"]
    other = [f for f in facilities if f not in nyc_area]

    shipments = []
    for n in range(150):
        fac = rng.choice(nyc_area) if rng.random() < 0.55 else rng.choice(other)
        pid, sku, pname, sup, (ocity, ostate, olat, olon) = rng.choice(PRODUCTS)
        site = next(s for s in SITES if s[0] == fac["serving_site_id"])
        miles = haversine_mi(olat, olon, fac["latitude"], fac["longitude"])
        transit_days = 1 if miles < 300 else (2 if miles < 1200 else 3)

        roll = rng.random()
        weather_origin = ocity in WEATHER_DELAYS_BY_ORIGIN
        # Delays are more likely out of storm-hit origins and into the NYC area
        p_delay = 0.12 + (0.14 if weather_origin else 0) + (0.06 if fac in nyc_area else 0)
        if roll < 0.18:
            status = "Delivered"
        elif roll < 0.18 + p_delay:
            status = "Delayed"
        elif roll < 0.18 + p_delay + 0.07:
            status = "Label-Create"
        elif roll < 0.18 + p_delay + 0.14:
            status = "Out-for-Delivery"
        else:
            status = "In-Transit"

        if status == "Delivered":
            orig_eta = DEMO_DATE - timedelta(days=rng.randint(0, 3))
        elif status == "Out-for-Delivery":
            orig_eta = DEMO_DATE
        elif status == "Label-Create":
            orig_eta = DEMO_DATE + timedelta(days=rng.randint(transit_days + 1, transit_days + 3))
        else:
            orig_eta = DEMO_DATE + timedelta(days=rng.randint(0, 3))
        ship_date = orig_eta - timedelta(days=transit_days) if status != "Label-Create" else DEMO_DATE

        delay_hours, delay_reason = 0, ""
        if status == "Delayed":
            if weather_origin and rng.random() < 0.7:
                delay_reason = WEATHER_DELAYS_BY_ORIGIN[ocity]
                delay_hours = rng.choice([18, 24, 30, 36, 48])
            elif fac in nyc_area:
                delay_reason = rng.choice(NYC_AREA_DELAYS)
                delay_hours = rng.choice([4, 6, 8, 12, 18, 24])
            else:
                delay_reason = rng.choice(GENERIC_DELAYS)
                delay_hours = rng.choice([6, 12, 18, 24])
        eta = orig_eta + timedelta(hours=delay_hours)  # date part only

        # Patient impact: scheduled procedure date and priority
        priority = rng.choices(["STAT", "Urgent", "Routine"], weights=[0.2, 0.35, 0.45])[0]
        proc_offset = {"STAT": rng.randint(0, 1), "Urgent": rng.randint(1, 2), "Routine": rng.randint(2, 6)}[priority]
        procedure_date = orig_eta + timedelta(days=proc_offset)

        # Last sensor reading: in spec normally; warm docks in the NYC heat drift above 46 °F
        temp = round(rng.uniform(37.5, 44.5), 1)
        if status == "Delayed" and fac in nyc_area and ("warm" in delay_reason.lower() or "reefer" in delay_reason.lower() or "dock" in delay_reason.lower()):
            temp = round(rng.uniform(45.5, 50.5), 1)
        elif status in ("Delayed", "In-Transit") and fac in nyc_area and rng.random() < 0.15:
            temp = round(rng.uniform(44.5, 46.5), 1)
        if status == "Delivered":
            temp = round(rng.uniform(37.0, 43.0), 1)

        dest = fac["metro"]
        shipments.append([
            # --- original columns (unchanged names/order) ---
            f"SHP-{30001 + n}", pid, sku, pname, sup, f"{ocity}, {ostate}", dest,
            ship_date.isoformat(), eta.isoformat(), rng.choice(CARRIERS), status,
            SOP_MAX_F, SOP_MIN_F,
            # --- new columns ---
            orig_eta.isoformat(), delay_hours, delay_reason, priority, procedure_date.isoformat(),
            temp, fac["facility_id"], fac["facility_name"], fac["facility_type"], site[0],
            olat, olon, fac["latitude"], fac["longitude"], round(miles),
        ])

    # Guarantee a handful of headline NYC stories for tomorrow's demo
    headline = [
        ("FAC-002", "PROD-0005", "JFK cargo backlog - pallet held on warm dock", 18, 48.7),  # aortic valve, heart institute
        ("FAC-001", "PROD-0001", "Reefer unit fault on final-mile truck", 12, 49.2),        # hip implant
        ("FAC-013", "PROD-0002", "Lake-effect snow - linehaul held at Chicago hub", 30, 43.9),
        ("FAC-009", "PROD-0008", "Connecting flight cancelled via SEA (heavy rain)", 24, 44.8),
    ]
    for i, (fid, pid, reason, hrs, temp) in enumerate(headline):
        fac = next(f for f in facilities if f["facility_id"] == fid)
        prod = next(p for p in PRODUCTS if p[0] == pid)
        ocity, ostate, olat, olon = prod[4]
        miles = haversine_mi(olat, olon, fac["latitude"], fac["longitude"])
        orig_eta = TOMORROW
        eta = orig_eta + timedelta(hours=hrs)
        row = shipments[i]
        row[:] = [
            row[0], prod[0], prod[1], prod[2], prod[3], f"{ocity}, {ostate}", fac["metro"],
            (orig_eta - timedelta(days=2)).isoformat(), eta.isoformat(), "FedEx Cold", "Delayed",
            SOP_MAX_F, SOP_MIN_F,
            orig_eta.isoformat(), hrs, reason, "STAT", TOMORROW.isoformat(),
            temp, fac["facility_id"], fac["facility_name"], fac["facility_type"], fac["serving_site_id"],
            olat, olon, fac["latitude"], fac["longitude"], round(miles),
        ]

    write_csv(
        "shipments.csv",
        ["shipment_id", "product_id", "sku", "product_name", "supplier_id", "origin", "destination",
         "ship_date", "eta_date", "carrier", "status", "temperature_max_f", "temperature_min_f",
         "original_eta_date", "delay_hours", "delay_reason", "priority", "procedure_date",
         "last_recorded_temp_f", "destination_facility_id", "destination_facility_name",
         "destination_facility_type", "routed_via_site_id",
         "origin_latitude", "origin_longitude", "destination_latitude", "destination_longitude",
         "route_miles"],
        shipments,
    )

    # ---- weather forecast ----------------------------------------------
    metros = sorted({f["metro"] for f in facilities} | {f"{s[3]}, {s[4]}" for s in SITES})
    rows = []
    for m in metros:
        city, state = m.split(", ")
        if (city, state) not in FORECAST:
            continue
        hi, lo, cond, alert = FORECAST[(city, state)]
        rows.append([city, state, TOMORROW.isoformat(), hi, lo, cond, alert,
                     max(0, hi - int(SOP_MAX_F))])
    write_csv(
        "weather_forecast.csv",
        ["city", "state", "forecast_date", "high_f", "low_f", "conditions", "weather_alert",
         "degrees_above_cold_chain_max"],
        rows,
    )


if __name__ == "__main__":
    main()
