"""Static civic knowledge: issue taxonomy, departments, SLA standards, and the Mumbai gazetteer.

Mumbai (BMC / MCGM) has 24 administrative wards labelled A through T.  Population, elevation and
drainage-capacity figures are **synthetic approximations** for demo purposes – not official data.
The landmark gazetteer uses real coordinates.
"""

CITY = "Mumbai"
MUNICIPALITY = "Brihanmumbai Municipal Corporation (BMC)"

# Bounding box (Greater Mumbai: from Colaba to Dahisar / Mulund)
LAT_MIN, LAT_MAX = 18.890, 19.270
LNG_MIN, LNG_MAX = 72.770, 72.980

# --- Ward layout for the SVG choropleth map ---
# Mumbai is a narrow north–south peninsula; the grid approximates that shape.
# Each ward has an explicit (row, col) position in a 6-row × 4-column layout.
GRID_COLS, GRID_ROWS = 4, 6

# Ward key → metadata.  Keys are integers 1-24 (DB column), but the "code" field carries BMC's letter code.
WARDS = {
    # -- South Mumbai (row 5 = bottom of map = south tip) --
    1:  {"code": "A",   "name": "Colaba / Fort",          "pop": 180, "elev": 5,  "drain": 20, "row": 5, "col": 0, "center": (18.925, 72.835)},
    2:  {"code": "B",   "name": "Dongri / Sandhurst Rd",  "pop": 130, "elev": 7,  "drain": 18, "row": 5, "col": 1, "center": (18.950, 72.840)},
    3:  {"code": "C",   "name": "Market / Bhuleshwar",    "pop": 160, "elev": 8,  "drain": 19, "row": 5, "col": 2, "center": (18.955, 72.830)},
    4:  {"code": "D",   "name": "Malabar Hill / Grant Rd", "pop": 100, "elev": 45, "drain": 38, "row": 5, "col": 3, "center": (18.965, 72.810)},
    # -- Island City central (row 4) --
    5:  {"code": "E",   "name": "Byculla",                "pop": 140, "elev": 10, "drain": 22, "row": 4, "col": 0, "center": (18.975, 72.835)},
    6:  {"code": "F/N", "name": "Matunga / Sion",         "pop": 200, "elev": 9,  "drain": 24, "row": 4, "col": 2, "center": (19.020, 72.855)},
    7:  {"code": "F/S", "name": "Parel / Sewri",          "pop": 190, "elev": 8,  "drain": 21, "row": 4, "col": 1, "center": (19.000, 72.840)},
    8:  {"code": "G/N", "name": "Dadar / Dharavi",        "pop": 350, "elev": 6,  "drain": 16, "row": 4, "col": 3, "center": (19.020, 72.850)},
    # -- Central / near suburbs (row 3) --
    9:  {"code": "G/S", "name": "Worli / Prabhadevi",     "pop": 180, "elev": 7,  "drain": 22, "row": 3, "col": 0, "center": (19.000, 72.820)},
    10: {"code": "H/E", "name": "Bandra East / Santacruz E", "pop": 240, "elev": 8,  "drain": 20, "row": 3, "col": 3, "center": (19.060, 72.855)},
    11: {"code": "H/W", "name": "Bandra West / Khar",     "pop": 160, "elev": 10, "drain": 26, "row": 3, "col": 1, "center": (19.060, 72.835)},
    16: {"code": "L",   "name": "Kurla",                  "pop": 310, "elev": 5,  "drain": 15, "row": 3, "col": 2, "center": (19.075, 72.880)},
    # -- Western + Eastern Suburbs (row 2) --
    12: {"code": "K/E", "name": "Andheri East / Jogeshwari E", "pop": 280, "elev": 9, "drain": 22, "row": 2, "col": 3, "center": (19.110, 72.865)},
    13: {"code": "K/W", "name": "Andheri West / Jogeshwari W", "pop": 220, "elev": 12, "drain": 28, "row": 2, "col": 0, "center": (19.120, 72.840)},
    17: {"code": "M/E", "name": "Chembur / Govandi",      "pop": 220, "elev": 4,  "drain": 14, "row": 2, "col": 2, "center": (19.050, 72.890)},
    18: {"code": "M/W", "name": "Mankhurd / Deonar",      "pop": 180, "elev": 3,  "drain": 12, "row": 2, "col": 1, "center": (19.040, 72.910)},
    # -- Mid suburbs (row 1) --
    14: {"code": "P/N", "name": "Malad",                  "pop": 260, "elev": 14, "drain": 26, "row": 1, "col": 0, "center": (19.180, 72.845)},
    15: {"code": "P/S", "name": "Goregaon",               "pop": 230, "elev": 11, "drain": 24, "row": 1, "col": 1, "center": (19.155, 72.855)},
    19: {"code": "N",   "name": "Ghatkopar",              "pop": 250, "elev": 7,  "drain": 20, "row": 1, "col": 2, "center": (19.085, 72.910)},
    20: {"code": "S",   "name": "Bhandup / Vikhroli",     "pop": 270, "elev": 6,  "drain": 18, "row": 1, "col": 3, "center": (19.145, 72.920)},
    # -- Northern suburbs (row 0 = top of map = north) --
    22: {"code": "R/C", "name": "Borivali",               "pop": 280, "elev": 15, "drain": 30, "row": 0, "col": 0, "center": (19.220, 72.855)},
    23: {"code": "R/N", "name": "Dahisar",                "pop": 200, "elev": 18, "drain": 32, "row": 0, "col": 1, "center": (19.255, 72.860)},
    24: {"code": "R/S", "name": "Kandivali",              "pop": 250, "elev": 13, "drain": 27, "row": 0, "col": 2, "center": (19.205, 72.860)},
    21: {"code": "T",   "name": "Mulund",                 "pop": 200, "elev": 12, "drain": 28, "row": 0, "col": 3, "center": (19.175, 72.940)},
}

# Zone assignment by rough geography
ZONES = {
    "City":            [1, 2, 3, 4, 5, 6, 7, 8, 9],        # Island City
    "Western Suburbs": [10, 11, 12, 13, 14, 15],
    "Eastern Suburbs": [16, 17, 18, 19, 20, 21, 22, 23, 24],
}
_WARD_ZONE = {}
for _z, _ww in ZONES.items():
    for _w in _ww:
        _WARD_ZONE[_w] = _z


def ward_zone(w: int) -> str:
    return _WARD_ZONE.get(w, "Mumbai")


DEPARTMENTS = {
    "SAN": {"name": "BMC Solid Waste Management Dept", "short": "Solid Waste (BMC)", "supervisor": "Ward Sanitary Inspector", "officer": "Dy Municipal Commissioner (SW Zone)", "color": "mint"},
    "WSB": {"name": "BMC Hydraulic Engineering Dept", "short": "Water Supply (BMC)", "supervisor": "Junior Engineer (Water)", "officer": "Executive Engineer (Water)", "color": "blue"},
    "PWD": {"name": "BMC Roads & Bridges Dept", "short": "Roads (BMC)", "supervisor": "Assistant Engineer (Roads)", "officer": "Chief Engineer (Roads)", "color": "orange"},
    "ELE": {"name": "BMC Street Lighting Dept", "short": "Street Lighting (BMC)", "supervisor": "Lighting Supervisor", "officer": "Executive Engineer (Electrical)", "color": "yellow"},
    "PUB": {"name": "BEST / Adani Electricity", "short": "Power (BEST/Adani)", "supervisor": "Line Supervisor", "officer": "Divisional Engineer", "color": "yellow"},
    "SWD": {"name": "BMC Stormwater Drains Dept", "short": "Stormwater (BMC)", "supervisor": "Drainage Supervisor", "officer": "Executive Engineer (SWD)", "color": "purple"},
    "PRK": {"name": "BMC Gardens & Trees Dept", "short": "Gardens (BMC)", "supervisor": "Garden Superintendent", "officer": "Tree Officer", "color": "mint"},
    "PHD": {"name": "BMC Public Health Dept", "short": "Public Health (BMC)", "supervisor": "Health Inspector", "officer": "Medical Officer of Health", "color": "coral"},
    "TRF": {"name": "Mumbai Traffic Police", "short": "Traffic Police", "supervisor": "Traffic Inspector", "officer": "DCP (Traffic)", "color": "orange"},
    "TPD": {"name": "BMC Building & Factories Dept", "short": "Enforcement (BMC)", "supervisor": "Enforcement Inspector", "officer": "Assistant Commissioner (Ward)", "color": "purple"},
    "CSC": {"name": "BMC Citizen Facilitation Centre", "short": "Citizen Cell (BMC)", "supervisor": "Grievance Officer", "officer": "Additional Municipal Commissioner", "color": "blue"},
}
EMERGENCY_TEAM = "NDRF Mumbai / BMC Disaster Management Cell"
COMMISSIONER = "BMC Municipal Commissioner's Office"

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
    {"level": 2, "at": 1.0, "role": "officer", "label": "Zonal Deputy Commissioner"},
    {"level": 3, "at": 1.5, "role": "commissioner", "label": "Municipal Commissioner / NDRF"},
]

WORKFLOW = ["Reported", "Assigned", "In Progress", "Inspection", "Resolved", "Closed"]
TERMINAL = {"Closed", "Rejected"}

# Relative performance of each department's field crews (1.0 = resolves right at SLA on average).
DEPT_PACE = {"SAN": 0.85, "WSB": 0.7, "PWD": 1.15, "ELE": 0.8, "PUB": 0.6, "SWD": 1.05, "PRK": 0.9,
             "PHD": 0.95, "TRF": 0.65, "TPD": 1.25, "CSC": 0.9}
WARD_PACE = {w: round(0.75 + (w % 7) * 0.08, 2) for w in WARDS}  # synthetic per-ward pace

# ---------------------------------------------------------------------------
# Locality-to-ward mapping (replaces sectors from Northbridge)
# Mumbai citizens refer to localities, not sector numbers.
# ---------------------------------------------------------------------------
LOCALITIES = {
    # locality name (lowercase) → ward key
    "colaba": 1, "fort": 1, "nariman point": 1, "cuffe parade": 1, "churchgate": 1,
    "dongri": 2, "sandhurst road": 2, "pydhonie": 2, "mandvi": 2,
    "bhuleshwar": 3, "crawford market": 3, "kalbadevi": 3, "girgaon": 3, "charni road": 3,
    "malabar hill": 4, "grant road": 4, "kemps corner": 4, "walkeshwar": 4, "breach candy": 4, "pedder road": 4,
    "byculla": 5, "mazgaon": 5, "reay road": 5, "lalbaug": 5,
    "matunga": 6, "sion": 6, "wadala": 6, "guru tegh bahadur nagar": 6,
    "parel": 7, "sewri": 7, "elphinstone": 7, "lower parel": 7,
    "dadar": 8, "dharavi": 8, "mahim": 8,
    "worli": 9, "prabhadevi": 9, "worli sea face": 9, "haji ali": 9,
    "bandra east": 10, "santacruz east": 10, "kalina": 10, "bkc": 10,
    "bandra west": 11, "khar": 11, "santacruz west": 11, "bandra": 11,
    "andheri east": 12, "jogeshwari east": 12, "marol": 12, "midc andheri": 12, "seepz": 12,
    "andheri west": 13, "jogeshwari west": 13, "versova": 13, "lokhandwala": 13, "oshiwara": 13,
    "malad": 14, "malad west": 14, "malad east": 14, "marve": 14, "madh island": 14,
    "goregaon": 15, "goregaon east": 15, "goregaon west": 15, "aarey": 15,
    "kurla": 16, "kurla west": 16, "kurla east": 16, "vidyavihar": 16, "saki naka": 16,
    "chembur": 17, "govandi": 17, "tilak nagar": 17, "mankhurd": 17,
    "deonar": 18, "shivaji nagar": 18, "trombay": 18,
    "ghatkopar": 19, "ghatkopar east": 19, "ghatkopar west": 19, "vikhroli": 19, "kanjurmarg": 19,
    "bhandup": 20, "nahur": 20, "powai": 20, "iit bombay": 20, "hiranandani": 20,
    "mulund": 21, "mulund east": 21, "mulund west": 21,
    "borivali": 22, "borivali west": 22, "borivali east": 22, "gorai": 22, "sanjay gandhi national park": 22,
    "dahisar": 23, "dahisar east": 23, "dahisar west": 23,
    "kandivali": 24, "kandivali east": 24, "kandivali west": 24, "charkop": 24,
}


def locality_ward(name: str) -> int | None:
    """Return the ward number for a known locality, or None."""
    return LOCALITIES.get(name.strip().lower())


# Gazetteer: landmark / road -> (lat, lng).  Lowercased keys; matched by substring.
LANDMARKS = {
    # South Mumbai
    "gateway of india": (18.9220, 72.8347), "cst": (18.9398, 72.8355), "chhatrapati shivaji terminus": (18.9398, 72.8355),
    "marine drive": (18.9432, 72.8235), "churchgate station": (18.9350, 72.8279), "flora fountain": (18.9340, 72.8330),
    "crawford market": (18.9470, 72.8330), "mumbai university": (18.9295, 72.8310), "taj hotel": (18.9217, 72.8332),
    "colaba causeway": (18.9180, 72.8318), "nariman point": (18.9250, 72.8200),
    # Central
    "dadar station": (19.0186, 72.8426), "siddhivinayak temple": (19.0170, 72.8305), "byculla zoo": (18.9790, 72.8340),
    "haji ali": (18.9827, 72.8090), "worli sea link": (19.0100, 72.8170), "nehru planetarium": (18.9700, 72.8120),
    "dharavi": (19.0430, 72.8550), "sion hospital": (19.0400, 72.8620), "hindmata junction": (18.9850, 72.8450),
    "lower parel": (18.9940, 72.8280), "parel station": (19.0010, 72.8390), "high street phoenix": (18.9940, 72.8250),
    "mahim": (19.0370, 72.8400),
    # Western Suburbs
    "bandra station": (19.0544, 72.8402), "bandra-worli sea link": (19.0370, 72.8160),
    "mount mary church": (19.0437, 72.8264), "linking road": (19.0710, 72.8430),
    "andheri station": (19.1197, 72.8468), "lokhandwala": (19.1384, 72.8290), "versova beach": (19.1322, 72.8110),
    "goregaon station": (19.1640, 72.8490), "goregaon film city": (19.1620, 72.8640),
    "malad station": (19.1870, 72.8480), "inorbit mall": (19.1790, 72.8340),
    "borivali station": (19.2310, 72.8570), "sanjay gandhi national park": (19.2300, 72.8700),
    "dahisar": (19.2540, 72.8620), "kandivali station": (19.2060, 72.8560),
    # Eastern Suburbs
    "kurla station": (19.0650, 72.8790), "bkc": (19.0650, 72.8680), "cst bus depot kurla": (19.0710, 72.8870),
    "chembur station": (19.0530, 72.8960), "govandi station": (19.0440, 72.9060),
    "ghatkopar station": (19.0868, 72.9086), "r city mall": (19.0890, 72.9100),
    "powai lake": (19.1270, 72.9060), "iit bombay": (19.1334, 72.9133), "hiranandani": (19.1220, 72.9110),
    "mulund station": (19.1725, 72.9520), "mulund check naka": (19.1810, 72.9560),
    "vikhroli station": (19.1100, 72.9280), "bhandup station": (19.1470, 72.9370),
    # Transport hubs
    "mumbai central station": (18.9690, 72.8210), "dadar tt": (19.0186, 72.8426),
    "lokmanya tilak terminus": (19.0690, 72.8870), "csmt": (18.9398, 72.8355),
    # Major roads/areas
    "western express highway": (19.1100, 72.8540), "eastern express highway": (19.0900, 72.9100),
    "sv road": (19.0600, 72.8400), "link road": (19.0700, 72.8430),
    "juhu beach": (19.0948, 72.8267), "juhu": (19.0948, 72.8267),
    "carter road": (19.0640, 72.8250), "bandstand": (19.0440, 72.8190),
    "reclamation": (19.0540, 72.8250),
}
