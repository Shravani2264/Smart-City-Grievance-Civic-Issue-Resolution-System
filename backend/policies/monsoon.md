# Monsoon preparedness policy

> CivicPulse operating policy (illustrative). Describes the rules the Predictive Intelligence agent
> applies; it is not an official BMC/MCGM SOP.

## POL-MON-001 | Ward waterlogging risk levels and actions
tags: monsoon, rainfall, waterlogging, flood, drainage, pumps, advisory, risk
version: 2026.11

Ward waterlogging risk (0-100) combines forecast rainfall against the ward's drain capacity, how
low-lying the ward is, open drain and sewer blockages, and waterlogging reports in the last 60 days.

- SEVERE (75+): pre-deploy pumps and a desilting crew, issue a citizen advisory, divert traffic.
- HIGH (55-74): clear open blockages within 6 hours and stage a pump.
- MODERATE (35-54): inspect known choke points before the rainfall.
- LOW: routine monitoring.

## POL-MON-002 | Rainfall data source
tags: monsoon, rainfall, forecast, weather, mcp, live data
version: 2026.11

The forecast may come from a live weather feed through an MCP rainfall server, or from the operator's
manual setting. A live value is only used after validation (a number between 0 and 150 mm/h); otherwise
the system falls back to the manual setting and says so on the dashboard.
