"""Agent 2 - Location Intelligence: vague place description -> geotag, ward, zone and jurisdiction.

Mumbai edition: resolves locality names (Dadar, Andheri, Bandra …), landmark gazetteer entries and
ward codes (A–T) to latitude/longitude inside the BMC boundary.  Falls back to nearest-ward-centroid
when no textual clue is found.
"""
import hashlib
import math
import re

from ..config import (CITY, LANDMARKS, LAT_MAX, LAT_MIN, LNG_MAX, LNG_MIN, LOCALITIES, MUNICIPALITY,
                      WARDS, ward_zone)
from .base import Agent, AgentResult


def ward_center(ward: int):
    return WARDS[ward]["center"]


def ward_of(lat: float, lng: float) -> int:
    """Return the nearest ward by centroid distance (works for irregular ward shapes)."""
    best, best_d = 1, float("inf")
    for w, m in WARDS.items():
        c = m["center"]
        d = (lat - c[0]) ** 2 + (lng - c[1]) ** 2
        if d < best_d:
            best, best_d = w, d
    return best


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
    return dist * math.cos(ang) / 111_000, dist * math.sin(ang) / (111_000 * math.cos(math.radians(19.07)))


def _match_locality(text: str):
    """Find the longest matching locality name in *text*; return (locality, ward) or (None, None)."""
    best, best_w, best_len = None, None, 0
    for loc, w in LOCALITIES.items():
        if loc in text and len(loc) > best_len:
            best, best_w, best_len = loc, w, len(loc)
    return best, best_w


class LocationIntelligenceAgent(Agent):
    name = "Location Intelligence"

    def run(self, location_text: str, complaint_text: str, lat=None, lng=None, seed="") -> AgentResult:
        return self.timed(self._run, location_text or "", complaint_text or "", lat, lng, seed)

    def _run(self, location_text, complaint_text, lat, lng, seed):
        combined = f"{location_text} {complaint_text}".lower()
        method, confidence, locality, landmark = "", 0.0, None, None
        evidence = []

        if lat is not None and lng is not None:
            method, confidence = "device GPS", 0.97
            evidence.append("GPS coordinates supplied by the citizen's device")
        else:
            # Try to match a locality name (e.g. "Dadar", "Andheri West", "BKC")
            locality, loc_ward = _match_locality(combined)

            # Try landmark gazetteer (longest match first)
            lm = sorted((k for k in LANDMARKS if re.search(r"\b" + re.escape(k) + r"\b", combined)), key=len, reverse=True)
            landmark = lm[0] if lm else None

            # Ward code hint (e.g. "Ward K/E", "Ward A")
            wm = re.search(r"ward[\s\-#]*([A-Za-z]{1,2}(?:/[A-Za-z])?)", combined)
            ward_hint = None
            if wm:
                code = wm.group(1).upper()
                for w, m in WARDS.items():
                    if m["code"] == code:
                        ward_hint = w
                        break

            # Also try numeric ward reference (less common in Mumbai but some people use it)
            if not ward_hint:
                wm_num = re.search(r"ward[\s\-#]*(\d{1,2})", combined)
                if wm_num and 1 <= int(wm_num.group(1)) <= 24:
                    ward_hint = int(wm_num.group(1))

            if locality and landmark:
                l_lat, l_lng = LANDMARKS[landmark]
                lm_ward = ward_of(l_lat, l_lng)
                if lm_ward == loc_ward:
                    # Locality and landmark agree → high confidence triangulation
                    w_lat, w_lng = ward_center(loc_ward)
                    lat = (w_lat + l_lat) / 2
                    lng = (w_lng + l_lng) / 2
                    method, confidence = "locality + landmark triangulation", 0.93
                    evidence.append(f"Locality '{locality}' (Ward {WARDS[loc_ward]['code']}) confirmed by landmark '{landmark}'")
                else:
                    # Landmark takes priority over vague locality
                    lat, lng = l_lat, l_lng
                    method, confidence = "landmark gazetteer", 0.82
                    evidence.append(f"Landmark '{landmark}' is in Ward {WARDS[lm_ward]['code']}, different from locality '{locality}' (Ward {WARDS[loc_ward]['code']}); trusting landmark")
                    locality = None
            elif locality:
                lat, lng = ward_center(loc_ward)
                method, confidence = "locality centroid", 0.80
                evidence.append(f"Locality '{locality}' resolves to Ward {WARDS[loc_ward]['code']} ({WARDS[loc_ward]['name']})")
            elif landmark:
                lat, lng = LANDMARKS[landmark]
                method, confidence = "landmark gazetteer", 0.78
                evidence.append(f"Matched gazetteer landmark '{landmark}'")
            elif ward_hint:
                lat, lng = ward_center(ward_hint)
                method, confidence = "ward centroid", 0.55
                evidence.append(f"Citizen named Ward {WARDS[ward_hint]['code']}")
            else:
                ward_guess = int(hashlib.md5(combined.encode()).hexdigest(), 16) % 24 + 1
                lat, lng = ward_center(ward_guess)
                method, confidence = "unresolved - field verification needed", 0.25
                evidence.append("No locality, ward or known landmark found; placed at a provisional ward centroid")

            dlat, dlng = _jitter(seed or combined, 220 if confidence < 0.9 else 90)
            lat, lng = lat + dlat, lng + dlng

        lat = min(LAT_MAX - 1e-4, max(LAT_MIN + 1e-4, lat))
        lng = min(LNG_MAX - 1e-4, max(LNG_MIN + 1e-4, lng))
        ward = ward_of(lat, lng)
        zone = ward_zone(ward)
        out = {
            "lat": round(lat, 6), "lng": round(lng, 6), "ward": ward, "ward_name": WARDS[ward]["name"],
            "sector": None, "landmark": landmark, "zone": zone, "municipality": MUNICIPALITY, "city": CITY,
            "locality": locality,
            "geo_confidence": confidence, "method": method, "needs_field_verification": confidence < 0.5,
        }
        return AgentResult(self.name, out, "; ".join(evidence) + f". Geotagged to Ward {WARDS[ward]['code']} ({WARDS[ward]['name']}), {zone}.")
