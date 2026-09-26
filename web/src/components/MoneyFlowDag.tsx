import { useMemo, useState } from 'react'

type FlowNode = {
  id: string
  layer?: number
  focus?: boolean
  risk_score?: number
  country?: string
  visibility?: string
  external?: boolean
  [key: string]: unknown
}

type FlowEdge = {
  source: string
  target: string
  amount?: number
  highlight?: boolean
}

type Props = {
  network: {
    flow_dag?: { nodes?: FlowNode[]; edges?: FlowEdge[] }
    nodes?: FlowNode[]
    edges?: FlowEdge[]
  } | null
}

export type MoneyFlowNetwork = NonNullable<Props['network']>

function money(n?: number) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`
  return `$${Math.round(v)}`
}

function tipRows(n: FlowNode) {
  const shown = new Set(['id', 'country', 'risk_score', 'focus', 'external', 'layer'])
  const rows: [string, string][] = [
    ['country', String(n.country || '—')],
    ['risk score', n.risk_score != null ? String(n.risk_score) : '—'],
    [
      'role',
      n.focus ? 'focal account' : n.external ? 'external counterparty' : 'related account',
    ],
  ]
  if (n.layer !== undefined) rows.push(['hop depth', String(n.layer)])
  Object.keys(n).forEach((k) => {
    if (shown.has(k)) return
    const v = n[k]
    if (v === null || v === undefined || typeof v === 'object') return
    rows.push([k.replace(/_/g, ' '), String(v)])
  })
  return rows
}

export function MoneyFlowDag({ network }: Props) {
  const [tip, setTip] = useState<{ title: string; rows: [string, string][]; x: number; y: number } | null>(
    null,
  )

  const svg = useMemo(() => {
    const dag = network?.flow_dag || network
    const nodes = [...(dag?.nodes || [])]
    const edges = dag?.edges || []
    if (!nodes.length) {
      return null
    }

    const W = 920
    const H = 340
    const padX = 70
    const padY = 36
    const maxLayer = Math.max(...nodes.map((n) => n.layer || 0), 1)
    const byLayer: Record<number, FlowNode[]> = {}
    nodes.forEach((n) => {
      const L = n.layer || 0
      ;(byLayer[L] ||= []).push(n)
    })
    Object.values(byLayer).forEach((arr) =>
      arr.sort((a, b) => Number(b.focus) - Number(a.focus) || (b.risk_score || 0) - (a.risk_score || 0)),
    )

    const positions: Record<string, { x: number; y: number; n: FlowNode }> = {}
    Object.entries(byLayer).forEach(([L, arr]) => {
      const layer = Number(L)
      const x = padX + (layer / maxLayer) * (W - padX * 2)
      arr.forEach((n, i) => {
        const y = arr.length === 1 ? H / 2 : padY + (i / (arr.length - 1)) * (H - padY * 2)
        positions[n.id] = { x, y, n }
      })
    })

    return { W, H, byLayer, maxLayer, padX, positions, edges, nodes }
  }, [network])

  if (!svg) {
    return <div className="muted" style={{ padding: 24 }}>No flow graph for this case.</div>
  }

  const { W, H, byLayer, maxLayer, padX, positions, edges, nodes } = svg

  return (
    <div className="net tall" style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Money movement network">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="#7A879C" />
          </marker>
          <marker id="arrow-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="#E0A04A" />
          </marker>
        </defs>
        {Object.keys(byLayer).map((L) => {
          const x = padX + (Number(L) / maxLayer) * (W - padX * 2)
          return (
            <text key={L} x={x} y={16} textAnchor="middle" fill="#6B778A" fontSize={10} fontFamily="IBM Plex Mono">
              hop {L}
            </text>
          )
        })}
        {edges.map((e, i) => {
          const a = positions[e.source]
          const b = positions[e.target]
          if (!a || !b) return null
          const dx = b.x - a.x
          const dy = b.y - a.y
          const len = Math.hypot(dx, dy) || 1
          const shrink = 18
          const x1 = a.x + (dx / len) * shrink
          const y1 = a.y + (dy / len) * shrink
          const x2 = b.x - (dx / len) * shrink
          const y2 = b.y - (dy / len) * shrink
          const midX = (x1 + x2) / 2
          const midY = (y1 + y2) / 2 - (e.highlight ? 10 : 4)
          const stroke = e.highlight ? '#E0A04A' : '#4A5870'
          const sw = e.highlight
            ? Math.min(5, 1.5 + Math.log10((e.amount || 1) + 1))
            : Math.min(3.5, 1 + Math.log10((e.amount || 1) + 1) * 0.7)
          return (
            <g key={i}>
              <path
                d={`M${x1} ${y1} Q ${midX} ${midY} ${x2} ${y2}`}
                fill="none"
                stroke={stroke}
                strokeWidth={sw}
                markerEnd={`url(#${e.highlight ? 'arrow-hi' : 'arrow'})`}
                className={e.highlight ? 'edge-flow-hi' : 'edge-flow'}
                opacity={e.highlight ? 1 : 0.75}
              />
              <text className="flow-label" x={midX} y={midY - 6} textAnchor="middle">
                {money(e.amount)}
              </text>
            </g>
          )
        })}
        {nodes.map((n) => {
          const p = positions[n.id]
          if (!p) return null
          const risk = n.risk_score || 0
          const vis = n.visibility || (n.external ? 'external' : 'observed')
          const fill = n.focus
            ? '#3FA796'
            : vis === 'external'
              ? '#3A4E6A'
              : vis === 'inferred'
                ? '#5A4A2A'
                : vis === 'unknown'
                  ? '#2A2A2A'
                  : risk >= 70
                    ? '#8B3E32'
                    : '#2F3F55'
          const stroke = n.focus ? '#7EE0D0' : vis === 'unknown' || vis === 'inferred' ? '#C4A36A' : '#6A7A90'
          const dash = vis === 'unknown' || vis === 'inferred' ? '4 3' : undefined
          return (
            <g
              key={n.id}
              className="flow-node"
              onMouseEnter={(e) => {
                const pad = 16
                let x = e.clientX + pad
                let y = e.clientY + pad
                if (x > window.innerWidth - 280) x = e.clientX - pad - 260
                if (y > window.innerHeight - 160) y = e.clientY - pad - 120
                setTip({ title: n.id || 'Account', rows: tipRows(n), x, y })
              }}
              onMouseMove={(e) => {
                const pad = 16
                let x = e.clientX + pad
                let y = e.clientY + pad
                if (x > window.innerWidth - 280) x = e.clientX - pad - 260
                if (y > window.innerHeight - 160) y = e.clientY - pad - 120
                setTip((t) => (t ? { ...t, x, y } : t))
              }}
              onMouseLeave={() => setTip(null)}
            >
              <rect
                x={p.x - 34}
                y={p.y - 18}
                rx={6}
                width={68}
                height={36}
                fill={fill}
                stroke={stroke}
                strokeWidth={1.5}
                strokeDasharray={dash}
              />
              <text x={p.x} y={p.y - 2} textAnchor="middle" fill="#E8ECF1" fontSize={10} fontFamily="IBM Plex Mono">
                {(n.id || '').slice(0, 8)}
              </text>
              <text x={p.x} y={p.y + 12} textAnchor="middle" fill="#A8B2C2" fontSize={9} fontFamily="IBM Plex Mono">
                {n.country || '?'} · {Math.round(risk)}
              </text>
            </g>
          )
        })}
      </svg>
      {tip && (
        <div className="node-tooltip" style={{ left: tip.x, top: tip.y, display: 'block' }}>
          <div className="tt-title">{tip.title}</div>
          {tip.rows.map(([k, v]) => (
            <div className="tt-row" key={k}>
              <span>{k}</span>
              <span>{v}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
