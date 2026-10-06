import { useEffect, useState, type FormEvent } from 'react'
import { ArrowUpRight, Camera, CheckCircle2, ChevronRight, LocateFixed, Sparkles, X } from 'lucide-react'
import { api, type ComplaintDetail } from './api'
import { priorityClass } from './charts'

const SAMPLES = [
  { text: 'Garbage not collected in my street for 5 days near Dharavi.', loc: '' },
  { text: 'Open manhole on the road right outside the school gate, children walk here every morning', loc: 'near Dadar station' },
  { text: 'Water leaking from the pipeline near Sion hospital, clean water flowing across the road', loc: 'Sion' },
  { text: 'Live wire hanging from the pole and sparking since the rain last night', loc: 'Andheri West' },
  { text: 'Park bench broken in the garden', loc: 'Juhu beach' },
]

export function IntakeModal({ aiEnabled, onClose, onOpen, onCreated }: { aiEnabled: boolean; onClose: () => void; onOpen: (id: string) => void; onCreated: () => void }) {
  const [text, setText] = useState('')
  const [loc, setLoc] = useState('')
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState<ComplaintDetail | null>(null)
  const [shown, setShown] = useState(0)

  useEffect(() => {
    if (!result || shown >= result.trace.length) return
    const t = window.setTimeout(() => setShown((s) => s + 1), 260)
    return () => window.clearTimeout(t)
  }, [result, shown])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setErr('')
    const f = new FormData()
    f.set('text', text); f.set('location', loc); f.set('name', name)
    if (file) f.set('image', file)
    try { const r = await api.create(f); setResult(r); setShown(0); onCreated() }
    catch (e2) { setErr((e2 as Error).message) } finally { setBusy(false) }
  }

  return <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    {!result ? <section className="intake-modal" role="dialog" aria-modal="true" aria-labelledby="intake-title">
      <div className="modal-heading"><span className="eyebrow">CITIZEN INTAKE</span><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div>
      <h2 id="intake-title">Report a city issue</h2>
      <p className="modal-description">Describe it in your own words, or attach a photo. Eleven agents will classify, geotag, prioritise, deduplicate and route it instantly.</p>
      <div className="sample-row">{SAMPLES.map((s) => <button key={s.text} type="button" onClick={() => { setText(s.text); setLoc(s.loc) }}>{s.text.slice(0, 34)}…</button>)}</div>
      <form onSubmit={submit}>
        <label className="form-label">What's happening?<textarea maxLength={800} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Garbage not collected in my street for 5 days near Sector 14" /></label>
        <label className="form-label">Where? <span className="optional-label">OPTIONAL IF IN THE TEXT</span><span className="input-with-icon"><LocateFixed size={16} /><input value={loc} onChange={(e) => setLoc(e.target.value)} placeholder="Sector, landmark, road or ward" /></span></label>
        <div className="form-split">
          <label className="form-label">Your name <span className="optional-label">OPTIONAL</span><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Citizen name" /></label>
          <label className="form-label">Photo <span className="optional-label">{aiEnabled ? 'AI VISION' : 'EVIDENCE'}</span><span className="file-input"><Camera size={15} /><span>{file ? file.name : 'Attach image'}</span><input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></span></label>
        </div>
        <div className="triage-preview"><Sparkles size={16} /><span>{aiEnabled ? 'Groq LLM + rule agents triage on submit' : 'Rule-based agents triage on submit (LLM offline)'}</span><span className="agent-mini">11 AGENTS</span></div>
        {err && <div className="error-banner">{err}</div>}
        <div className="modal-actions"><button type="button" className="outline-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={busy || (text.trim().length < 6 && !file)}><ArrowUpRight size={16} />{busy ? 'Agents working…' : 'Submit & route'}</button></div>
      </form>
    </section>
      : <section className="agent-run-modal" role="dialog" aria-modal="true" aria-labelledby="run-title">
        <div className="agent-run-head"><div><span className="agent-run-kicker"><span className="agent-run-live" /> {shown < result.trace.length ? 'AGENTS RUNNING' : 'AGENT RUN COMPLETE'} · {result.id}</span><h2 id="run-title">Your complaint is in motion</h2><p>Each agent's decision, in the order the orchestrator ran them.</p></div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div>
        <div className="agent-run-stats">
          <div><span>ISSUE</span><strong>{result.issue_label}</strong></div>
          <div><span>ROUTED TO</span><strong>{result.department}</strong></div>
          <div><span>LOCATION</span><strong>Ward {result.ward} · {result.ward_name}</strong></div>
          <div><span>SEVERITY · SLA</span><strong><span className={priorityClass(result.priority)}>{result.priority}</span> {result.severity_score}/100 · {result.sla_hours}h</strong></div>
        </div>
        <div className="agent-run-list">{result.trace.slice(0, shown).map((s) => <div className="agent-run-row" key={s.step}>
          <span className="agent-run-number">{String(s.step).padStart(2, '0')}</span><CheckCircle2 size={16} className="ok-icon" />
          <span className="agent-run-copy"><strong>{s.agent} <em>{s.mode !== 'rules' ? 'LLM' : ''}</em></strong><small>{s.reasoning}</small></span>
        </div>)}{shown < result.trace.length && <div className="agent-run-row pending"><span className="spinner" />Running {result.trace[shown].agent}…</div>}</div>
        <div className="agent-run-actions"><span>{result.cluster_id ? `Merged into incident ${result.cluster_id} (${result.cluster_size} reports)` : 'New incident opened'}</span><button className="primary-button" onClick={() => onOpen(result.id)}>Open ticket <ChevronRight size={15} /></button></div>
      </section>}
  </div>
}
