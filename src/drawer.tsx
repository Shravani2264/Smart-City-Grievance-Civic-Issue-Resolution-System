import { useEffect, useState } from 'react'
import { Building2, Check, ChevronDown, GitMerge, LocateFixed, ShieldCheck, Sparkles, Star, X } from 'lucide-react'
import { ago, api, clock, slaText, titleCase, type ComplaintDetail } from './api'
import { SlaBadge, catHex, priorityClass } from './charts'

export function DetailDrawer({ id, now, onClose, onChanged, onSelect }: { id: string; now: number; onClose: () => void; onChanged: (msg: string) => void; onSelect: (id: string) => void }) {
  const [c, setC] = useState<ComplaintDetail | null>(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState<'overview' | 'trace' | 'timeline'>('overview')
  const [next, setNext] = useState('')
  const [rating, setRating] = useState(0)

  useEffect(() => { setC(null); api.complaint(id).then(setC).catch((e) => setErr(e.message)) }, [id])
  useEffect(() => { if (c) setNext(c.allowed_next[0] ?? '') }, [c])
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onClose])

  async function move() {
    if (!c || !next) return
    try { const r = await api.setStatus(c.id, next); setC(r); onChanged(`${c.id} → ${next}${next === 'Resolved' ? ' · verification window opened' : ''}`) }
    catch (e) { setErr((e as Error).message) }
  }
  async function rate(n: number) {
    if (!c) return
    setRating(n)
    const r = await api.feedback(c.id, n, n <= 2 ? 'Issue still not fixed' : 'Confirmed fixed')
    setC(r.complaint); onChanged(`${c.id}: ${r.message}`)
  }

  return <>
    <button className="drawer-scrim" aria-label="Close complaint details" onClick={onClose} />
    <aside className="detail-drawer" role="dialog" aria-modal="true" aria-label={`Complaint ${id}`}>
      <div className="drawer-top"><span className="eyebrow">TICKET {id}</span><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div>
      {!c ? <div className="empty-state">{err || 'Loading…'}</div> : <>
        <div className="drawer-id-row"><span className="cat-chip" style={{ background: catHex(c.category) }} /><span className="ticket-id">{c.category}</span><span className="reported-time">{ago(c.created_at, now)} · {c.citizen_name} · {c.ai_mode === 'ai' ? 'LLM-assisted triage' : 'rules triage'}</span></div>
        <h2 className="drawer-title">{c.title}</h2>
        <div className="drawer-pills"><span className={priorityClass(c.priority)}>{c.priority} · {c.severity_score}/100</span><span className={`status-label s-${c.status.toLowerCase().replace(' ', '-')}`}><i />{c.status}</span><SlaBadge state={c.sla.state} text={slaText(c)} />{c.escalation_level > 0 && <span className="esc-pill">Escalated L{c.escalation_level}</span>}</div>
        <blockquote className="citizen-quote">“{c.text}”{c.location_text && <small>Location given: {c.location_text}</small>}</blockquote>
        {c.image_analysis?.findings && <div className="ai-insight"><span className="ai-insight-icon"><Sparkles size={15} /></span><div><strong>Photo analysis</strong><p>{c.image_analysis.findings}</p></div></div>}

        <div className="tabs">{(['overview', 'trace', 'timeline'] as const).map((t) => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t === 'trace' ? `Agent trace (${c.trace?.length ?? 0})` : titleCase(t)}</button>)}</div>

        {tab === 'overview' && <>
          <div className="detail-section"><h3>SEVERITY BREAKDOWN</h3>
            {c.severity_factors.factors.map((f) => <div className="factor-row" key={f.factor}><span>{f.factor}</span><strong className={f.points < 0 ? 'danger-text' : ''}>{f.points > 0 ? '+' : ''}{f.points}</strong></div>)}
            <div className="factor-row total"><span>Severity score · trend {c.severity_factors.trend}</span><strong>{c.severity_score}</strong></div>
          </div>
          <div className="detail-section"><h3>LOCATION & ROUTING</h3>
            <div className="detail-pair"><span><LocateFixed size={15} />Geotag</span><strong>Ward {c.ward_name}<small>{c.location_meta.zone} · {c.location_meta.method} · confidence {Math.round(c.location_meta.geo_confidence * 100)}%{c.location_meta.needs_field_verification ? ' · needs field check' : ''}</small></strong></div>
            <div className="detail-pair"><span><Building2 size={15} />Assigned</span><strong>{c.department}<small>{c.unit} · {c.severity_factors.routing.jurisdiction}</small></strong></div>
            {c.severity_factors.routing.notify?.length > 0 && <div className="detail-pair"><span>Also notified</span><strong>{c.severity_factors.routing.notify.join(', ')}</strong></div>}
          </div>
          <div className="sla-box"><div><span className="eyebrow">RESOLUTION SLA · {c.sla_hours}h</span><strong className={c.sla.state === 'breached' ? 'danger-text' : ''}>{slaText(c)}</strong></div>
            <small>Due {clock(c.due_at)}</small>
            <div className="esc-ladder">{[1, 2, 3].map((l) => { const e = c.escalations?.find((x) => x.level === l); const at = c.sla_start + c.sla_hours * 3600 * [0.5, 1, 1.5][l - 1]
              return <div key={l} className={`rung ${e ? 'fired' : ''}`}><b>L{l}</b><span>{e ? e.target : [c.severity_factors.routing.supervisor, c.severity_factors.routing.district_officer, c.priority === 'CRITICAL' ? 'Emergency team' : 'Commissioner'][l - 1]}</span><small>{e ? `fired ${ago(e.at, now)}` : `at ${clock(at)}`}</small></div> })}</div>
          </div>
          {c.cluster && <div className="detail-section"><h3><GitMerge size={12} /> INCIDENT {c.cluster.id} · {c.cluster.count} REPORTS</h3>
            {c.cluster_members?.slice(0, 8).map((m) => <button key={m.id} className={`member-row ${m.id === c.id ? 'me' : ''}`} onClick={() => m.id !== c.id && onSelect(m.id)}><strong>{m.id}{m.is_primary ? ' · lead' : ''}</strong><small>{m.citizen_name} · {ago(m.created_at, now)} — {m.text.slice(0, 70)}</small></button>)}
          </div>}
          {c.verification && <div className="detail-section"><h3><ShieldCheck size={12} /> RESOLUTION VERIFICATION · {c.verification.status.toUpperCase()}</h3>
            {Object.entries(c.verification.checks ?? {}).map(([k, v]) => <div className="factor-row" key={k}><span>{titleCase(k)}</span><strong>{v}</strong></div>)}
            {c.verification.verified_by && <p className="panel-note">Closed: {c.verification.verified_by}</p>}
            {c.verification.failed_reason && <p className="panel-note danger-text">Reopened: {c.verification.failed_reason}</p>}
          </div>}
          {c.citizen && <div className="detail-section"><h3>REPORTER</h3><div className="factor-row"><span>{c.citizen.name} · {c.citizen.reports} reports · {c.citizen.verified} verified{c.citizen.rejected ? ` · ${c.citizen.rejected} false` : ''}</span><strong>Reputation {Math.round(c.citizen.reputation)}</strong></div></div>}
        </>}

        {tab === 'trace' && <div className="trace-list">{c.trace?.map((s) => <div key={s.step} className="trace-step"><span className="agent-run-number">{String(s.step).padStart(2, '0')}</span>
          <div><strong>{s.agent} <em>{s.mode}{s.ms ? ` · ${s.ms} ms` : ''}</em></strong><p>{s.reasoning}</p></div></div>)}</div>}

        {tab === 'timeline' && <div className="detail-section timeline-section">{c.history.map((h, i) => <div className="timeline-item complete" key={i}><span className="timeline-marker"><Check size={11} /></span><span><strong>{h.status} <em className="muted">by {h.actor}</em></strong><small>{clock(h.at)}{h.note ? ` — ${h.note}` : ''}</small></span></div>)}
          {c.escalations?.map((e, i) => <div className="timeline-item esc" key={`e${i}`}><span className="timeline-marker">!</span><span><strong>{e.level ? `Escalated L${e.level} → ${e.target}` : e.role}</strong><small>{clock(e.at)} — {e.reason}</small></span></div>)}
        </div>}

        {err && <div className="error-banner">{err}</div>}
        <div className="drawer-actions">
          {c.status === 'Resolved' || c.status === 'Closed' ? <div className="feedback-box"><span>Citizen feedback (verification)</span><div>{[1, 2, 3, 4, 5].map((n) => <button key={n} aria-label={`${n} stars`} onClick={() => rate(n)} className={n <= (rating || c.feedback_rating || 0) ? 'on' : ''}><Star size={18} /></button>)}</div><small>1–2 stars reopens the ticket</small></div>
            : <label className="status-action-label">Move ticket to<select value={next} onChange={(e) => setNext(e.target.value)}>{c.allowed_next.map((s) => <option key={s}>{s}</option>)}</select><ChevronDown size={14} /></label>}
          {c.status !== 'Resolved' && c.status !== 'Closed' && <button className="primary-button" disabled={!next} onClick={move}>Update status</button>}
          {c.status === 'Resolved' && <button className="outline-button" onClick={() => { setNext('Reopened'); api.setStatus(c.id, 'Reopened', 'Operator reopened').then((r) => { setC(r); onChanged(`${c.id} reopened`) }) }}>Reopen</button>}
        </div>
      </>}
    </aside>
  </>
}
