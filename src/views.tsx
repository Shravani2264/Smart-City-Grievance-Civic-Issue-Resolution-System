import { useEffect, useState, type ReactNode } from 'react'
import {
  AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, Bot, Building2, CheckCircle2, ChevronRight, Clock3, CloudRain, Download, FileText,
  Filter, GitMerge, Layers, LocateFixed, Plus, ShieldAlert, Sparkles, TicketCheck, TrendingUp, UserCheck, Users,
} from 'lucide-react'
import { ago, api, fmtDur, slaText, type Citizen, type CivicEvent, type Complaint, type Dashboard, type DeptPerf, type MapData, type Prediction, type Report } from './api'
import { BarList, CityMap, Meter, SlaBadge, TrendChart, catHex, priorityClass } from './charts'

type Common = { now: number; version: number; onSelect: (id: string) => void }

function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    let live = true
    fn().then((d) => { if (live) { setData(d); setErr('') } }).catch((e) => live && setErr((e as Error).message))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, err }
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

function Metric({ label, value, note, icon, tone, trend }: { label: string; value: string; note: string; icon: ReactNode; tone: string; trend?: ReactNode }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><div className="metric-bottom"><span>{note}</span>{trend}</div></div>
}

function Loading({ err }: { err?: string }) { return <div className="empty-state">{err ? `Could not load: ${err}` : 'Loading live data...'}</div> }

const LEVEL_TONE: Record<string, string> = { critical: 'ev-critical', warning: 'ev-warning', success: 'ev-success', info: 'ev-info' }

export function EventFeed({ events, now, onSelect }: { events: CivicEvent[]; now: number; onSelect: (id: string) => void }) {
  return <div className="event-feed">{events.map((e) => (
    <button key={e.id} className={`event-row ${LEVEL_TONE[e.level] ?? ''}`} onClick={() => e.complaint_id && onSelect(e.complaint_id)} disabled={!e.complaint_id}>
      <span className="event-dot" />
      <span className="event-copy"><strong>{e.agent}</strong><small>{e.message}</small></span>
      <span className="event-time">{ago(e.at, now)}</span>
    </button>
  ))}</div>
}

function QueueItem({ c, onSelect }: { c: Complaint; onSelect: (id: string) => void }) {
  return <button className="queue-item" onClick={() => onSelect(c.id)}>
    <span className="cat-chip" style={{ background: catHex(c.category) }} />
    <span className="queue-copy"><strong>{c.title}</strong><small>{c.id} · Ward {c.ward} {c.ward_name} · {c.department}{c.cluster_size > 1 && ` · ${c.cluster_size} reports`}</small></span>
    <span className="queue-side"><span className={priorityClass(c.priority)}>{c.priority} {c.severity_score}</span><SlaBadge state={c.sla.state} text={slaText(c)} /></span>
  </button>
}

// ------------------------------------------------------------------ Overview
export function Overview({ dash, now, version, onSelect, onNavigate, onNew }: Common & { dash: Dashboard | null; onNavigate: (v: string) => void; onNew: () => void }) {
  const map = useLoad(() => api.map(), [version])
  if (!dash) return <Loading />
  const k = dash.kpis
  return <>
    <PageHeading eyebrow="CIVIC OPERATIONS CONTROL CENTER" title="City at a glance" description="Live view of every grievance the 11 agents are understanding, routing, tracking and escalating."
      action={<button className="primary-button" onClick={onNew}><Plus size={17} />Report an issue</button>} />
    <section className="metrics-grid">
      <Metric label="Open incidents" value={String(k.open)} note={`${k.open_reports} citizen reports · ${k.duplicates_merged_7d} merged (7d)`} icon={<TicketCheck size={18} />} tone="mint" />
      <Metric label="SLA at risk / breached" value={`${k.at_risk} / ${k.breached}`} note={`${k.escalated_open} escalated · ${k.critical_open} critical`} icon={<ShieldAlert size={18} />} tone="coral" trend={<span className="metric-trend warning"><AlertTriangle size={12} />Needs action</span>} />
      <Metric label="Reported / resolved (24h)" value={`${k.reported_today} / ${k.resolved_today}`} note="Auto-triaged on arrival" icon={<CheckCircle2 size={18} />} tone="blue" />
      <Metric label="Avg. resolution (7d)" value={k.avg_resolution_h ? `${k.avg_resolution_h}h` : '—'} note={`${k.sla_met_pct ?? '—'}% within SLA`} icon={<Clock3 size={18} />} tone="gold" />
    </section>

    <section className="operations-grid">
      <div className="panel issues-panel">
        <div className="panel-heading"><div><span className="eyebrow">PRIORITY QUEUE · SORTED BY SLA RISK × SEVERITY</span><h2>Needs attention</h2></div><button className="text-button" onClick={() => onNavigate('Complaints')}>All tickets <ChevronRight size={15} /></button></div>
        <div className="queue-list">{dash.queue.map((c) => <QueueItem key={c.id} c={c} onSelect={onSelect} />)}</div>
      </div>
      <div className="panel feed-panel">
        <div className="panel-heading"><div><span className="eyebrow"><span className="live-dot" /> LIVE AGENT ACTIVITY</span><h2>What the agents are doing</h2></div><button className="text-button" onClick={() => onNavigate('Agents')}>Agents <ChevronRight size={15} /></button></div>
        <EventFeed events={dash.events} now={now} onSelect={onSelect} />
      </div>
    </section>

    <section className="lower-grid">
      <div className="panel map-panel">
        <div className="panel-heading"><div><span className="eyebrow">GEOGRAPHIC INTELLIGENCE · LAST 14 DAYS</span><h2>Open issues by ward</h2></div><button className="text-button" onClick={() => onNavigate('City map')}>Open city map <ChevronRight size={15} /></button></div>
        {map.data ? <CityMap data={map.data} mode="open" onSelect={onSelect} /> : <Loading err={map.err} />}
        <div className="hotspot-footer"><span><strong>Ward {dash.hot_ward.ward} · {dash.hot_ward.name}</strong> has the most open reports</span><span className="hotspot-value">{dash.hot_ward.open} <small>open</small></span></div>
      </div>
      <div className="stack">
        <div className="panel pad">
          <div className="panel-heading"><div><span className="eyebrow">DUPLICATE DETECTION</span><h2>Active incident clusters</h2></div><GitMerge size={18} className="muted-icon" /></div>
          <div className="cluster-list">{dash.clusters.length === 0 ? <div className="empty-state">No multi-report incidents open.</div> : dash.clusters.map((cl) => (
            <button key={cl.id} className="cluster-row" onClick={() => onSelect(cl.primary_id)}>
              <span className="cluster-count">{cl.count}</span><span><strong>{cl.title}</strong><small>{cl.id} · Ward {cl.ward} · {cl.status} · last report {ago(cl.last_at, now)}</small></span><ChevronRight size={15} />
            </button>))}</div>
        </div>
        <div className="panel pad">
          <div className="panel-heading"><div><span className="eyebrow">THIS WEEK</span><h2>What residents report</h2></div></div>
          <BarList rows={dash.categories.map((c) => ({ label: c.category, value: c.count, color: catHex(c.category) }))} />
        </div>
      </div>
    </section>
  </>
}

// ------------------------------------------------------------------ Complaints
export function ComplaintsView({ now, version, onSelect, search }: Common & { search: string }) {
  const [status, setStatus] = useState('Open')
  const [priority, setPriority] = useState('')
  const [category, setCategory] = useState('')
  const [scope, setScope] = useState('all')
  const { data, err } = useLoad(() => api.complaints({ status, priority, category, q: search, scope, limit: 250 }), [status, priority, category, search, scope, version])
  return <>
    <PageHeading eyebrow="CITIZEN SERVICE DESK" title="Complaints" description="Every report, auto-classified, geotagged, prioritised and routed. Click a row for the full agent trace." />
    <div className="queue-toolbar">
      <div className="queue-summary"><span className="live-dot" />{data?.length ?? '…'} records</div>
      <div className="filters">
        <label className="filter-select"><Filter size={14} /><select value={status} onChange={(e) => setStatus(e.target.value)}>{['Open', '', 'Assigned', 'In Progress', 'Inspection', 'Resolved', 'Reopened', 'Closed', 'Rejected'].map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}</select></label>
        <label className="filter-select"><select value={priority} onChange={(e) => setPriority(e.target.value)}>{['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => <option key={s} value={s}>{s || 'All priorities'}</option>)}</select></label>
        <label className="filter-select"><select value={category} onChange={(e) => setCategory(e.target.value)}>{['', 'Solid Waste Management', 'Water Supply', 'Roads & Infrastructure', 'Electricity & Lighting', 'Drainage & Sewerage', 'Public Health', 'Parks & Trees', 'Traffic & Mobility', 'Encroachment & Planning', 'General'].map((s) => <option key={s} value={s}>{s || 'All categories'}</option>)}</select></label>
        <label className="filter-select"><Layers size={14} /><select value={scope} onChange={(e) => setScope(e.target.value)}><option value="all">All reports</option><option value="incidents">Unique incidents</option></select></label>
      </div>
    </div>
    <div className="panel full-table-panel"><div className="table-scroll">
      {!data ? <Loading err={err} /> : <table className="complaint-table"><thead><tr><th>ISSUE</th><th>LOCATION</th><th>ROUTED TO</th><th>PRIORITY</th><th>STATUS</th><th>SLA</th><th>ESC.</th></tr></thead>
        <tbody>{data.map((c) => <tr key={c.id} onClick={() => onSelect(c.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onSelect(c.id)}>
          <td><div className="table-issue"><span className="cat-chip" style={{ background: catHex(c.category) }} /><span><strong>{c.title}</strong><small>{c.id} · {ago(c.created_at, now)}{c.cluster_id && ` · ${c.cluster_id} (${c.cluster_size})`}{c.has_image ? ' · 📷' : ''}</small></span></div></td>
          <td><strong>Ward {c.ward} · {c.ward_name}</strong><small>{c.landmark ?? (c.sector ? `Sector ${c.sector}` : c.location_text || '—')}</small></td>
          <td><strong>{c.department}</strong><small>{c.unit}</small></td>
          <td><span className={priorityClass(c.priority)}>{c.priority} · {c.severity_score}</span></td>
          <td><span className={`status-label s-${c.status.toLowerCase().replace(' ', '-')}`}><i />{c.status}</span></td>
          <td><SlaBadge state={c.sla.state} text={slaText(c)} /></td>
          <td>{c.escalation_level ? <span className="esc-pill">L{c.escalation_level}</span> : '—'}</td>
        </tr>)}</tbody></table>}
      {data && data.length === 0 && <div className="empty-state">No complaints match those filters.</div>}
    </div></div>
  </>
}

// ------------------------------------------------------------------ Map
export function MapView({ version, onSelect }: Common) {
  const [mode, setMode] = useState<'open' | 'efficiency'>('open')
  const [category, setCategory] = useState('')
  const { data, err } = useLoad<MapData>(() => api.map(category), [category, version])
  return <>
    <PageHeading eyebrow="LOCATION INTELLIGENCE" title="City heatmap" description="Ward choropleth with every geotagged report from the last 14 days. Open issues are large dots; resolved ones fade." />
    <div className="queue-toolbar">
      <div className="segmented">{(['open', 'efficiency'] as const).map((m) => <button key={m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>{m === 'open' ? 'Open backlog' : 'Ward efficiency'}</button>)}</div>
      <label className="filter-select"><Filter size={14} /><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All issue types</option>{data?.categories.map((c) => <option key={c}>{c}</option>)}</select></label>
    </div>
    <section className="map-page-grid">
      <div className="panel pad">{data ? <CityMap data={data} mode={mode} onSelect={onSelect} /> : <Loading err={err} />}</div>
      <div className="panel pad hotspot-list-panel">
        <div className="panel-heading"><div><span className="eyebrow">WARDS RANKED BY OPEN BACKLOG</span><h2>Priority wards</h2></div></div>
        {data && [...data.wards].sort((a, b) => b.open - a.open).map((w, i) => (
          <div key={w.ward} className="hotspot-list-item"><span className={`hotspot-rank rank-${Math.min(4, i + 1)}`}>{String(i + 1).padStart(2, '0')}</span>
            <span><strong>Ward {w.ward} · {w.name}</strong><small>{w.top_issue ?? 'No recent reports'} · efficiency {w.efficiency ?? '—'}/100</small></span>
            <span className="hotspot-count">{w.open}<small>open</small></span></div>))}
      </div>
    </section>
  </>
}

// ------------------------------------------------------------------ Escalations
export function EscalationsView({ now, version, onSelect }: Common) {
  const { data, err } = useLoad(() => api.escalations(), [version])
  if (!data) return <Loading err={err} />
  const lad = data.ladder_30d
  return <>
    <PageHeading eyebrow="ESCALATION AGENT" title="Escalations & SLA risk" description="Tickets climb Supervisor → District Officer → Commissioner / Emergency team automatically as their SLA clock runs down." />
    <section className="metrics-grid">
      <Metric label="Breach-risk / L0 alerts" value={String(data.tickets.filter((t) => t.sla.state === 'at_risk').length)} note="Crew alerted, not yet escalated" icon={<Clock3 size={18} />} tone="gold" />
      <Metric label="L1 · Supervisor (30d)" value={String(lad['1'] ?? 0)} note="50% of SLA elapsed unresolved" icon={<UserCheck size={18} />} tone="blue" />
      <Metric label="L2 · District Officer (30d)" value={String(lad['2'] ?? 0)} note="SLA breached" icon={<ShieldAlert size={18} />} tone="coral" />
      <Metric label="L3 · Commissioner / Emergency" value={String(lad['3'] ?? 0)} note="150% of SLA elapsed" icon={<AlertTriangle size={18} />} tone="coral" />
    </section>
    <section className="esc-grid">
      <div className="panel full-table-panel"><div className="table-scroll"><table className="complaint-table esc-table"><thead><tr><th>TICKET</th><th>OWNER</th><th>SLA</th><th>ESCALATED TO</th></tr></thead><tbody>
        {data.tickets.map((t) => { const last = [...(t.escalations ?? [])].reverse().find((e) => e.level > 0); return <tr key={t.id} onClick={() => onSelect(t.id)}>
          <td><div className="table-issue"><span className="cat-chip" style={{ background: catHex(t.category) }} /><span><strong>{t.title}</strong><small>{t.id} · Ward {t.ward} · <span className={priorityClass(t.priority)}>{t.priority}</span></small></span></div></td>
          <td><strong>{t.department}</strong><small>{t.status} · {t.unit}</small></td>
          <td><SlaBadge state={t.sla.state} text={slaText(t)} /><small>SLA {t.sla_hours}h</small></td>
          <td>{last ? <><span className="esc-pill">L{last.level}</span> <strong className="inline">{last.target}</strong><small>{last.reason}</small></> : <small>Breach-risk alert to crew</small>}</td>
        </tr> })}
      </tbody></table>{data.tickets.length === 0 && <div className="empty-state">Nothing at risk. Advance the clock to watch escalations fire.</div>}</div></div>
      <div className="panel feed-panel"><div className="panel-heading"><div><span className="eyebrow">ESCALATION LOG</span><h2>Recent escalations</h2></div></div><EventFeed events={data.feed} now={now} onSelect={onSelect} /></div>
    </section>
  </>
}

// ------------------------------------------------------------------ Departments
export function DepartmentsView({ version }: Common) {
  const { data, err } = useLoad(() => api.report(30), [version])
  if (!data) return <Loading err={err} />
  return <>
    <PageHeading eyebrow="MUNICIPAL SERVICE NETWORK · LAST 30 DAYS" title="Department performance" description="Efficiency = 40% SLA compliance + 30% speed vs SLA + 20% backlog health + 10% citizen satisfaction." />
    <section className="department-cards">{data.departments.map((d) => <DeptCard key={d.code} d={d} />)}</section>
  </>
}

function DeptCard({ d }: { d: DeptPerf }) {
  return <div className="panel team-card">
    <div className="team-card-top"><span className={`team-icon ${d.color}`}><Building2 size={19} /></span><span className="team-open"><i />{d.open} open · {d.overdue} overdue</span></div>
    <h2>{d.name}</h2>
    <div className="team-kpis"><span><strong>{d.score}</strong><small>efficiency</small></span><span><strong>{d.sla_compliance}%</strong><small>within SLA</small></span><span><strong>{d.avg_resolution_h ?? '—'}h</strong><small>avg. resolution</small></span></div>
    <Meter value={d.score} label="Efficiency" />
    <div className="team-foot"><span>{d.total} tickets · {d.resolved} resolved · {d.escalations ?? 0} escalations</span><span>Satisfaction {d.satisfaction}%</span></div>
  </div>
}

// ------------------------------------------------------------------ Insights (predictive + reputation)
export function InsightsView({ version, onToast }: Common & { onToast: (m: string) => void }) {
  const [rain, setRain] = useState<number | null>(null)
  const pred = useLoad<Prediction>(() => api.predict(rain ?? undefined), [rain, version])
  const map = useLoad(() => api.map(), [version])
  const cit = useLoad(() => api.citizens(), [version])
  useEffect(() => { if (rain === null && pred.data) setRain(pred.data.rain_mm_hr) }, [pred.data, rain])
  const risk = Object.fromEntries((pred.data?.waterlogging ?? []).map((w) => [w.ward, w.risk]))
  return <>
    <PageHeading eyebrow="PREDICTIVE CIVIC INTELLIGENCE" title="Insights & forecasts" description="Anticipate problems before citizens report them: rainfall-driven waterlogging risk, surging hotspots and reporter credibility." />
    <section className="operations-grid">
      <div className="panel pad">
        <div className="panel-heading"><div><span className="eyebrow">WATERLOGGING FORECAST</span><h2>Rainfall scenario</h2></div><CloudRain size={18} className="muted-icon" /></div>
        <div className="rain-control">
          <input type="range" min={0} max={120} step={2} value={rain ?? 24} onChange={(e) => setRain(Number(e.target.value))} aria-label="Forecast rainfall mm per hour" />
          <strong>{rain ?? '…'} mm/h</strong>
          <button className="outline-button" onClick={async () => { if (rain !== null) { await api.setRain(rain); onToast(`Forecast set to ${rain} mm/h - drainage teams briefed on high-risk wards`) } }}>Use as forecast</button>
        </div>
        {map.data ? <CityMap data={map.data} mode="risk" highlight={risk} showPoints={false} /> : <Loading err={map.err} />}
      </div>
      <div className="panel pad">
        <div className="panel-heading"><div><span className="eyebrow">PRE-EMPTIVE ACTIONS</span><h2>Wards at risk</h2></div></div>
        <div className="risk-list">{pred.data?.waterlogging.slice(0, 6).map((w) => (
          <div key={w.ward} className="risk-row"><span className={`risk-score r-${w.level.toLowerCase()}`}>{w.risk}</span>
            <span><strong>Ward {w.ward} · {w.name} <em className={`risk-tag r-${w.level.toLowerCase()}`}>{w.level}</em></strong><small>{w.drivers.join(' · ')}</small><small className="risk-action"><ArrowRight size={11} />{w.action}</small></span></div>))}</div>
      </div>
    </section>
    <section className="lower-grid">
      <div className="panel pad">
        <div className="panel-heading"><div><span className="eyebrow">EMERGING HOTSPOTS · 72H VS 14-DAY BASELINE</span><h2>Surging issues</h2></div><TrendingUp size={18} className="muted-icon" /></div>
        {pred.data && pred.data.hotspots.length === 0 && <div className="empty-state">No abnormal surges detected.</div>}
        {pred.data?.hotspots.map((h) => <div className="risk-row" key={`${h.ward}-${h.category}`}><span className="cat-chip big" style={{ background: catHex(h.category) }} />
          <span><strong>{h.category} · Ward {h.ward} {h.name}</strong><small>{h.last_72h} reports in 72h vs {h.expected} expected · {h.surge}× surge · projected {h.projection_7d} this week</small></span></div>)}
      </div>
      <div className="panel pad">
        <div className="panel-heading"><div><span className="eyebrow">CITIZEN REPUTATION</span><h2>Reporter credibility</h2></div><Users size={18} className="muted-icon" /></div>
        <p className="panel-note">Verified fixes and first reports of real incidents raise reputation; reports found false lower it. Low reputation slightly lowers priority. Reports are never blocked.</p>
        <div className="rep-cols">
          <div><h3>Most helpful</h3>{cit.data?.top.slice(0, 5).map((c) => <RepRow key={c.id} c={c} />)}</div>
          <div><h3>Flagged</h3>{cit.data?.flagged.length ? cit.data.flagged.slice(0, 5).map((c) => <RepRow key={c.id} c={c} />) : <small className="muted">None</small>}</div>
        </div>
      </div>
    </section>
  </>
}

function RepRow({ c }: { c: Citizen }) {
  return <div className="rep-row"><span className="profile-avatar small">{c.name.split(' ').map((p) => p[0]).join('').slice(0, 2)}</span><span><strong>{c.name}</strong><small>{c.reports} reports · {c.verified} verified{c.rejected ? ` · ${c.rejected} false` : ''}</small></span><strong className={c.reputation < 40 ? 'danger-text' : ''}>{Math.round(c.reputation)}</strong></div>
}

// ------------------------------------------------------------------ Transparency
export function TransparencyView({ version, aiEnabled }: Common & { aiEnabled: boolean }) {
  const [days, setDays] = useState(30)
  const [narr, setNarr] = useState<{ text: string; mode: string } | null>(null)
  const [loadingNarr, setLoadingNarr] = useState(false)
  const { data, err } = useLoad<Report>(() => api.report(days), [days, version])
  useEffect(() => setNarr(null), [days])
  if (!data) return <Loading err={err} />
  const prev = data.prev_avg_resolution_h
  const faster = prev && data.avg_resolution_h ? prev - data.avg_resolution_h : null
  async function generate() {
    setLoadingNarr(true)
    try { const r = await api.report(days, true); setNarr({ text: r.narrative ?? '', mode: r.narrative_mode ?? '' }) } finally { setLoadingNarr(false) }
  }
  return <>
    <PageHeading eyebrow="PUBLIC ACCOUNTABILITY" title="Transparency report" description="Open, aggregated performance data for residents and councillors. No personal citizen data is published."
      action={<a className="outline-button" href={`/api/report.csv?days=${days}`}><Download size={16} />Export CSV</a>} />
    <div className="report-controls"><span><span className="live-dot" />REPORTING PERIOD</span>
      <div className="segmented">{[7, 30, 90].map((d) => <button key={d} className={days === d ? 'on' : ''} onClick={() => setDays(d)}>{d === 7 ? 'Week' : d === 30 ? 'Month' : 'Quarter'}</button>)}</div></div>
    <section className="report-metrics">
      <Metric label="Total complaints" value={data.total_complaints.toLocaleString()} note={`${data.unique_incidents} incidents · ${data.duplicates_merged} duplicates merged`} icon={<FileText size={18} />} tone="mint" />
      <Metric label="Resolved" value={data.resolved.toLocaleString()} note={`${data.resolution_rate}% · ${data.closed_verified} verified closed`} icon={<CheckCircle2 size={18} />} tone="blue" />
      <Metric label="Avg. resolution time" value={data.avg_resolution_h ? `${data.avg_resolution_h}h` : '—'} note={prev ? `Previous period ${prev}h` : 'No prior period'} icon={<Clock3 size={18} />} tone="gold"
        trend={faster !== null ? <span className={`metric-trend ${faster > 0 ? 'positive' : 'warning'}`}>{faster > 0 ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}{fmtDur(Math.abs(faster))}</span> : undefined} />
      <Metric label="City efficiency score" value={`${data.city_efficiency ?? '—'}/100`} note={`${data.sla_compliance}% in SLA · ${data.satisfaction ?? '—'}/5 satisfaction`} icon={<TrendingUp size={18} />} tone="coral" />
    </section>
    <section className="lower-grid transparency-lower">
      <div className="panel pad"><div className="panel-heading"><div><span className="eyebrow">DAILY FLOW</span><h2>Reported vs resolved</h2></div></div><TrendChart data={data.daily} /></div>
      <div className="panel pad"><div className="panel-heading"><div><span className="eyebrow">TOP ISSUES</span><h2>What residents report</h2></div></div>
        <BarList rows={data.top_issues.slice(0, 7).map((t) => ({ label: t.category, value: t.count, color: catHex(t.category), note: `${t.resolved} resolved` }))} /></div>
    </section>
    <section className="lower-grid">
      <div className="panel full-table-panel"><div className="panel-heading pad-x"><div><span className="eyebrow">WARD EFFICIENCY</span><h2>Government efficiency score by ward</h2></div></div><div className="table-scroll"><table className="complaint-table compact"><thead><tr><th>WARD</th><th>SCORE</th><th>TICKETS</th><th>OPEN</th><th>OVERDUE</th><th>TOP ISSUE</th></tr></thead><tbody>
        {[...data.wards].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).map((w) => <tr key={w.ward}><td><strong>Ward {w.ward} · {w.name}</strong></td><td><div className="score-cell"><strong>{w.score ?? '—'}</strong><Meter value={w.score} /></div></td><td>{w.total}</td><td>{w.open}</td><td>{w.overdue}</td><td>{w.top_issue ?? '—'}</td></tr>)}
      </tbody></table></div></div>
      <div className="panel pad narrative-panel">
        <div className="panel-heading"><div><span className="eyebrow">REPORTING AGENT</span><h2>Monthly civic report</h2></div><button className="primary-button" onClick={generate} disabled={loadingNarr}><Sparkles size={15} />{loadingNarr ? 'Writing…' : narr ? 'Regenerate' : 'Generate'}</button></div>
        {narr ? <><Markdown text={narr.text} /><small className="muted">{narr.mode === 'ai' ? 'Written by the Groq LLM from the figures above.' : 'Template narrative (enable GROQ_API_KEY for an AI-written report).'}</small></>
          : <p className="panel-note">Generates a plain-language public report from this period's figures{aiEnabled ? ' using the Groq LLM' : ''}: highlights, shortfalls and measurable commitments.</p>}
      </div>
    </section>
  </>
}

function Markdown({ text }: { text: string }) {
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => p.startsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : p)
  return <div className="md">{text.split('\n').map((l, i) => l.startsWith('###') ? <h3 key={i}>{l.replace(/^#+\s*/, '')}</h3>
    : l.startsWith('- ') || l.startsWith('* ') ? <li key={i}>{inline(l.slice(2))}</li> : l.trim() ? <p key={i}>{inline(l)}</p> : null)}</div>
}

// ------------------------------------------------------------------ Agents
const FLOW = ['Citizen input', 'Understand issue + location', 'Classify + prioritise', 'Route to department', 'Track SLA + progress', 'Detect delays + escalate', 'Cluster similar complaints', 'Transparency reports', 'City dashboard']

export function AgentsView({ version }: Common) {
  const { data, err } = useLoad(() => api.agents(), [version])
  return <>
    <PageHeading eyebrow="MULTI-AGENT ARCHITECTURE" title="The agent network" description="Eleven specialised agents, coordinated by a master orchestrator. Each decision is recorded in the ticket's trace." />
    <div className="panel pad flow-panel"><div className="flow">{FLOW.map((f, i) => <span key={f} className="flow-step"><b>{f}</b>{i < FLOW.length - 1 && <ArrowRight size={14} />}</span>)}</div></div>
    {!data ? <Loading err={err} /> : <section className="agent-grid">{data.map((a, i) => (
      <div key={a.name} className={`panel agent-card ${i === 10 ? 'orchestrator' : ''}`}>
        <div className="agent-card-top"><span className="agent-num">{String(i + 1).padStart(2, '0')}</span><Bot size={18} /><span className="live-dot" /></div>
        <h2>{a.name}</h2><p>{a.role}</p>
        <small>{a.actions_24h} actions in the last 24h</small>
      </div>))}</section>}
    <div className="panel department-note"><LocateFixed size={18} /><span><strong>Hybrid intelligence.</strong> The Groq LLM (text + vision) handles language and photo understanding; deterministic, auditable agents own routing, SLA, escalation and verification so every civic decision is explainable. If the LLM is unavailable, a rules engine takes over seamlessly.</span></div>
  </>
}
