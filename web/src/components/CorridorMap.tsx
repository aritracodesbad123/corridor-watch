import { geoMercator, geoPath } from 'd3-geo'
import { useEffect, useMemo, useRef, useState } from 'react'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'

type Country = {
  country: string
  label?: string
  lon: number
  lat: number
  focus?: boolean
  in_amount?: number
  out_amount?: number
}

type Flow = {
  source: string
  target: string
  source_lon: number
  source_lat: number
  target_lon: number
  target_lat: number
  amount?: number
  count?: number
  highlight?: boolean
}

export type Geo = {
  countries?: Country[]
  flows?: Flow[]
}

const WORLD_ATLAS_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'
let cachedFeatures: GeoJSON.Feature[] | null = null

async function getWorldFeatures(): Promise<GeoJSON.Feature[]> {
  if (cachedFeatures) return cachedFeatures
  const topo = (await (await fetch(WORLD_ATLAS_URL)).json()) as Topology
  const obj = topo.objects.countries
  const fc = feature(topo, obj as never) as unknown as GeoJSON.FeatureCollection
  cachedFeatures = fc.features
  return cachedFeatures
}

function money(n?: number) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`
  return `$${Math.round(v)}`
}

export function CorridorMap({ geo }: { geo: Geo | null | undefined }) {
  const [features, setFeatures] = useState<GeoJSON.Feature[] | null>(null)
  const [err, setErr] = useState('')
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const drag = useRef<{ x: number; y: number } | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    getWorldFeatures()
      .then((f) => {
        if (!cancelled) setFeatures(f)
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : 'Map unavailable')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const W = 920
  const H = 360
  const projection = useMemo(() => {
    const frame = {
      type: 'Polygon' as const,
      coordinates: [
        [
          [-120, -15],
          [150, -15],
          [150, 50],
          [-120, 50],
          [-120, -15],
        ],
      ],
    }
    return geoMercator().fitExtent(
      [
        [24, 24],
        [W - 24, H - 24],
      ],
      frame as GeoJSON.Polygon,
    )
  }, [])

  const pathGen = useMemo(() => geoPath(projection), [projection])

  const countries = geo?.countries || []
  const flows = geo?.flows || []
  const maxAmt = Math.max(...flows.map((f) => f.amount || 0), 1)

  function resetView() {
    setScale(1)
    setPan({ x: 0, y: 0 })
  }

  return (
    <div className="map-stage">
      <div className="map-zoom-bar">
        <button
          type="button"
          className="map-zoom-btn"
          onClick={() => setScale((s) => Math.min(4, s * 1.25))}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          type="button"
          className="map-zoom-btn"
          onClick={() => setScale((s) => Math.max(0.6, s / 1.25))}
          aria-label="Zoom out"
        >
          −
        </button>
        <button type="button" className="map-zoom-btn" onClick={resetView} aria-label="Reset zoom">
          reset
        </button>
      </div>
      <div
        className="net tall"
        ref={wrapRef}
        onWheel={(e) => {
          e.preventDefault()
          setScale((s) => (e.deltaY < 0 ? Math.min(4, s * 1.1) : Math.max(0.6, s / 1.1)))
        }}
        onPointerDown={(e) => {
          if (e.button !== 0) return
          drag.current = { x: e.clientX, y: e.clientY }
          ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
        }}
        onPointerMove={(e) => {
          if (!drag.current) return
          const dx = e.clientX - drag.current.x
          const dy = e.clientY - drag.current.y
          drag.current = { x: e.clientX, y: e.clientY }
          setPan((p) => ({ x: p.x + dx, y: p.y + dy }))
        }}
        onPointerUp={() => {
          drag.current = null
        }}
      >
        {err && <div className="muted" style={{ padding: 24 }}>Map failed: {err}</div>}
        {!err && !features && <div className="muted" style={{ padding: 24 }}>Loading map…</div>}
        {features && (
          <svg
            viewBox={`0 0 ${W} ${H}`}
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
              transformOrigin: 'center center',
            }}
            role="img"
            aria-label="Corridor geography world map"
          >
            <rect className="map-ocean" width={W} height={H} />
            {features.map((f, i) => {
              const d = pathGen(f as GeoJSON.Feature)
              return d ? <path key={i} className="map-land" d={d} /> : null
            })}
            {flows.map((f, i) => {
              const a = projection([f.source_lon, f.source_lat])
              const b = projection([f.target_lon, f.target_lat])
              if (!a || !b) return null
              const mx = (a[0] + b[0]) / 2
              const my =
                Math.min(a[1], b[1]) - 30 - (f.highlight ? 20 : 0) - Math.abs(a[0] - b[0]) * 0.08
              const sw = 1.2 + 4 * ((f.amount || 0) / maxAmt)
              const col = f.highlight ? '#E0A04A' : '#3FA796'
              return (
                <g key={`f-${i}`}>
                  <path
                    d={`M${a[0]} ${a[1]} Q ${mx} ${my} ${b[0]} ${b[1]}`}
                    fill="none"
                    stroke={col}
                    strokeWidth={sw}
                    opacity={0.9}
                    className={f.highlight ? 'edge-flow-hi' : 'edge-flow'}
                  />
                  <text className="flow-label" x={mx} y={my + 4} textAnchor="middle">
                    {f.source}→{f.target} {money(f.amount)}
                  </text>
                </g>
              )
            })}
            {countries.map((c, i) => {
              const p = projection([c.lon, c.lat])
              if (!p) return null
              const r = c.focus ? 9 : 6
              const fill = c.focus ? '#E0A04A' : '#3FA796'
              return (
                <g key={`c-${i}`}>
                  <circle cx={p[0]} cy={p[1]} r={r + 4} fill={fill} opacity={0.2} />
                  <circle cx={p[0]} cy={p[1]} r={r} fill={fill} stroke="#0F1419" strokeWidth={1.5} />
                  <text
                    x={p[0]}
                    y={p[1] - 12}
                    textAnchor="middle"
                    fill="#0F172A"
                    fontSize={11}
                    fontFamily="IBM Plex Mono"
                    fontWeight={600}
                  >
                    {c.country}
                  </text>
                  <text x={p[0]} y={p[1] + 22} textAnchor="middle" fill="#64748B" fontSize={9} fontFamily="IBM Plex Mono">
                    {c.label}
                  </text>
                </g>
              )
            })}
            {!countries.length && (
              <text x={W / 2} y={H / 2} textAnchor="middle" fill="#8B95A8">
                No corridor geography for this case
              </text>
            )}
          </svg>
        )}
      </div>
      <div className="viz-legend">
        <span>
          <i style={{ background: '#E0A04A' }} /> country on focal path
        </span>
        <span>
          <i style={{ background: '#3FA796' }} /> related corridor country
        </span>
        <span>arc width ∝ volume · drag to pan · wheel to zoom</span>
      </div>
    </div>
  )
}

export function geoSummary(geo: Geo | null | undefined) {
  const flows = [...(geo?.flows || [])].sort((a, b) => (b.amount || 0) - (a.amount || 0))
  if (!flows.length) return <div className="muted">No cross-border arcs in neighborhood.</div>
  return (
    <>
      {flows.slice(0, 6).map((f, i) => (
        <div className="kv" key={i}>
          <span>
            {f.source} → {f.target} · {f.count ?? 0} txns
          </span>
          <span>{money(f.amount)}</span>
        </div>
      ))}
    </>
  )
}
