"""Seed ~5 weeks of synthetic city history by replaying citizen reports through the real agent pipeline.

Reports are submitted in chronological order on the simulated clock and the orchestrator's control loop
ticks every 3 simulated hours, so field progress, verification, reopenings and escalations all happen
exactly as they would live. Includes the problem-statement scenario: a garbage cluster near Sector 14.
"""
import random

from . import db
from .agents.orchestrator import Orchestrator

DAY = 86400
rng = random.Random(14)

TEMPLATES = {
    "garbage_uncollected": (16, ["Garbage not collected in our lane for {d} days {loc}", "Dustbin overflowing and kachra spread on road {loc}, smell is unbearable",
                                 "Waste pile {loc} not cleared since {d} days, stray dogs and flies everywhere", "Garbage van has not come for {d} days {loc}"]),
    "illegal_dumping": (4, ["Construction debris dumped on footpath {loc}", "People burning garbage at night {loc}, smoke entering homes"]),
    "water_leakage": (9, ["Water pipeline leakage {loc}, clean water flowing on road for {d} days", "Pipe burst {loc}, lot of water wastage and road getting damaged"]),
    "no_water_supply": (6, ["No water supply in our building {loc} since {d} days", "Very low pressure water supply {loc}, residents depending on tanker"]),
    "contaminated_water": (3, ["Dirty yellow water coming in taps {loc}, children falling sick", "Contaminated drinking water supply {loc} with foul smell"]),
    "pothole": (11, ["Huge pothole {loc}, vehicles swerving and two-wheelers falling", "Deep potholes on the main road {loc} causing traffic jam", "Big pothole {loc} filled with water, accident risk"]),
    "road_damage": (4, ["Footpath broken {loc}, elderly people find it unsafe", "Road surface cracked and damaged {loc} after rains"]),
    "open_manhole": (2, ["Open manhole {loc} right next to the school gate, very dangerous for children", "Manhole cover missing {loc}, someone may fall in at night"]),
    "streetlight_out": (9, ["Streetlights not working {loc} for {d} days, area is dark at night and unsafe", "Street light pole light off {loc}, women feel unsafe walking"]),
    "power_outage": (4, ["Power cut {loc} since {d} hours, transformer issue", "No electricity in entire colony {loc} since morning"]),
    "exposed_wire": (2, ["Live wire hanging low {loc}, sparking during rain", "Exposed electric wire on the pole {loc} near children's play area"]),
    "drain_blockage": (8, ["Drain blocked {loc}, dirty water overflowing onto road", "Choked nala {loc}, mosquito breeding and foul smell"]),
    "waterlogging": (5, ["Severe waterlogging {loc} after rain, knee deep water and traffic stuck", "Road flooded {loc}, water entering shops"]),
    "sewage_overflow": (4, ["Sewage overflowing {loc} for {d} days, health hazard for residents", "Sewer chamber overflow {loc}, toilet water on street"]),
    "fallen_tree": (3, ["Tree fell on the road {loc} blocking traffic", "Dangerous tree leaning over houses {loc}, branch fell yesterday"]),
    "park_maintenance": (3, ["Park benches broken and swings damaged {loc}", "Garden grass overgrown and playground not maintained {loc}"]),
    "stray_animals": (4, ["Stray dog menace {loc}, a child was bitten last week", "Cattle sitting on road {loc} causing traffic issues"]),
    "mosquito_breeding": (3, ["Mosquito breeding in stagnant water {loc}, dengue cases in our society", "Need fogging {loc}, too many mosquitoes"]),
    "traffic_signal": (3, ["Traffic signal not working {loc}, chaos at the junction", "Signal off since morning {loc}, near accident happened"]),
    "encroachment": (3, ["Hawkers have encroached the entire footpath {loc}", "Illegal construction blocking the lane {loc}"]),
    "noise_pollution": (2, ["Loudspeaker noise late at night {loc}", "Constant loud music from hall {loc} after 11 pm"]),
}
LANDMARK_PHRASES = ["near the temple", "near Hanuman Temple", "opposite City Hospital", "near the bus depot", "on MG Road", "near the railway station",
                    "behind Old Market", "near Riverside Promenade", "on Lakeview Road", "near Civic Centre", "near the school", "in Shanti Nagar",
                    "near Greenfield community park", "on Airport Road", "in the Industrial Estate", "near the mall", "near the stadium",
                    "near the college", "near the church", "near the gurudwara", "in New Township", "near the flyover", "in Hillcrest"]
FIRST = ["Ananya", "Rohan", "Priya", "Vikram", "Sneha", "Arjun", "Meera", "Kabir", "Isha", "Aditya", "Farah", "Imran", "Neha", "Siddharth", "Pooja",
         "Rahul", "Kavya", "Dev", "Sana", "Tanvi", "Harsh", "Nisha", "Omkar", "Ritu", "Yash", "Zoya", "Gaurav", "Shreya", "Aman", "Lakshmi"]
LAST = ["Mehta", "Kulkarni", "Iyer", "Patil", "Shah", "Khan", "Deshmukh", "Nair", "Joshi", "Rao", "Gupta", "Pawar", "Fernandes", "Sharma", "Singh"]


def loc_phrase():
    r = rng.random()
    s = rng.randint(1, 36)
    if r < 0.45:
        return f"in Sector {s}", f"Sector {s}"
    if r < 0.8:
        lm = rng.choice(LANDMARK_PHRASES)
        return lm, lm.split(" ", 1)[1] if lm.startswith(("near", "on", "in", "opposite", "behind")) else lm
    lm = rng.choice(LANDMARK_PHRASES)
    return f"{lm}, Sector {s}", f"{lm.split(' ', 1)[1]}, Sector {s}"


def make_report():
    types, weights = zip(*[(k, v[0]) for k, v in TEMPLATES.items()])
    it = rng.choices(types, weights)[0]
    tpl = rng.choice(TEMPLATES[it][1])
    loc_in_text, loc_field = loc_phrase()
    text = tpl.format(loc=loc_in_text, d=rng.choice([2, 3, 4, 5, 6, 7]))
    return text, loc_field if rng.random() < 0.7 else ""


def seed(days=35, per_day=18):
    db.reset()
    db.set_setting("clock_offset_hours", 0)
    db.set_setting("rain_mm_hr", 24)
    orch = Orchestrator()
    now = db.now()
    start = now - days * DAY
    citizens = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(220)]

    events = []
    for _ in range(days * per_day):
        t = start + rng.random() * days * DAY
        events.append((t, *make_report(), rng.choice(citizens)))

    # Recurring incidents: several citizens reporting the same problem within a few days
    incidents = [
        ("garbage_uncollected", "Garbage not collected for {d} days near the community park, Sector 14", "Sector 14 community park", now - 3 * DAY, 11, 2.8),
        ("water_leakage", "Water leaking from the pipeline on Lakeview Road, flowing across the road", "Lakeview Road", now - 2 * DAY, 6, 1.6),
        ("pothole", "Big potholes on MG Road near the junction causing traffic jam", "MG Road", now - 4 * DAY, 7, 3.5),
        ("drain_blockage", "Blocked drain in Shanti Nagar, dirty water overflowing on road", "Shanti Nagar", now - 1.5 * DAY, 5, 1.3),
        ("streetlight_out", "Streetlights not working near Riverside Promenade, very dark at night", "Riverside Promenade", now - 9 * DAY, 6, 2),
        ("sewage_overflow", "Sewage overflowing near the railway station for days, terrible smell", "near the railway station", now - 12 * DAY, 5, 2),
    ]
    # Recent surge (monsoon evening) so the live board has real open work
    for _ in range(46):
        events.append((now - rng.random() * 1.5 * DAY, *make_report(), rng.choice(citizens)))
    for _it, text, loc, t0, n, spread in incidents:
        for _ in range(n):
            events.append((t0 + rng.random() * spread * DAY, text.format(d=rng.choice([3, 4, 5])), loc, rng.choice(citizens)))
    events = [e for e in events if e[0] < now - 600]
    events.sort()

    next_tick = start
    for t, text, loc, name in events:
        while next_tick <= t:
            orch.tick(next_tick)
            next_tick += 3 * 3600
        # Tickets from the last ~10 h are left for live operators (not auto-progressed by the crew simulator)
        orch.intake(text, loc, name, at=t, use_ai=False, simulate=not (t > now - 10 * 3600 and rng.random() < 0.6))
    orch.tick(now)

    # A few reports that operators found to be false / malicious -> reputation penalty
    for c in db.query("SELECT id FROM complaints WHERE status='Assigned' AND is_primary=1 AND cluster_id IS NULL ORDER BY created_at DESC LIMIT 4"):
        orch.update_status(c["id"], "Rejected", "Ward Officer", "Field visit found no such issue")
    db.log_event("Master Orchestrator", f"System initialised with {len(events)} historical reports; 11 agents online", level="success", at=now)
    return len(events)


if __name__ == "__main__":
    import time
    t = time.time()
    n = seed()
    print(f"seeded {n} reports in {time.time() - t:.1f}s")
    for row in db.query("SELECT status, COUNT(*) n FROM complaints GROUP BY status"):
        print(row)
