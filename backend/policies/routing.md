# Routing policy

> CivicPulse operating policy (illustrative). Describes the rules the Department Routing agent
> enforces; it is not an official BMC/MCGM circular.

## POL-RTE-001 | Department ownership and crew assignment
tags: routing, department, ownership, crew, workload, assignment, jurisdiction, ward
version: 2026.11

Each issue type has exactly one owning department (see the SLA service standards). The ticket is placed
under that department's division for the ward's zone and assigned to the zone crew with the fewest open
tickets. Ownership is decided by rules, never by the language model.

## POL-RTE-002 | Emergency cell notification
tags: routing, emergency, ndrf, disaster management, live wire, open manhole, safety
version: 2026.11

The NDRF Mumbai / BMC Disaster Management Cell is notified for every exposed live wire and every open
manhole, and for any issue with a base hazard of 75 or more when the complaint carries a safety-risk
signal.

## POL-RTE-004 | Low-confidence locations
tags: routing, location, geotag, confidence, field verification, ward centroid
version: 2026.11

When a location cannot be resolved from GPS, a known locality or a landmark, the ticket is placed at the
ward centroid (confidence 0.55) or flagged "unresolved - field verification needed" (confidence 0.25).
The crew confirms the exact spot on the first visit; the ticket is never rejected for a vague address.
