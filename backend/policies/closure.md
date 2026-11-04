# Resolution and closure policy

> CivicPulse operating policy (illustrative). Describes the rules the Resolution Verification and
> Workflow agents enforce; it is not an official BMC/MCGM circular.

## POL-VER-001 | Resolved is a claim, closed is verified
tags: verification, closure, resolved, closed, citizen confirmation, 48 hours
version: 2026.11

A crew marking a ticket "Resolved" opens a 48-hour verification window. The ticket is "Closed" only
when the citizen confirms the fix with a rating of 3 or more, or when the 48 hours pass with no negative
signal. SLA compliance is measured at the resolution time, but the ticket stays visible until closed.

## POL-VER-002 | Reopening on a failed verification
tags: verification, reopen, rating, feedback, dissatisfied, not fixed
version: 2026.11

A citizen rating of 2 or less reopens the ticket and re-dispatches the crew. This applies during the
verification window and also after closure. The reopen count is published in the transparency report.

## POL-VER-003 | Follow-up complaints
tags: verification, follow-up, recurrence, duplicate, reopen
version: 2026.11

A new report that clusters onto an incident during its verification window fails verification and
reopens the incident. A new report after closure is recorded as a recurrence and also reopens it.

## POL-INT-001 | Duplicate reports become one incident
tags: duplicate, cluster, incident, merge, radius, similarity
version: 2026.11

Reports in the same category within 400 m and 7 days whose combined geo, text and type similarity is at
least 0.62 are merged into one civic incident. The incident inherits the lead ticket's SLA and crew;
growth of the cluster can raise the incident's severity but never lower it.

## POL-INT-002 | Reporter reputation never blocks a report
tags: reputation, credibility, citizen, rejected, false report
version: 2026.11

Reporter reputation (0-100, starting at 60) is only a light weight in the severity score. No report is
refused or deprioritised to the point of being ignored because of a low reputation. Rejected reports
cost 15 points; verified fixes earn 3.
