import { useMemo, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Clock3, XCircle } from 'lucide-react'
import type { Complaint, MapData, SlaState } from './api'

/* Validated categorical palette (fixed order, CVD-checked). Minor categories fold into "Other". */
export const CATEGORY_HEX: Record<string, string> = {
  'Water Supply': '#2a78d6',
  'Roads & Infrastructure': '#eb6834',
  'Solid Waste Management': '#1baf7a',
  'Electricity & Lighting': '#eda100',
  'Public Health': '#e87ba4',
  'Drainage & Sewerage': '#4a3aa7',
}
export const OTHER_HEX = '#8a8984'
export const catHex = (c: string) => CATEGORY_HEX[c] ?? OTHER_HEX
export const catLegend = [...Object.keys(CATEGORY_HEX), 'Other']

const STATUS: Record<string, { color: string; label: string; icon: ReactNode }> = {
  on_track: { color: '#0a8a0a', label: 'On track', icon: <CheckCircle2 size={12} /> },
  at_risk: { color: '#b07800', label: 'At risk', icon: <AlertTriangle size={12} /> },
  breached: { color: '#d03b3b', label: 'Breached', icon: <XCircle size={12} /> },
  met: { color: '#0a8a0a', label: 'SLA met', icon: <CheckCircle2 size={12} /> },
  breached_resolved: { color: '#c05a2a', label: 'Resolved late', icon: <Clock3 size={12} /> },
}

export function SlaBadge({ state, text }: { state: SlaState; text?: string }) {
  const s = STATUS[state]
  return <span className="sla-badge" style={{ color: s.color }}>{s.icon}{text ?? s.label}</span>
}

/* Sequential blue ramp (light -> dark) for magnitude */
const BLUE = ['#eef4fc', '#cde2fb', '#a9ccf5', '#86b6ef', '#5f9eea', '#3987e5', '#2a6fc4', '#1c5cab']
export function seqBlue(t: number) {
  return BLUE[Math.max(0, Math.min(BLUE.length - 1, Math.round(t * (BLUE.length - 1))))]
}

export function BarList({ rows, max, unit = '' }: { rows: { label: string; value: number; color: string; note?: string }[]; max?: number; unit?: string }) {
  const m = max ?? Math.max(1, ...rows.map((r) => r.value))
  return <div className="barlist">{rows.map((r) => (
    <div className="barlist-row" key={r.label} title={`${r.label}: ${r.value}${unit}${r.note ? ` · ${r.note}` : ''}`}>
      <span className="barlist-label"><i style={{ background: r.color }} />{r.label}</span>
      <span className="barlist-track"><span style={{ width: `${Math.max(2, (r.value / m) * 100)}%`, background: r.color }} /></span>
      <strong>{r.value.toLocaleString()}{unit}</strong>
    </div>
  ))}</div>
}

export function Meter({ value, label }: { value: number | null; label?: string }) {
  const v = value ?? 0
  const tone = v >= 80 ? '#0a8a0a' : v >= 65 ? '#b07800' : '#d03b3b'
  return <div className="meter" title={`${label ?? 'Score'}: ${v}/100`}><span style={{ width: `${v}%`, background: tone }} /></div>
}

export function TrendChart({ data }: { data: { day: number; reported: number; resolved: number }[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const ref = useRef<SVGSVGElement>(null)
  const W = 640, H = 200, P = { l: 34, r: 12, t: 12, b: 24 }
  const max = Math.max(4, ...data.map((d) => Math.max(d.reported, d.resolved)))
  const nice = Math.ceil(max / 10) * 10
  const x = (i: number) => P.l + (i / Math.max(1, data.length - 1)) * (W - P.l - P.r)
  const y = (v: number) => H - P.b - (v / nice) * (H - P.t - P.b)
  const path = (k: 'reported' | 'resolved') => data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d[k]).toFixed(1)}`).join('')
  const ticks = [0, nice / 2, nice]
  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    setHover(Math.max(0, Math.min(data.length - 1, Math.round(((px - P.l) / (W - P.l - P.r)) * (data.length - 1)))))
  }
  const h = hover !== null ? data[hover] : null
  const fmt = (ts: number) => new Date(ts * 1000).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  return <div className="trend-wrap">
    <div className="chart-legend"><span><i style={{ background: '#2a78d6' }} />Reported</span><span><i style={{ background: '#1baf7a' }} />Resolved</span></div>
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="trend-svg" onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="Daily complaints reported and resolved">
      {ticks.map((t) => <g key={t}><line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} className="grid" /><text x={P.l - 6} y={y(t) + 3} className="axis" textAnchor="end">{t}</text></g>)}
      {data.map((d, i) => i % Math.ceil(data.length / 6) === 0 && <text key={d.day} x={x(i)} y={H - 6} className="axis" textAnchor="middle">{fmt(d.day)}</text>)}
      <path d={path('reported')} className="line" stroke="#2a78d6" />
      <path d={path('resolved')} className="line" stroke="#1baf7a" />
      {h && hover !== null && <g>
        <line x1={x(hover)} x2={x(hover)} y1={P.t} y2={H - P.b} className="crosshair" />
        <circle cx={x(hover)} cy={y(h.reported)} r={4} fill="#2a78d6" stroke="#fff" strokeWidth={2} />
        <circle cx={x(hover)} cy={y(h.resolved)} r={4} fill="#1baf7a" stroke="#fff" strokeWidth={2} />
      </g>}
      <rect x={P.l} y={P.t} width={W - P.l - P.r} height={H - P.t - P.b} fill="transparent" />
    </svg>
    {h && hover !== null && <div className="chart-tip" style={{ left: `${(x(hover) / W) * 100}%` }}><strong>{fmt(h.day)}</strong><span><i style={{ background: '#2a78d6' }} />Reported {h.reported}</span><span><i style={{ background: '#1baf7a' }} />Resolved {h.resolved}</span></div>}
  </div>
}

/* SVG city map: ward choropleth (sequential) + complaint points (categorical) */
export function CityMap({ data, mode, onSelect, showPoints = true, highlight }: {
  data: MapData; mode: 'open' | 'efficiency' | 'risk'; onSelect?: (id: string) => void; showPoints?: boolean
  highlight?: Record<number, number>
}) {
  const [tip, setTip] = useState<{ x: number; y: number; body: ReactNode } | null>(null)
  const { bounds: b } = data
  const W = 800, H = 500
  const cw = W / b.cols, ch = H / b.rows
  const px = (lng: number) => ((lng - b.lng_min) / (b.lng_max - b.lng_min)) * W
  const py = (lat: number) => ((b.lat_max - lat) / (b.lat_max - b.lat_min)) * H
  const maxOpen = Math.max(1, ...data.wards.map((w) => w.open))
  const value = (w: MapData['wards'][number]) => mode === 'open' ? w.open / maxOpen : mode === 'efficiency' ? ((w.efficiency ?? 50) - 50) / 50 : (highlight?.[w.ward] ?? 0) / 100
  const pts = useMemo(() => [...data.points].sort((a, c) => Number(a.open) - Number(c.open)), [data.points])
  return <div className="citymap">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Ward map of Mumbai with complaint locations" onMouseLeave={() => setTip(null)}>
      {data.wards.map((w) => <g key={w.ward}>
        <rect x={w.col * cw + 2} y={w.row * ch + 2} width={cw - 4} height={ch - 4} rx={8} fill={seqBlue(value(w))} className="ward-cell"
          onMouseMove={(e) => setTip({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, body: <><strong>Ward {w.code || w.ward} · {w.name}</strong><span>{w.open} open · {w.overdue} overdue</span><span>Efficiency {w.efficiency ?? '—'}/100</span>{mode === 'risk' && <span>Waterlogging risk {highlight?.[w.ward] ?? 0}/100</span>}{w.top_issue && <span>Top issue: {w.top_issue}</span>}</> })} />
      </g>)}
      <path d={`M0,${H * 0.47} C${W * 0.2},${H * 0.4} ${W * 0.3},${H * 0.62} ${W * 0.5},${H * 0.55} S${W * 0.8},${H * 0.15} ${W},${H * 0.12}`} className="river" />
      {showPoints && pts.map((p) => <circle key={p.id} cx={px(p.lng)} cy={py(p.lat)} r={p.open ? (p.priority === 'CRITICAL' ? 10 : 8) : 5}
        fill={catHex(p.category)} fillOpacity={p.open ? 1 : 0.45} stroke="#fff" strokeWidth={2} className="map-dot"
        onClick={() => onSelect?.(p.id)}
        onMouseMove={(e) => { e.stopPropagation(); setTip({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, body: <><strong>{p.id} · {p.title}</strong><span>{p.category}</span><span>{p.status} · {p.priority}</span></> }) }} />)}
      {data.wards.map((w) => <g key={`l${w.ward}`} className={value(w) > 0.6 ? 'on-dark' : ''}>
        <text x={w.col * cw + 12} y={w.row * ch + 28} className="ward-label">{w.code || `W${w.ward}`} {w.name}</text>
        <text x={w.col * cw + 12} y={w.row * ch + 48} className="ward-sub">{mode === 'open' ? `${w.open} open` : mode === 'efficiency' ? `Efficiency ${w.efficiency ?? '—'}` : `Risk ${highlight?.[w.ward] ?? 0}`}</text>
      </g>)}
    </svg>
    {tip && <div className="map-tip" style={{ left: tip.x + 14, top: tip.y + 10 }}>{tip.body}</div>}
    <div className="map-legend2">
      {showPoints && catLegend.map((c) => <span key={c}><i style={{ background: c === 'Other' ? OTHER_HEX : CATEGORY_HEX[c] }} />{c}</span>)}
      <span className="ramp-legend"><em>{mode === 'open' ? 'Fewer open' : mode === 'efficiency' ? 'Lower efficiency' : 'Lower risk'}</em><b style={{ background: `linear-gradient(90deg, ${BLUE.join(',')})` }} /><em>{mode === 'open' ? 'More open' : mode === 'efficiency' ? 'Higher' : 'Higher'}</em></span>
    </div>
  </div>
}

export function priorityClass(p: Complaint['priority']) { return `priority-pill ${p.toLowerCase()}` }
