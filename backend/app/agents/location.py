"""Agent 2 - Location Intelligence: vague place description -> geotag, ward, zone and jurisdiction."""
import hashlib
import math
import re

from ..config import (CITY, GRID_COLS, GRID_ROWS, LANDMARKS, LAT_MAX, LAT_MIN, LNG_MAX, LNG_MIN, MUNICIPALITY, WARDS,
                      ZONES, sector_ward)
from .base import Agent, AgentResult

CELL_LAT = (LAT_MAX - LAT_MIN) / GRID_ROWS
CELL_LNG = (LNG_MAX - LNG_MIN) / GRID_COLS


def ward_cell(ward: int):
    row, col = (ward - 1) // GRID_COLS, (ward - 1) % GRID_COLS
    lat_top = LAT_MAX - row * CELL_LAT
    lng_left = LNG_MIN + col * CELL_LNG
    return row, col, lat_top, lng_left


def ward_center(ward: int):
    _, _, top, left = ward_cell(ward)
    return top - CELL_LAT / 2, left + CELL_LNG / 2


def sector_center(n: int):
    w = sector_ward(n)
    _, _, top, left = ward_cell(w)
    i = (n - 1) // 12  # 0..2 -> west, middle, east third of the ward
    return top - CELL_LAT * (0.35 + 0.15 * i), left + CELL_LNG * (0.22 + 0.28 * i)


def ward_of(lat: float, lng: float) -> int:
    col = min(GRID_COLS - 1, max(0, int((lng - LNG_MIN) / CELL_LNG)))
    row = min(GRID_ROWS - 1, max(0, int((LAT_MAX - lat) / CELL_LAT)))
    return row * GRID_COLS + col + 1


def haversine_m(a_lat, a_lng, b_lat, b_lng):
    r = 6371000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _jitter(seed: str, metres: float):
    h = hashlib.sha1(seed.encode()).digest()
    ang = h[0] / 255 * 2 * math.pi
    dist = (h[1] / 255) * metres
    return dist * math.cos(ang) / 111_000, dist * math.sin(ang) / (111_000 * math.cos(math.radians(19.05)))


class LocationIntelligenceAgent(Agent):
    name = "Location Intelligence"

    def run(self, location_text: str, complaint_text: str, lat=None, lng=None, seed="") -> AgentResult:
        return self.timed(self._run, location_text or "", complaint_text or "", lat, lng, seed)

    def _run(self, location_text, complaint_text, lat, lng, seed):
        combined = f"{location_text} {complaint_text}".lower()
        method, confidence, sector, landmark = "", 0.0, None, None
        evidence = []

        if lat is not None and lng is not None:
            method, confidence = "device GPS", 0.97
            evidence.append("GPS coordinates supplied by the citizen's device")
        else:
            m = re.search(r"sector[\s\-]*(\d{1,2})", combined)
            if m and 1 <= int(m.group(1)) <= 36:
                sector = int(m.group(1))
            lm = sorted((k for k in LANDMARKS if re.search(r"\b" + re.escape(k) + r"\b", combined)), key=len, reverse=True)
            landmark = lm[0] if lm else None
            wm = re.search(r"ward[\s\-#]*(\d{1,2})", combined)
            ward_hint = int(wm.group(1)) if wm and 1 <= int(wm.group(1)) <= 12 else None

            if sector:
                lat, lng = sector_center(sector)
                method, confidence = "sector centroid", 0.8
                evidence.append(f"Sector {sector} resolves to Ward {sector_ward(sector)}")
                if landmark:
                    l_lat, l_lng = LANDMARKS[landmark]
                    if ward_of(l_lat, l_lng) == sector_ward(sector):
                        lat, lng = (lat + l_lat) / 2, (lng + l_lng) / 2
                        method, confidence = "sector + landmark triangulation", 0.92
                        evidence.append(f"Landmark '{landmark}' lies inside the same ward; refined position")
                    else:
                        evidence.append(f"Landmark '{landmark}' is outside Sector {sector}; trusting the sector and flagging for field check")
                        landmark = None
                        confidence = 0.7
            elif landmark:
                lat, lng = LANDMARKS[landmark]
                method, confidence = "landmark gazetteer", 0.78
                evidence.append(f"Matched gazetteer landmark '{landmark}'")
            elif ward_hint:
                lat, lng = ward_center(ward_hint)
                method, confidence = "ward centroid", 0.55
                evidence.append(f"Citizen named Ward {ward_hint}")
            else:
                ward_guess = int(hashlib.md5(combined.encode()).hexdigest(), 16) % 12 + 1
                lat, lng = ward_center(ward_guess)
                method, confidence = "unresolved - field verification needed", 0.25
                evidence.append("No sector, ward or known landmark found; placed at a provisional ward centroid")
            dlat, dlng = _jitter(seed or combined, 220 if confidence < 0.9 else 90)
            lat, lng = lat + dlat, lng + dlng

        lat = min(LAT_MAX - 1e-4, max(LAT_MIN + 1e-4, lat))
        lng = min(LNG_MAX - 1e-4, max(LNG_MIN + 1e-4, lng))
        ward = ward_of(lat, lng)
        row = (ward - 1) // GRID_COLS
        zone = ZONES[row]
        out = {
            "lat": round(lat, 6), "lng": round(lng, 6), "ward": ward, "ward_name": WARDS[ward]["name"],
            "sector": sector, "landmark": landmark, "zone": zone, "municipality": MUNICIPALITY, "city": CITY,
            "geo_confidence": confidence, "method": method, "needs_field_verification": confidence < 0.5,
        }
        return AgentResult(self.name, out, "; ".join(evidence) + f". Geotagged to Ward {ward} ({WARDS[ward]['name']}), {zone}.")
