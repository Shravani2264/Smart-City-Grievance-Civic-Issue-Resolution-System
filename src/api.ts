export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type SlaState = 'on_track' | 'at_risk' | 'breached' | 'met' | 'breached_resolved'

export type TraceStep = { step: number; agent: string; output: Record<string, unknown>; reasoning: string; mode: string; ms: number }
export type HistoryItem = { status: string; at: number; actor: string; note: string }
export type Escalation = { level: number; role: string; target: string; reason: string; at: number }
export type CivicEvent = { id: number; at: number; agent: string; complaint_id: string | null; level: string; message: string }

export type Complaint = {
  id: string; created_at: number; text: string; location_text: string; citizen_name: string; citizen_id: string; has_image: number
  issue_type: string; issue_label: string; category: string; title: string; lat: number; lng: number; ward: number; ward_name: string
  sector: number | null; landmark: string | null; dept: string; department: string; unit: string; severity_score: number; priority: Priority
  sla_hours: number; due_at: number; status: string; escalation_level: number; cluster_id: string | null; is_primary: number
  resolved_at: number | null; closed_at: number | null; feedback_rating: number | null; reopen_count: number; ai_mode: string
  duration_days: number; color: string; signals: string[]; cluster_size: number
  sla: { state: SlaState; remaining_h: number | null; elapsed_frac: number | null }
}

export type ComplaintDetail = Complaint & {
  urgency_signals: Record<string, string[]>
  severity_factors: { factors: { factor: string; points: number }[]; trend: string; routing: Record<string, unknown> & { notify: string[]; supervisor: string; district_officer: string; jurisdiction: string; division: string }; duplicate: Record<string, unknown> }
  location_meta: { zone: string; municipality: string; geo_confidence: number; method: string; needs_field_verification: boolean }
  escalations: Escalation[]; history: HistoryItem[]; trace: TraceStep[]; allowed_next: string[]
  verification: { status: string; window_until?: number; checks?: Record<string, string>; verified_by?: string; failed_reason?: string } | null
  image_analysis: { findings: string } | null
  sla_start: number; lead_id?: string
  cluster?: { id: string; count: number; title: string; status: string }
  cluster_members?: { id: string; created_at: number; citizen_name: string; text: string; is_primary: number }[]
  citizen?: { name: string; reputation: number; reports: number; verified: number; rejected: number; helpful: number }
  events?: CivicEvent[]
}

export type DeptPerf = { code: string; name: string; short: string; color: string; score: number; sla_compliance: number; open: number; overdue: number; total: number; resolved: number; avg_resolution_h?: number | null; escalations?: number; speed?: number; backlog_health?: number; satisfaction?: number }

export type Dashboard = {
  now: number
  kpis: { open: number; open_reports: number; at_risk: number; breached: number; reported_today: number; resolved_today: number; avg_resolution_h: number | null; sla_met_pct: number | null; escalated_open: number; critical_open: number; duplicates_merged_7d: number }
  queue: Complaint[]
  categories: { category: string; count: number; color: string }[]
  departments: DeptPerf[]
  hot_ward: { ward: number; name: string; open: number }
  clusters: { id: string; count: number; title: string; ward: number; status: string; last_at: number; primary_id: string }[]
  events: CivicEvent[]
}

export type MapData = {
  bounds: { lat_min: number; lat_max: number; lng_min: number; lng_max: number; cols: number; rows: number }
  wards: { ward: number; name: string; code: string; row: number; col: number; pop: number; open: number; recent: number; efficiency: number | null; overdue: number; top_issue: string | null }[]
  points: { id: string; lat: number; lng: number; category: string; color: string; status: string; priority: Priority; title: string; open: boolean; ward: number }[]
  categories: string[]
}

export type Report = {
  city: string; period_days: number; generated_at: number; total_complaints: number; unique_incidents: number; duplicates_merged: number
  resolved: number; closed_verified: number; open: number; reopened: number; resolution_rate: number; avg_resolution_h: number | null
  median_resolution_h: number | null; prev_avg_resolution_h: number | null; sla_compliance: number | null; escalations: number
  satisfaction: number | null; city_efficiency: number | null
  top_issues: { category: string; count: number; color: string; resolved: number }[]
  departments: DeptPerf[]
  wards: { ward: number; name: string; score: number | null; total: number; open: number; overdue: number; top_issue: string | null; sla_compliance?: number }[]
  daily: { day: number; reported: number; resolved: number }[]
  narrative?: string; narrative_mode?: string
}

export type Prediction = {
  rain_mm_hr: number; hours: number
  waterlogging: { ward: number; name: string; risk: number; level: string; drivers: string[]; action: string }[]
  hotspots: { ward: number; name: string; category: string; last_72h: number; expected: number; surge: number; projection_7d: number }[]
}

export type Health = { ok: boolean; clock: number; clock_offset_hours: number; agents: number; ai: { enabled: boolean; provider: string; model: string | null; vision_model: string | null; reason: string | null } }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not JSON */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/health'),
  dashboard: () => request<Dashboard>('/dashboard'),
  complaints: (params: Record<string, string | number>) => request<Complaint[]>(`/complaints?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== 0).map(([k, v]) => [k, String(v)]))}`),
  complaint: (id: string) => request<ComplaintDetail>(`/complaints/${id}`),
  create: (form: FormData) => request<ComplaintDetail>('/complaints', { method: 'POST', body: form }),
  setStatus: (id: string, status: string, note = '') => post<ComplaintDetail>(`/complaints/${id}/status`, { status, note }),
  feedback: (id: string, rating: number, comment = '') => post<{ message: string; complaint: ComplaintDetail }>(`/complaints/${id}/feedback`, { rating, comment }),
  map: (category = '') => request<MapData>(`/map?days=14${category ? `&category=${encodeURIComponent(category)}` : ''}`),
  escalations: () => request<{ tickets: (Complaint & { escalations: Escalation[] })[]; feed: CivicEvent[]; ladder_30d: Record<string, number> }>('/escalations'),
  report: (days: number, narrative = false) => request<Report>(`/report?days=${days}&narrative=${narrative}`),
  predict: (rain?: number) => request<Prediction>(`/predict${rain !== undefined ? `?rain=${rain}` : ''}`),
  citizens: () => request<{ top: Citizen[]; flagged: Citizen[]; total: number }>('/citizens'),
  agents: () => request<{ name: string; role: string; actions_24h: number }[]>('/agents'),
  advance: (hours: number) => post<{ progressed: number; escalations: number; verified_closed: number; reopened: number }>('/sim/advance', { hours }),
  setRain: (mm: number) => post<{ rain_mm_hr: number }>('/sim/rain', { hours: mm }),
  reset: () => post<{ seeded: number }>('/sim/reset', {}),
}

export type Citizen = { id: string; name: string; reputation: number; reports: number; verified: number; rejected: number; helpful: number }

// ---------- formatting ----------
export function ago(ts: number, now: number) {
  const s = Math.max(0, now - ts)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

export function clock(ts: number) {
  return new Date(ts * 1000).toLocaleString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function slaText(c: Pick<Complaint, 'sla' | 'status'>) {
  if (c.sla.state === 'met') return 'Met'
  if (c.sla.state === 'breached_resolved') return 'Late'
  const h = c.sla.remaining_h ?? 0
  if (h < 0) return `${fmtDur(-h)} overdue`
  return `${fmtDur(h)} left`
}

export function fmtDur(h: number) {
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}m`
  if (h < 48) return `${Math.floor(h)}h ${Math.round((h % 1) * 60)}m`
  return `${Math.round(h / 24)}d`
}

export const titleCase = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
