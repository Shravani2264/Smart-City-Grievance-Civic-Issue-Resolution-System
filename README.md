# CivicPulse: Autonomous Civic Grievance & Urban Operations System — Mumbai

**PS-10 · GovTech / Civic Tech.** A multi-agent system for Mumbai (BMC / MCGM). Citizens report civic issues in plain language, optionally with a photo. Eleven agents then understand the issue, geotag it, prioritise it, deduplicate it, route it, track it against an SLA, escalate delays, verify the fix, and publish transparency reports. Everything appears in a live city operations dashboard.

```
Citizen input → Understand issue + location → Classify + prioritise → Route to BMC department
→ Track SLA + progress → Detect delays + escalate → Cluster similar complaints
→ Verify resolution → Transparency reports → Mumbai city intelligence dashboard
```

## Quick start

```powershell
./start.ps1                 # builds the UI, installs Python deps, serves http://localhost:8000
```

Manual / dev mode (hot reload):

```powershell
cd backend; pip install -r requirements.txt; python -m uvicorn app.main:app --port 8000
# in a second terminal, from the project root
npm install; npm run dev    # http://localhost:5173 (proxies /api to :8000)
```

On first start the backend seeds about 5 weeks of Mumbai city history: roughly 700 reports across all 24 BMC wards, replayed in order through the real agent pipeline. Every number on the dashboard is therefore produced by the agents. None are hardcoded.

### Enable the LLM (Groq)

Copy `backend/.env.example` to `backend/.env` and set `GROQ_API_KEY`. In AI mode:

- **Complaint understanding** uses `openai/gpt-oss-120b` in JSON mode. It handles free text, including Hinglish (kachra, nala, paani).
- **Photo classification** uses the vision model `qwen/qwen3.8-27b`.
- **The monthly transparency narrative** is written by the LLM from the computed figures.

The LLM is called through **LangChain** (`langchain-groq` + LCEL chains `prompt | llm | parser`) — see `backend/app/llm.py`. Without a key, or with `CIVIC_AI_MODE=rules`, a deterministic rules engine takes over. The demo works offline. LLM output is schema-validated, and anything malformed falls back to rules.

### Prompt-injection defence (`backend/app/guard.py`)

Citizen text is untrusted and flows into an LLM prompt, so it is defended in three layers: **detect** known injection/jailbreak patterns, **neutralise** role-delimiter tokens and cap length, and **isolate** the text inside `<citizen_complaint>` data markers with a system instruction never to obey anything inside them. Defence in depth: every consequential decision (routing, SLA, priority band, status) is made by the rules engine, never the model — so even an undetected injection cannot change where a ticket goes or close it. Detected attempts are flagged in the agent trace and lightly dent reporter reputation.

### Durable execution

All state lives in SQLite (WAL). Multi-step writes that must be atomic — merging a report into an incident — run inside `with db.transaction():`, so a crash mid-merge can never leave a half-updated cluster. On startup `db.recover()` re-syncs any state an unclean shutdown could have skewed (cluster counts, lost primaries), and the 20-second control loop recomputes from the database each tick, so the pipeline resumes cleanly after a restart.

### Policy RAG (`backend/app/policy_rag.py`, `backend/policies/`)

The service rules live as versioned policy clauses (`POL-ESC-001`, `POL-VER-002`, …). Hand-written clauses are in `backend/policies/*.md`; one SLA clause per issue type (`POL-SLA-*`) and the co-notification clause are **generated from `config.py`**, so a cited SLA can never drift from the SLA that was applied. They are CivicPulse's own operating policy, not official BMC text.

- **Index:** SQLite FTS5 with BM25 ranking and Porter stemming, built in memory at startup. No vector DB, no extra dependency, nothing stored on the OneDrive-synced path.
- **Citations on decisions:** the SLA, Routing, Escalation and Verification agents attach the clause behind each decision (`output.policy`), and it shows in the agent trace.
- **Ask the policy:** `POST /api/policies/ask` retrieves the top clauses, and the LLM answers *only* from them. Cited IDs are checked against what was retrieved, and invented IDs are removed. Offline, it returns an extractive answer. The Transparency page has a panel for this.
- **Grounded narrative:** the monthly report prompt includes retrieved clauses and cites them.
- Also: `GET /api/policies?q=…` for search and `GET /api/policies/{id}` for a single clause.

### MCP client (`backend/app/mcp_client.py`)

Agents call tools on external **Model Context Protocol** servers. The bundled server `backend/mcp_servers/rainfall_server.py` exposes `get_rainfall_forecast` (Open-Meteo, no key needed). The Predictive agent uses it when you press **Live forecast (MCP)** on the Insights page (`/api/predict?source=live`).

- Sessions are persistent: one background loop, one server process reused for every call. They are warmed at startup.
- Each call has a timeout and a TTL cache, and a failed server is retried after 60 s. Tool output is validated (0–150 mm/h) and falls back to the manual setting (POL-AI-003).
- To add servers, copy `backend/mcp_servers.example.json` to `backend/mcp_servers.json`. Check status at `GET /api/mcp`. Disable with `CIVIC_MCP=off`.

### Optimisations

Of the usual "make an LLM faster" techniques, quantization, KV cache, batching and parallelism run on Groq's side. These are the application-level ones:

| Technique | Implementation |
|---|---|
| Speculative decoding → **rules-first cascade** | The rules engine is the cheap "draft". The LLM is called only when rules confidence is below `CIVIC_CASCADE_THRESHOLD` (0.85), nothing matched, or a photo is attached |
| Distillation → **optional small-model tier** | Set `GROQ_FAST_MODEL=openai/gpt-oss-20b` to try a small model first and accept it only when its confidence is ≥ 0.8 |
| KV caching → **stable prompt prefix + response cache** | The system+schema prefix is byte-identical on every call (provider prefix caching). Identical requests are served from an in-process LRU (`CIVIC_LLM_CACHE_TTL`) |
| Telemetry | LLM calls, cache hits, failures and mean latency per model in `/api/health` and the eval report |

Eval, AI mode, same session (`python -m eval.evaluate --ai`): with the cascade, **7 LLM calls instead of 35 (−80%)** for the 35 gold complaints, and issue-type accuracy unchanged at 97.1%. Mean end-to-end latency was 155 ms with the cascade vs 3,144 ms without it (Groq latency varies between runs; the call reduction is the stable number).

## The agents (`backend/app/agents/`)

| # | Agent | What it decides |
|---|---|---|
| 1 | Complaint Understanding | Issue type (22 types), urgency signals (safety, public health, traffic, vulnerable groups, wide impact, property damage), duration, location phrase, photo findings |
| 2 | Location Intelligence | Turns "near Dadar station" or "Andheri West" into lat/lng, BMC ward (A–T), zone, and a confidence score. Low-confidence locations are flagged for a field check |
| 3 | Department Routing | Owning BMC department (or BEST/Traffic Police), division, least-loaded crew, and co-notified departments (e.g. open manhole → Traffic Police + NDRF) |
| 4 | Priority & Severity | Explainable 0–100 score: base hazard + signals + persistence (health risk grows with time) + population exposure + cluster size ± reporter credibility |
| 5 | Duplicate Detection | Geo (400 m) + text similarity + issue type + recency → merges reports into one **civic incident**. Cluster growth raises the incident's severity |
| 6 | SLA Management | Service standard per issue type, tightened by priority. Escalation checkpoints at 50% / 100% / 150% of the SLA |
| 7 | Escalation | Continuously climbs Supervisor → Zonal Dy Commissioner → Municipal Commissioner / NDRF, plus breach-risk alerts to the crew |
| 8 | Workflow Tracking | Reported → Assigned → In Progress → Inspection → Resolved → Closed (+ Reopened / Rejected). Illegal transitions are refused. Clustered reports stay in sync |
| 9 | Resolution Verification | "Resolved" is a claim. A ticket closes only after citizen confirmation, no follow-up complaints, or a quiet 48 h window. A low rating or a new report reopens it |
| 10 | Transparency Reporting | Totals, resolution time, SLA compliance, satisfaction, **Government Efficiency Score** per ward and department, a narrative report, and CSV export |
| 11 | Master Orchestrator | Runs the pipeline, records every agent's reasoning in the ticket's **agent trace**, and runs the 20-second control loop |

Supporting agents: **Predictive Intelligence**, which models rainfall against drainage capacity, elevation, open blockages and history to give ward-level waterlogging risk (critical for Mumbai monsoons), and flags emerging hotspots. **Citizen Reputation** tracks verified versus false reports. It only weights priority lightly and never blocks a report.

## Demo script (5 minutes)

1. **Overview**: the live queue is sorted by SLA risk × severity. The agent activity feed sits next to the ward heatmap and incident clusters.
2. **Report issue** → *"Garbage not collected in my street for 5 days near Dharavi."* Watch the 11 agents run. The output: Solid Waste → Ward G/N (Dadar/Dharavi) → BMC Sanitation → merged into a multi-report incident → 48 h SLA → supervisor at 24 h.
3. Open the ticket and walk through the severity breakdown, escalation ladder, incident members, and the **Agent trace** tab.
4. Report *"Open manhole outside the school gate near Dadar station"*. It comes back CRITICAL with a 3 h SLA, and the NDRF/BMC Disaster Management Cell is notified immediately.
5. **Simulation clock → +24h**: crews progress, SLAs breach, escalations fire, verifications close or reopen tickets. Check the **Escalations** page.
6. On a resolved ticket, give it 1 star. Verification fails and the ticket reopens.
7. **Insights**: drag the rainfall slider and watch low-lying wards (Dharavi, Kurla, Mankhurd) light up with recommended pre-emptive actions — a key feature for Mumbai's monsoon season.
8. **Transparency** → **Generate**: the monthly civic report, ward efficiency scores, and CSV export.

## Tests

```powershell
cd backend; python -m pytest -q tests
```

The tests cover the problem-statement scenario, critical-hazard routing, landmark geocoding, the full lifecycle with a citizen-triggered reopen, escalation to L3 after a time warp, reports and forecasts, and classifier paraphrases. `test_mcp_rag.py` covers policy retrieval and citation grounding, the MCP client (against an offline fake server), failure fallback, and the LLM cascade.

## Evaluation

```powershell
cd backend; python -m eval.evaluate            # offline (rules engine)
cd backend; python -m eval.evaluate --ai       # live LLM via LangChain
```

Runs a labelled gold set through the real pipeline and reports classification accuracy, routing accuracy, priority-band agreement, duplicate-detection precision/recall, prompt-injection resistance (detection recall + false-positive rate), and per-agent latency. The gold set includes hard cases on purpose — paraphrases, Hinglish, ambiguous wording, obfuscated attacks — so the numbers are honest rather than perfect. Representative **rules-engine** run (35 labelled complaints + 33 injection attacks + 4 benign probes):

| Metric | Rules engine |
|---|---|
| Issue-type accuracy | 85.7% |
| Category / routing accuracy | 85.7% |
| Priority-band acceptable | 91.4% |
| Duplicate precision / recall | 100% / 88.9% |
| Prompt-injection detection recall | 97.0% |
| Prompt-injection false-positive rate | 0% |
| Pipeline stayed safe under injection | 100% |
| End-to-end latency (mean) | ~24 ms |

Reading the numbers:

- **Classification 85.7%** is the *keyword* fallback on a deliberately hard set (paraphrases, Hinglish, ambiguous wording). The LLM path (`--ai`) handles these far better — on a cleaner 20-case set it scored ~95% — at a ~10× latency cost (~3.8 s vs ~24 ms per complaint, the Groq round-trip). This gap is the point: it shows *why* the LLM matters.
- **Duplicate recall 88.9%** — the one miss is a true recurrence of an incident seeded ~12 days ago, which the 7-day dedup window intentionally does not merge. Precision is 100%: it never wrongly merges distinct issues.
- **Injection 97.0%** — the single miss is a leetspeak-obfuscated attack (`1gn0re all prev10us…`). It still causes no harm: **pipeline-safe stayed 100%** because routing/SLA/priority/status are rule-based, never model-controlled — so even an undetected injection can't change a ticket. False positives on benign complaints (some containing trigger-ish words) were 0%.

## Notes

- The system is configured for **Mumbai (BMC)** with all 24 administrative wards (A through T). Ward population, elevation and drainage-capacity figures are synthetic approximations for demo purposes. Landmark coordinates are real. The gazetteer is in `backend/app/config.py`.
- Field crews and citizen feedback for historical tickets come from a deterministic simulator, so the control loop has something to act on. Tickets an operator touches leave the simulator.
- Stack: **LangChain** + Groq (LLM) · FastAPI + SQLite/WAL · React 19 + TypeScript + Vite.
