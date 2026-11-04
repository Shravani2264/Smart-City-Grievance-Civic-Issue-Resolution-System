# Escalation policy

> CivicPulse operating policy (illustrative). Describes the rules the Escalation and SLA agents
> enforce; it is not an official BMC/MCGM circular.

## POL-ESC-001 | Escalation ladder
tags: escalation, sla, delay, breach, supervisor, deputy commissioner, commissioner, ndrf
version: 2026.11

Every open lead ticket is checked against its SLA on each control-loop tick. When the fraction of the
SLA that has elapsed crosses a checkpoint, the ticket climbs one rung and the named officer is notified:

- Level 1 at 50% of the SLA: the owning department's ward supervisor.
- Level 2 at 100% of the SLA (breach): the department's zonal officer / Deputy Municipal Commissioner.
- Level 3 at 150% of the SLA: the Municipal Commissioner's Office, or the NDRF / BMC Disaster
  Management Cell when the ticket is CRITICAL.

Rungs are never skipped silently: if several checkpoints are crossed at once (for example after a long
outage), each rung is recorded with the time it should have fired.

## POL-ESC-002 | Breach-risk alert to the crew
tags: escalation, sla, at risk, warning, crew, breach risk
version: 2026.11

Before any formal escalation, the assigned field crew gets a single breach-risk alert when the time
remaining on the SLA falls to 2 hours or 25% of the SLA, whichever is larger. The alert is not sent
again once the ticket has reached Level 2.

## POL-ESC-003 | Immediate alert for critical hazards
tags: escalation, critical, hazard, emergency, immediate, safety
version: 2026.11

A ticket scored CRITICAL (severity 80+) alerts the supervisor and the emergency cell at intake, without
waiting for the first checkpoint. Its SLA is also halved (see the SLA service standards).
