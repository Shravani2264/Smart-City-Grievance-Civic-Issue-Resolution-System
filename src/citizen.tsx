import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Activity, ArrowRight, CheckCircle2, ClipboardList, LocateFixed, LogIn, MapPin, Search, Shield, Sparkles, Star, TicketCheck, X,
} from 'lucide-react'
import { api, clock, slaText, type ComplaintDetail, type Report } from './api'
import { priorityClass, SlaBadge, catHex } from './charts'
import { IntakeModal } from './intake'

/* -------------------------------------------------------------------------- *
 * Citizen Portal — the public-facing front end.
 * Separate from the staff/admin control center: citizens can report an issue,
 * track a complaint by its ID, rate a resolution, and see public city stats.
 * No simulation clock, agent traces, escalation management or reputation here.
 * -------------------------------------------------------------------------- */

function StatusBig({ c }: { c: ComplaintDetail }) {
  const open = !['Closed', 'Rejected'].includes(c.status)
  return <div className={`cz-status-chip s-${c.status.toLowerCase().replace(' ', '-')}`}>
    {open ? <Activity size={15} /> : <CheckCircle2 size={15} />}{c.status}
  </div>
}

function FeedbackStars({ c, onDone }: { c: ComplaintDetail; onDone: (msg: string) => void }) {
  const [hover, setHover] = useState(0)
  const [rating, setRating] = useState(c.feedback_rating ?? 0)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(c.feedback_rating != null)

  async function send(r: number) {
    setBusy(true)
    try {
      const res = await api.feedback(c.id, r, comment)
      setSent(true)
      onDone(res.message || (res.complaint.status === 'Reopened' ? 'Thanks — we have reopened your complaint.' : 'Thanks for confirming the fix!'))
    } catch (e) { onDone((e as Error).message) } finally { setBusy(false) }
  }

  if (sent) return <div className="cz-feedback done"><CheckCircle2 size={16} />Thank you — your rating was recorded.</div>
  return <div className="cz-feedback">
    <strong>Was this actually resolved? Rate the fix:</strong>
    <div className="cz-stars" role="radiogroup" aria-label="Rate the resolution">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" aria-label={`${n} star${n > 1 ? 's' : ''}`} disabled={busy}
          onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)} onClick={() => setRating(n)}
          className={(hover || rating) >= n ? 'on' : ''}><Star size={26} /></button>
      ))}
    </div>
    <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={300}
      placeholder="Optional: tell us what's still wrong (a low rating reopens the complaint)" />
    <button className="primary-button" disabled={busy || rating === 0} onClick={() => send(rating)}>
      {busy ? 'Sending…' : 'Submit rating'}</button>
  </div>
}

function TrackCard({ c, onToast }: { c: ComplaintDetail; onToast: (m: string) => void }) {
  const resolved = c.status === 'Resolved'
  const stages = ['Reported', 'Assigned', 'In Progress', 'Inspection', 'Resolved', 'Closed']
  const reached = new Set(c.history.map((h) => h.status))
  const activeIdx = Math.max(0, stages.findIndex((s) => s === c.status))
  return <div className="cz-track-card panel">
    <div className="cz-track-top">
      <div><span className="eyebrow">{c.id}{c.cluster_id ? ` · part of incident ${c.cluster_id}` : ''}</span>
        <h3>{c.title}</h3>
        <p className="cz-track-loc"><MapPin size={14} />Ward {c.ward} · {c.ward_name}{c.landmark ? ` · ${c.landmark}` : ''}</p>
      </div>
      <StatusBig c={c} />
    </div>

    <div className="cz-progress">
      {stages.map((s, i) => {
        const done = reached.has(s) || i < activeIdx
        const active = s === c.status
        return <div key={s} className={`cz-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
          <span className="cz-dot">{done && !active ? <CheckCircle2 size={14} /> : i + 1}</span>
          <small>{s}</small>
        </div>
      })}
    </div>

    <div className="cz-track-meta">
      <div><span>HANDLED BY</span><strong>{c.department}</strong></div>
      <div><span>PRIORITY</span><strong><span className={priorityClass(c.priority)}>{c.priority}</span></strong></div>
      <div><span>SERVICE TARGET</span><strong>{c.sla_hours}h · <SlaBadge state={c.sla.state} text={slaText(c)} /></strong></div>
      <div><span>FILED</span><strong>{clock(c.created_at)}</strong></div>
    </div>

    <details className="cz-timeline-wrap"><summary>Full timeline ({c.history.length} updates)</summary>
      <ol className="cz-timeline">{[...c.history].reverse().map((h, i) => <li key={i}>
        <span className="cz-tl-dot" /><div><strong>{h.status}</strong><small>{clock(h.at)} · {h.actor}</small>{h.note && <p>{h.note}</p>}</div>
      </li>)}</ol>
    </details>

    {resolved && <FeedbackStars c={c} onDone={onToast} />}
  </div>
}

function PublicStats() {
  const [r, setR] = useState<Report | null>(null)
  useEffect(() => { api.report(30).then(setR).catch(() => {}) }, [])
  if (!r) return null
  const tiles = [
    { label: 'Complaints this month', value: r.total_complaints },
    { label: 'Resolution rate', value: `${Math.round(r.resolution_rate)}%` },
    { label: 'Avg. resolution time', value: r.avg_resolution_h ? `${Math.round(r.avg_resolution_h)}h` : '—' },
    { label: 'On-time (SLA)', value: r.sla_compliance != null ? `${Math.round(r.sla_compliance)}%` : '—' },
  ]
  return <section className="cz-stats">
    <div className="cz-stats-head"><Shield size={16} /><span>Public accountability · last 30 days · {r.city}</span></div>
    <div className="cz-stats-grid">
      {tiles.map((t) => <div key={t.label} className="cz-stat"><strong>{t.value}</strong><small>{t.label}</small></div>)}
    </div>
    {r.top_issues?.length > 0 && <div className="cz-topissues">
      <span className="eyebrow">MOST REPORTED</span>
      <div>{r.top_issues.slice(0, 5).map((t) => <span key={t.category} className="cz-issue-chip">
        <i style={{ background: catHex(t.category) }} />{t.category}<em>{t.count}</em></span>)}</div>
    </div>}
  </section>
}

export function CitizenPortal({ aiEnabled, onSwitchToAdmin }: { aiEnabled: boolean; onSwitchToAdmin: () => void }) {
  const [showIntake, setShowIntake] = useState(false)
  const [trackId, setTrackId] = useState('')
  const [tracked, setTracked] = useState<ComplaintDetail | null>(null)
  const [trackErr, setTrackErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => { if (!toast) return; const t = window.setTimeout(() => setToast(''), 4200); return () => window.clearTimeout(t) }, [toast])

  const track = useCallback(async (id: string) => {
    const clean = id.trim().toUpperCase()
    if (!clean) return
    setBusy(true); setTrackErr('')
    try { setTracked(await api.complaint(clean)) }
    catch { setTrackErr(`No complaint found with ID "${clean}". Check the ID from your submission receipt.`); setTracked(null) }
    finally { setBusy(false) }
  }, [])

  async function onTrackSubmit(e: FormEvent) { e.preventDefault(); track(trackId) }

  return <div className="cz-portal">
    <header className="cz-header">
      <div className="cz-brand">
        <span className="brand-mark"><Activity size={20} strokeWidth={2.5} /></span>
        <div><strong>Mumbai Grievance Portal</strong><small>Brihanmumbai Municipal Corporation · Citizen services</small></div>
      </div>
      <button className="cz-staff-link" onClick={onSwitchToAdmin}><LogIn size={15} />Staff / Admin login</button>
    </header>

    <main className="cz-main">
      <section className="cz-hero">
        <span className="eyebrow"><Sparkles size={14} /> AI-POWERED CIVIC RESOLUTION</span>
        <h1>Report a civic issue in Mumbai</h1>
        <p>Potholes, garbage, water, drainage, streetlights, dangerous wires and more. Describe it in your own words — our system classifies, locates, prioritises and routes it to the right BMC department automatically.</p>
        <div className="cz-hero-actions">
          <button className="primary-button lg" onClick={() => setShowIntake(true)}><TicketCheck size={18} />Report an issue</button>
          <a className="outline-button lg" href="#track" onClick={(e) => { e.preventDefault(); document.getElementById('track')?.scrollIntoView({ behavior: 'smooth' }) }}><Search size={16} />Track my complaint</a>
        </div>
      </section>

      <PublicStats />

      <section className="cz-track-section" id="track">
        <div className="cz-section-head"><ClipboardList size={18} /><h2>Track your complaint</h2></div>
        <p className="cz-section-sub">Enter the complaint ID you received when you submitted (looks like <code>CMP-00123</code>).</p>
        <form className="cz-track-form" onSubmit={onTrackSubmit}>
          <span className="input-with-icon"><LocateFixed size={16} />
            <input value={trackId} onChange={(e) => setTrackId(e.target.value)} placeholder="CMP-00123" aria-label="Complaint ID" /></span>
          <button className="primary-button" disabled={busy || !trackId.trim()}>{busy ? 'Looking…' : 'Track'}<ArrowRight size={15} /></button>
        </form>
        {trackErr && <div className="error-banner">{trackErr}</div>}
        {tracked && <TrackCard c={tracked} onToast={(m) => { setToast(m); track(tracked.id) }} />}
      </section>

      <section className="cz-how">
        <div className="cz-section-head"><Sparkles size={18} /><h2>How it works</h2></div>
        <div className="cz-how-grid">
          {[
            { t: 'You describe it', d: 'Plain language or a photo. No forms, no categories to pick.' },
            { t: 'AI agents triage it', d: '11 agents classify, geotag, prioritise, deduplicate and route it in seconds.' },
            { t: 'The right team acts', d: 'It goes to the owning BMC department with a service deadline attached.' },
            { t: 'You confirm the fix', d: 'Rate the resolution — a low rating reopens it until it is actually done.' },
          ].map((s, i) => <div key={s.t} className="cz-how-card"><span className="cz-how-num">{i + 1}</span><strong>{s.t}</strong><p>{s.d}</p></div>)}
        </div>
      </section>
    </main>

    <footer className="cz-footer">
      <span>CivicPulse · built for Mumbai (BMC)</span>
      <button className="cz-staff-link ghost" onClick={onSwitchToAdmin}><Shield size={14} />Open staff control center</button>
    </footer>

    {showIntake && <IntakeModal aiEnabled={aiEnabled} onClose={() => setShowIntake(false)}
      onOpen={(id) => { setShowIntake(false); setTrackId(id); track(id); document.getElementById('track')?.scrollIntoView({ behavior: 'smooth' }) }}
      onCreated={() => {}} />}
    {toast && <div className="toast" role="status"><CheckCircle2 size={17} />{toast}<button aria-label="Dismiss" onClick={() => setToast('')}><X size={15} /></button></div>}
  </div>
}
