import { useCallback, useEffect, useState } from 'react'
import {
  Activity, AlertOctagon, BarChart3, Bell, Bot, Building2, ChevronRight, CloudRain, FastForward, Map, Menu, RotateCcw, Search, Sparkles,
  TicketCheck, X, CheckCircle2, Users,
} from 'lucide-react'
import { api, clock, type Dashboard, type Health } from './api'
import { AgentsView, ComplaintsView, DepartmentsView, EscalationsView, InsightsView, MapView, Overview, TransparencyView } from './views'
import { DetailDrawer } from './drawer'
import { IntakeModal } from './intake'
import { CitizenPortal } from './citizen'

const NAV = [
  { label: 'Overview', icon: Activity },
  { label: 'Complaints', icon: TicketCheck },
  { label: 'City map', icon: Map },
  { label: 'Escalations', icon: AlertOctagon },
  { label: 'Departments', icon: Building2 },
  { label: 'Insights', icon: CloudRain },
  { label: 'Transparency', icon: BarChart3 },
  { label: 'Agents', icon: Bot },
]

type Role = 'admin' | 'citizen'

export default function App() {
  const roleFromHash = (): Role => {
    const h = window.location.hash
    if (h.startsWith('#citizen')) return 'citizen'
    if (h && h !== '#') return 'admin' // a deep link to any control-center view
    return (localStorage.getItem('civic-role') as Role) || 'citizen'
  }
  const [role, setRoleState] = useState<Role>(roleFromHash)
  const setRole = useCallback((r: Role) => {
    setRoleState(r)
    try { localStorage.setItem('civic-role', r) } catch { /* private mode */ }
    window.location.hash = r === 'citizen' ? '#citizen' : '#overview'
  }, [])

  const fromHash = () => NAV.find((n) => `#${n.label.toLowerCase().replace(' ', '-')}` === window.location.hash.split('/')[0])?.label ?? 'Overview'
  const [view, setViewState] = useState(fromHash)
  const setView = useCallback((v: string) => { setViewState(v); window.history.replaceState(null, '', `#${v.toLowerCase().replace(' ', '-')}`) }, [])
  const [health, setHealth] = useState<Health | null>(null)
  const [dash, setDash] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(() => window.location.hash.split('/')[1] ?? null)
  const [showIntake, setShowIntake] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [toast, setToast] = useState('')
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0) // bump to refresh every view

  const refresh = useCallback(async () => {
    try {
      const [h, d] = await Promise.all([api.health(), api.dashboard()])
      setHealth(h); setDash(d); setError('')
    } catch (e) {
      setError(`Cannot reach the CivicPulse API (${(e as Error).message}). Start the backend: cd backend && python -m uvicorn app.main:app --port 8000`)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh, version])
  useEffect(() => { const t = window.setInterval(() => setVersion((v) => v + 1), 10000); return () => window.clearInterval(t) }, [])
  useEffect(() => { if (!toast) return; const t = window.setTimeout(() => setToast(''), 3800); return () => window.clearTimeout(t) }, [toast])

  async function warp(hours: number) {
    setBusy(true)
    try {
      const r = await api.advance(hours)
      setToast(`Clock +${hours}h · ${r.progressed} field updates · ${r.escalations} escalations · ${r.verified_closed} verified · ${r.reopened} reopened`)
      setVersion((v) => v + 1)
    } catch (e) { setToast((e as Error).message) } finally { setBusy(false) }
  }

  async function reset() {
    setBusy(true)
    try { const r = await api.reset(); setToast(`Demo data reset · ${r.seeded} historical reports replayed through the agents`); setVersion((v) => v + 1) }
    catch (e) { setToast((e as Error).message) } finally { setBusy(false) }
  }

  const now = health?.clock ?? Date.now() / 1000
  const ai = health?.ai
  const common = { now, version, onSelect: setSelected }

  if (role === 'citizen') {
    return <CitizenPortal aiEnabled={!!ai?.enabled} onSwitchToAdmin={() => setRole('admin')} />
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" onClick={(e) => { e.preventDefault(); setView('Overview') }}>
          <span className="brand-mark"><Activity size={20} strokeWidth={2.5} /></span>
          <span className="brand-name">civic<span>pulse</span><small>URBAN OPERATIONS</small></span>
        </a>
        <div className="city-switcher"><span className="city-avatar">M</span><span><strong>Mumbai</strong><small>BMC (MCGM) · 24 wards</small></span></div>
        <button className="role-switch" onClick={() => setRole('citizen')}><Users size={15} />Citizen portal<ChevronRight size={14} /></button>
        <div className="nav-caption">CONTROL CENTER</div>
        <nav aria-label="Main navigation">
          {NAV.map(({ label, icon: Icon }) => (
            <button key={label} className={`nav-link ${view === label ? 'active' : ''}`} onClick={() => { setView(label); setMobileNav(false) }}>
              <Icon size={18} strokeWidth={1.9} /><span>{label}</span>
              {label === 'Complaints' && dash && <span className="nav-count">{dash.kpis.open}</span>}
              {label === 'Escalations' && dash && dash.kpis.breached > 0 && <span className="nav-count hot">{dash.kpis.breached}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="service-card">
          <span className="service-icon"><Sparkles size={17} /></span>
          <div><strong>{health?.agents ?? 11} agents online</strong><small>{ai?.enabled ? `Groq · ${ai.model}` : 'Rules engine (offline mode)'}</small></div>
          <span className="live-dot" />
          <small className="service-foot">{ai?.enabled ? `Vision: ${ai.vision_model?.split('/').pop()}` : 'Set GROQ_API_KEY to enable the LLM'}</small>
        </div>
        <div className="sim-card">
          <span className="eyebrow">SIMULATION CLOCK</span>
          <strong>{clock(now)}</strong>
          {health && health.clock_offset_hours > 0 && <small>+{health.clock_offset_hours}h ahead of real time</small>}
          <div className="sim-buttons">
            <button disabled={busy} onClick={() => warp(6)}><FastForward size={13} />6h</button>
            <button disabled={busy} onClick={() => warp(24)}><FastForward size={13} />24h</button>
            <button disabled={busy} onClick={reset} title="Reset demo data"><RotateCcw size={13} /></button>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(!mobileNav)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>Mumbai</span><ChevronRight size={14} /><strong>{view}</strong></div>
          <label className="global-search"><Search size={16} /><input value={search} onChange={(e) => { setSearch(e.target.value); if (view !== 'Complaints') setView('Complaints') }} placeholder="Search tickets, incidents, places..." /></label>
          <button className="icon-button notification-button" aria-label="Alerts" onClick={() => setView('Escalations')}><Bell size={18} />{dash && dash.kpis.breached > 0 && <i />}</button>
          <button className="primary-button" onClick={() => setShowIntake(true)}><Sparkles size={15} />Report issue</button>
        </header>

        <div className="content-wrap">
          {error && <div className="error-banner">{error}</div>}
          {view === 'Overview' && <Overview dash={dash} {...common} onNavigate={setView} onNew={() => setShowIntake(true)} />}
          {view === 'Complaints' && <ComplaintsView {...common} search={search} />}
          {view === 'City map' && <MapView {...common} />}
          {view === 'Escalations' && <EscalationsView {...common} />}
          {view === 'Departments' && <DepartmentsView {...common} />}
          {view === 'Insights' && <InsightsView {...common} onToast={setToast} />}
          {view === 'Transparency' && <TransparencyView {...common} aiEnabled={!!ai?.enabled} />}
          {view === 'Agents' && <AgentsView {...common} />}
        </div>
      </main>

      {mobileNav && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      {selected && <DetailDrawer id={selected} now={now} onClose={() => setSelected(null)} onChanged={(msg) => { setToast(msg); setVersion((v) => v + 1) }} onSelect={setSelected} />}
      {showIntake && <IntakeModal aiEnabled={!!ai?.enabled} onClose={() => setShowIntake(false)} onOpen={(id) => { setShowIntake(false); setSelected(id); setVersion((v) => v + 1) }} onCreated={() => setVersion((v) => v + 1)} />}
      {toast && <div className="toast" role="status"><CheckCircle2 size={17} />{toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={15} /></button></div>}
    </div>
  )
}
