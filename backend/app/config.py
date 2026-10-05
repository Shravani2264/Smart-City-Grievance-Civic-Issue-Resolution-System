"""Static civic knowledge: issue taxonomy, departments, SLA standards, and the city gazetteer.

Northbridge is a fictional municipal corporation used for the demo. Its 12 wards sit on a
4 x 3 grid; sectors 1-36 map three-per-ward, and named landmarks/roads carry coordinates.
"""

CITY = "Northbridge"
MUNICIPALITY = "Northbridge Municipal Corporation"

# Bounding box of the city (lat grows north, lng grows east)
LAT_MIN, LAT_MAX = 19.000, 19.090
LNG_MIN, LNG_MAX = 73.000, 73.120
GRID_COLS, GRID_ROWS = 4, 3

DEPARTMENTS = {
    "SAN": {"name": "Municipal Sanitation Unit", "short": "Sanitation", "supervisor": "Ward Sanitary Inspector", "officer": "Deputy Commissioner (Health)", "color": "mint"},
    "WSB": {"name": "Water Supply Board", "short": "Water Supply", "supervisor": "Junior Engineer (Water)", "officer": "Executive Engineer (Water)", "color": "blue"},
    "PWD": {"name": "Public Works Department", "short": "Public Works", "supervisor": "Assistant Engineer (Roads)", "officer": "City Engineer", "color": "orange"},
    "ELE": {"name": "Electrical Department", "short": "Electrical", "supervisor": "Lighting Supervisor", "officer": "Executive Engineer (Electrical)", "color": "yellow"},
    "PUB": {"name": "Power Utility Board", "short": "Power Utility", "supervisor": "Line Supervisor", "officer": "Divisional Engineer (Power)", "color": "yellow"},
    "SWD": {"name": "Stormwater & Sewerage", "short": "Drainage", "supervisor": "Drainage Supervisor", "officer": "Executive Engineer (Drainage)", "color": "purple"},
    "PRK": {"name": "Parks & Horticulture", "short": "Parks", "supervisor": "Garden Superintendent", "officer": "Tree Officer", "color": "mint"},
    "PHD": {"name": "Public Health Department", "short": "Public Health", "supervisor": "Health Inspector", "officer": "Medical Officer of Health", "color": "coral"},
    "TRF": {"name": "Traffic Engineering Cell", "short": "Traffic", "supervisor": "Traffic Engineer", "officer": "Deputy Commissioner (Traffic)", "color": "orange"},
    "TPD": {"name": "Town Planning & Enforcement", "short": "Enforcement", "supervisor": "Enforcement Inspector", "officer": "Assistant Commissioner (Ward)", "color": "purple"},
    "CSC": {"name": "Citizen Service Cell", "short": "Service Cell", "supervisor": "Grievance Officer", "officer": "Additional Commissioner", "color": "blue"},
}
EMERGENCY_TEAM = "Disaster Management & Emergency Response Cell"
COMMISSIONER = "Municipal Commissioner's Office"

# issue_type -> category, department, base SLA hours, base severity (0-100), keywords, label
ISSUE_TYPES = {
    "garbage_uncollected": {"label": "Garbage not collected", "category": "Solid Waste Management", "dept": "SAN", "sla": 48, "base": 45,
                            "kw": ["garbage", "trash", "waste", "rubbish", "not collected", "dustbin", "bin overflow", "kachra", "litter", "pile"]},
    "illegal_dumping": {"label": "Illegal dumping", "category": "Solid Waste Management", "dept": "SAN", "sla": 72, "base": 40,
                        "kw": ["dumping", "dumped", "debris", "construction waste", "dump site", "burning garbage", "burning waste"]},
    "water_leakage": {"label": "Water pipeline leakage", "category": "Water Supply", "dept": "WSB", "sla": 24, "base": 52,
                      "kw": ["leak", "leakage", "pipe burst", "burst pipe", "pipeline", "water wastage", "water flowing", "water leaking"]},
    "no_water_supply": {"label": "No water supply", "category": "Water Supply", "dept": "WSB", "sla": 24, "base": 58,
                        "kw": ["no water", "water supply", "low pressure", "water cut", "dry taps", "no supply", "tanker"]},
    "contaminated_water": {"label": "Contaminated water", "category": "Water Supply", "dept": "WSB", "sla": 12, "base": 72,
                           "kw": ["dirty water", "contaminated", "muddy water", "smelly water", "yellow water", "polluted water", "drinking water"]},
    "pothole": {"label": "Pothole", "category": "Roads & Infrastructure", "dept": "PWD", "sla": 72, "base": 48,
                "kw": ["pothole", "potholes", "crater", "pit on road"]},
    "road_damage": {"label": "Damaged road / footpath", "category": "Roads & Infrastructure", "dept": "PWD", "sla": 96, "base": 38,
                    "kw": ["road damaged", "broken road", "road broken", "footpath", "pavement", "speed breaker", "road cave", "cracked road", "divider"]},
    "open_manhole": {"label": "Open manhole", "category": "Roads & Infrastructure", "dept": "PWD", "sla": 6, "base": 82,
                     "kw": ["manhole", "open drain cover", "missing cover", "uncovered"]},
    "streetlight_out": {"label": "Streetlight not working", "category": "Electricity & Lighting", "dept": "ELE", "sla": 72, "base": 35,
                        "kw": ["streetlight", "street light", "lamp post", "light not working", "lights out", "dark street", "pole light"]},
    "power_outage": {"label": "Power outage", "category": "Electricity & Lighting", "dept": "PUB", "sla": 12, "base": 60,
                     "kw": ["power cut", "no electricity", "power outage", "blackout", "transformer", "electricity gone"]},
    "exposed_wire": {"label": "Exposed live wire", "category": "Electricity & Lighting", "dept": "PUB", "sla": 4, "base": 88,
                     "kw": ["live wire", "exposed wire", "hanging wire", "sparking", "electric shock", "fallen wire", "naked wire"]},
    "drain_blockage": {"label": "Blocked drain", "category": "Drainage & Sewerage", "dept": "SWD", "sla": 48, "base": 46,
                       "kw": ["drain blocked", "blocked drain", "clogged", "gutter", "nala", "choked drain", "drain"]},
    "waterlogging": {"label": "Waterlogging", "category": "Drainage & Sewerage", "dept": "SWD", "sla": 24, "base": 58,
                     "kw": ["waterlogging", "waterlogged", "flooded", "flooding", "water accumulated", "knee deep", "stagnant water on road"]},
    "sewage_overflow": {"label": "Sewage overflow", "category": "Drainage & Sewerage", "dept": "SWD", "sla": 24, "base": 64,
                        "kw": ["sewage", "sewer", "overflowing sewage", "chamber overflow", "toilet water"]},
    "fallen_tree": {"label": "Fallen / dangerous tree", "category": "Parks & Trees", "dept": "PRK", "sla": 24, "base": 62,
                    "kw": ["fallen tree", "tree fell", "tree collapsed", "branch fell", "dangerous tree", "uprooted"]},
    "park_maintenance": {"label": "Park maintenance", "category": "Parks & Trees", "dept": "PRK", "sla": 168, "base": 18,
                         "kw": ["park", "bench", "swing", "playground", "garden", "grass"]},
    "stray_animals": {"label": "Stray animal menace", "category": "Public Health", "dept": "PHD", "sla": 72, "base": 42,
                      "kw": ["stray dog", "stray dogs", "dog bite", "cattle", "stray animal", "monkey", "cows on road"]},
    "mosquito_breeding": {"label": "Mosquito breeding / fogging", "category": "Public Health", "dept": "PHD", "sla": 48, "base": 50,
                          "kw": ["mosquito", "dengue", "malaria", "fogging", "larvae"]},
    "traffic_signal": {"label": "Traffic signal fault", "category": "Traffic & Mobility", "dept": "TRF", "sla": 12, "base": 64,
                       "kw": ["signal not working", "traffic signal", "traffic light", "signal off", "blinking signal"]},
    "encroachment": {"label": "Encroachment", "category": "Encroachment & Planning", "dept": "TPD", "sla": 168, "base": 28,
                     "kw": ["encroachment", "hawkers", "illegal construction", "blocked footpath", "illegal parking", "unauthorised"]},
    "noise_pollution": {"label": "Noise pollution", "category": "Public Health", "dept": "PHD", "sla": 72, "base": 25,
                        "kw": ["noise", "loudspeaker", "loud music", "honking"]},
    "other": {"label": "General civic issue", "category": "General", "dept": "CSC", "sla": 120, "base": 25, "kw": []},
}

CATEGORY_COLORS = {
    "Solid Waste Management": "mint", "Water Supply": "blue", "Roads & Infrastructure": "orange",
    "Electricity & Lighting": "yellow", "Drainage & Sewerage": "purple", "Parks & Trees": "mint",
    "Public Health": "coral", "Traffic & Mobility": "orange", "Encroachment & Planning": "purple", "General": "blue",
}

# Urgency signal detectors: signal -> (keywords, severity boost)
URGENCY_SIGNALS = {
    "safety_risk": (["accident", "injur", "fell", "fall into", "danger", "unsafe", "risk", "shock", "electrocut", "fire", "collapse", "deep", "open manhole", "spark", "dark at night", "hazard"], 18),
    "public_health_risk": (["smell", "stink", "foul", "mosquito", "disease", "dengue", "health", "contaminat", "sick", "vomit", "rats", "flies", "sewage", "rotting", "stray animals"], 12),
    "traffic_impact": (["traffic", "jam", "vehicles", "swerve", "blocking road", "blocked road", "main road", "highway", "junction", "bus route"], 9),
    "vulnerable_groups": (["school", "children", "kids", "hospital", "elderly", "senior citizen", "pregnant", "disabled", "anganwadi"], 10),
    "wide_impact": (["entire area", "whole colony", "whole society", "many houses", "entire street", "hundreds", "all residents", "whole sector", "entire lane", "several buildings"], 8),
    "property_damage": (["damage", "seeping into", "entering homes", "inside houses", "basement", "shops flooded"], 7),
}

# Escalation chain: fraction of SLA elapsed -> level
ESCALATION_LEVELS = [
    {"level": 1, "at": 0.5, "role": "supervisor", "label": "Supervisor"},
    {"level": 2, "at": 1.0, "role": "officer", "label": "District Officer"},
    {"level": 3, "at": 1.5, "role": "commissioner", "label": "Commissioner / Emergency Team"},
]

WORKFLOW = ["Reported", "Assigned", "In Progress", "Inspection", "Resolved", "Closed"]
TERMINAL = {"Closed", "Rejected"}

# Ward metadata: population (thousands), elevation (m), drainage capacity (mm/hr it can absorb)
# Ward k sits at row (k-1)//4 (0 = north) and column (k-1)%4 (0 = west).
WARDS = {
    1: {"name": "Hillcrest", "pop": 64, "elev": 38, "drain": 45},
    2: {"name": "Old Market", "pop": 112, "elev": 22, "drain": 26},
    3: {"name": "Lakeview", "pop": 88, "elev": 11, "drain": 22},
    4: {"name": "Airport Road", "pop": 54, "elev": 30, "drain": 40},
    5: {"name": "Riverside", "pop": 96, "elev": 7, "drain": 18},
    6: {"name": "Shanti Nagar", "pop": 128, "elev": 10, "drain": 21},
    7: {"name": "Greenfield", "pop": 104, "elev": 18, "drain": 30},
    8: {"name": "Industrial Estate", "pop": 46, "elev": 16, "drain": 27},
    9: {"name": "College Town", "pop": 71, "elev": 24, "drain": 36},
    10: {"name": "MG Road", "pop": 92, "elev": 19, "drain": 31},
    11: {"name": "Station Area", "pop": 136, "elev": 13, "drain": 24},
    12: {"name": "New Township", "pop": 58, "elev": 27, "drain": 42},
}
ZONES = {0: "North Zone", 1: "Central Zone", 2: "South Zone"}


def sector_ward(n: int) -> int:
    """Sectors 1-36 map three per ward (e.g. Sector 14 -> Ward 7)."""
    return ((n + 4) % 12) + 1


# Relative performance of each department's field crews (1.0 = resolves right at SLA on average).
# Used only by the field-operations simulator that stands in for real crews in the demo.
DEPT_PACE = {"SAN": 0.85, "WSB": 0.7, "PWD": 1.15, "ELE": 0.8, "PUB": 0.6, "SWD": 1.05, "PRK": 0.9,
             "PHD": 0.95, "TRF": 0.65, "TPD": 1.25, "CSC": 0.9}
WARD_PACE = {1: 0.85, 2: 1.1, 3: 1.0, 4: 0.8, 5: 1.2, 6: 1.25, 7: 1.05, 8: 0.95, 9: 0.85, 10: 1.0, 11: 1.15, 12: 0.8}

# Gazetteer: landmark / road -> (lat, lng). Lowercased keys; matched by substring.
LANDMARKS = {
    "hanuman temple": (19.078, 73.020), "temple": (19.050, 73.048), "shiv mandir": (19.022, 73.098),
    "main road": (19.046, 73.062), "mg road": (19.018, 73.050), "lakeview road": (19.081, 73.072),
    "old market": (19.079, 73.044), "market": (19.076, 73.046), "railway station": (19.012, 73.072), "station": (19.013, 73.070),
    "bus depot": (19.048, 73.092), "city hospital": (19.052, 73.040), "hospital": (19.053, 73.041),
    "riverside promenade": (19.045, 73.012), "riverside": (19.043, 73.015), "lake": (19.083, 73.068),
    "civic centre": (19.072, 73.108), "airport road": (19.080, 73.098), "industrial estate": (19.040, 73.102),
    "shanti nagar": (19.046, 73.040), "greenfield": (19.050, 73.070), "community park": (19.049, 73.066),
    "central park": (19.074, 73.028), "school": (19.058, 73.078), "college": (19.020, 73.028),
    "highway": (19.030, 73.090), "flyover": (19.028, 73.060), "new township": (19.015, 73.105),
    "hillcrest": (19.081, 73.012), "mall": (19.016, 73.058), "stadium": (19.024, 73.084), "church": (19.062, 73.030),
    "mosque": (19.036, 73.052), "gurudwara": (19.068, 73.088), "police station": (19.044, 73.074),
}
