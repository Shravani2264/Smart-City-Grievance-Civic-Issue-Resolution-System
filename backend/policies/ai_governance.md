# AI governance policy

> CivicPulse operating policy (illustrative). Describes how the system uses language models and
> external tools.

## POL-AI-001 | What the language model may decide
tags: ai, llm, governance, decision, classification, routing, accountability
version: 2026.11

The language model may suggest the issue type, a ticket title, the location phrase, urgency signals and
the wording of the transparency report. It never decides the owning department, the SLA, the priority
band, escalation or a ticket's status. Those are computed by rules from this policy set, so every
consequential decision can be traced to a policy clause.

## POL-AI-002 | Citizen text is untrusted data
tags: ai, prompt injection, security, untrusted input, sanitise
version: 2026.11

Citizen text is screened for injection patterns, stripped of role-delimiter tokens, capped in length
and wrapped in data markers before it reaches a model. A detected attempt is noted in the agent trace
and lightly lowers reporter reputation, but the complaint is still processed.

## POL-AI-003 | External tool results are untrusted data
tags: ai, mcp, tools, external data, validation, fallback
version: 2026.11

Results from MCP tool servers are validated against an expected shape and range before use, are never
passed to a model as instructions, and every call has a timeout and a rules-based fallback.

## POL-AI-004 | Rules first, model when uncertain
tags: ai, cascade, cost, latency, confidence, rules engine
version: 2026.11

Each complaint is first classified by the rules engine. The language model is only called when the rules
are not confident (below 0.85), no known pattern matched, or a photo is attached. Identical requests are
answered from a short-lived response cache instead of calling the model again. Policy answers and report
narratives quote retrieved policy clauses and cite their IDs.
