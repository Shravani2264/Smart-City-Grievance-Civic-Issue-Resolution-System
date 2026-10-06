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

### RAG + vector search (ChromaDB)

Every complaint is embedded (MiniLM, 384-d, local ONNX — no PyTorch, runs offline) into a **ChromaDB** vector store. Two agents use it:

- **Duplicate Detection** scores semantic similarity, so "kachra pile" matches "trash heap uncollected" and "nala choked" matches "drain blocked" with no shared keywords. Falls back to keyword Jaccard if ChromaDB is absent.
- **Complaint Understanding** retrieves a few similar past complaints with their confirmed issue types and feeds them to the LLM as grounding examples (few-shot RAG).

Optional: `pip install chromadb` enables it; the system runs unchanged without it. `GET /api/health` reports the RAG status and vector count.

### Prompt-injection defence (`backend/app/guard.py`)

Citizen text is untrusted and flows into an LLM prompt, so it is defended in three layers: **detect** known injection/jailbreak patterns, **neutralise** role-delimiter tokens and cap length, and **isolate** the text inside `<citizen_complaint>` data markers with a system instruction never to obey anything inside them. Defence in depth: every consequential decision (routing, SLA, priority band, status) is made by the rules engine, never the model — so even an undetected injection cannot change where a ticket goes or close it. Detected attempts are flagged in the agent trace and lightly dent reporter reputation.

### Durable execution

All state lives in SQLite (WAL). Multi-step writes that must be atomic — merging a report into an incident — run inside `with db.transaction():`, so a crash mid-merge can never leave a half-updated cluster. On startup `db.recover()` re-syncs any state an unclean shutdown could have skewed (cluster counts, lost primaries), and the 20-second control loop recomputes from the database each tick, so the pipeline resumes cleanly after a restart.

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

The tests cover the problem-statement scenario, critical-hazard routing, landmark geocoding, the full lifecycle with a citizen-triggered reopen, escalation to L3 after a time warp, reports and forecasts, and classifier paraphrases.

## Evaluation

```powershell
cd backend; python -m eval.evaluate            # offline (rules engine)
cd backend; python -m eval.evaluate --ai       # live LLM via LangChain
```

Runs a labelled gold set through the real pipeline and reports classification accuracy, routing accuracy, priority-band agreement, duplicate-detection precision/recall, prompt-injection resistance, and per-agent latency. Representative run (synthetic gold set of 20 complaints + probes):

| Metric | Rules engine | AI mode (Groq) |
|---|---|---|
| Issue-type accuracy | 90% | 95% |
| Category / routing accuracy | 90% | 95% |
| Priority-band acceptable | 100% | 100% |
| Duplicate precision / recall (semantic) | 100% / 100% | 100% / 100% |
| Prompt-injection detected | 100% | 100% |
| Pipeline stayed safe under injection | 100% | 100% |
| End-to-end latency (mean) | ~0.44 s | ~3.8 s |

The LLM lifts accuracy a few points at a ~10× latency cost (the Groq round-trip); semantic dedup adds ~190 ms per complaint for the query embedding. Numbers vary with the model and free-tier rate limits — during one AI run a Groq 429 was caught and the pipeline fell back to rules mid-flight, exactly as designed.

## Notes

- The system is configured for **Mumbai (BMC)** with all 24 administrative wards (A through T). Ward population, elevation and drainage-capacity figures are synthetic approximations for demo purposes. Landmark coordinates are real. The gazetteer is in `backend/app/config.py`.
- Field crews and citizen feedback for historical tickets come from a deterministic simulator, so the control loop has something to act on. Tickets an operator touches leave the simulator.
- Stack: **LangChain** + Groq (LLM) · **ChromaDB** (RAG / vector search) · FastAPI + SQLite/WAL · React 19 + TypeScript + Vite.
