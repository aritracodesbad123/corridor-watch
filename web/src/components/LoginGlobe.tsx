import { geoContains, geoGraticule10, geoOrthographic, geoPath, type GeoProjection } from 'd3-geo'
import { createPortal } from 'react-dom'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { feature } from 'topojson-client'
import type { Topology } from 'topojson-specification'

const WORLD = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'
const NAMES = 'https://cdn.jsdelivr.net/gh/lukes/ISO-3166-Countries-with-Regional-Codes@master/all/all.json'
const W = 640
const H = 640

const HUBS: [string, number, number, number][] = [
  ['New York', -74.01, 40.71, -12],
  ['London', -0.13, 51.51, -14],
  ['Frankfurt', 8.68, 50.11, 14],
  ['Zurich', 8.54, 47.37, -12],
  ['Dubai', 55.27, 25.2, -12],
  ['Mumbai', 72.88, 19.08, 14],
  ['Singapore', 103.85, 1.29, 14],
  ['Hong Kong', 114.17, 22.32, -12],
  ['Shanghai', 121.47, 31.23, 14],
  ['Tokyo', 139.69, 35.68, -12],
  ['Sydney', 151.21, -33.87, 14],
  ['Sao Paulo', -46.63, -23.55, 14],
]

const LINKS: [number, number][] = [
  [0, 1],
  [1, 2],
  [2, 3],
  [1, 4],
  [4, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [7, 9],
  [8, 9],
  [6, 10],
  [0, 11],
  [0, 7],
  [4, 6],
  [1, 6],
]

type NamedFeature = GeoJSON.Feature & { properties: { name: string } }

export function LoginGlobe({ reduced }: { reduced: boolean }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const sphereRef = useRef<SVGPathElement>(null)
  const gratRef = useRef<SVGPathElement>(null)
  const landRef = useRef<SVGGElement>(null)
  const arcRef = useRef<SVGGElement>(null)
  const nodeRef = useRef<SVGGElement>(null)
  const projRef = useRef<GeoProjection | null>(null)
  const featuresRef = useRef<NamedFeature[]>([])
  const hoverRef = useRef(false)
  const [tip, setTip] = useState<{ name: string; x: number; y: number } | null>(null)

  useEffect(() => {
    let dead = false
    let raf = 0
    let lon = -28
    const projection = geoOrthographic().scale(268).translate([W / 2, H / 2]).clipAngle(90).precision(0.4)
    projRef.current = projection
    const path = geoPath(projection)
    const sphere = { type: 'Sphere' } as const

    function paint() {
      projection.rotate([lon, -18, 12])
      if (sphereRef.current) sphereRef.current.setAttribute('d', path(sphere) || '')
      if (gratRef.current) gratRef.current.setAttribute('d', path(geoGraticule10()) || '')
      const lands = landRef.current?.children
      featuresRef.current.forEach((f, i) => {
        lands?.[i]?.setAttribute('d', path(f) || '')
      })
      const arcs = arcRef.current?.children
      LINKS.forEach(([a, b], i) => {
        const line = {
          type: 'LineString' as const,
          coordinates: [
            [HUBS[a][1], HUBS[a][2]],
            [HUBS[b][1], HUBS[b][2]],
          ],
        }
        arcs?.[i]?.setAttribute('d', path(line) || '')
      })
      const nodes = nodeRef.current?.children
      HUBS.forEach((h, i) => {
        const p = projection([h[1], h[2]])
        const g = nodes?.[i] as SVGGElement | undefined
        if (!g) return
        if (!p) {
          g.setAttribute('display', 'none')
          return
        }
        g.setAttribute('display', '')
        g.setAttribute('transform', `translate(${p[0].toFixed(1)} ${p[1].toFixed(1)})`)
      })
    }

    function tick() {
      if (!hoverRef.current) lon = (lon + 0.28) % 360
      paint()
      raf = requestAnimationFrame(tick)
    }

    void (async () => {
      const [topo, codes] = await Promise.all([
        fetch(WORLD).then((r) => r.json()) as Promise<Topology>,
        fetch(NAMES).then((r) => r.json()) as Promise<Array<{ name: string; 'country-code': string }>>,
      ])
      if (dead) return
      const byId = new Map(codes.map((c) => [String(Number(c['country-code'])), c.name]))
      const fc = feature(topo, topo.objects.countries as never) as unknown as GeoJSON.FeatureCollection
      const feats = fc.features.map((f) => ({
        ...f,
        properties: { name: byId.get(String(f.id ?? '')) || '' },
      })) as NamedFeature[]
      featuresRef.current = feats
      const land = landRef.current
      if (land) {
        land.replaceChildren()
        feats.forEach((f) => {
          const el = document.createElementNS('http://www.w3.org/2000/svg', 'path')
          el.setAttribute('class', 'login-land')
          el.dataset.name = f.properties.name
          land.appendChild(el)
        })
      }
      const arcs = arcRef.current
      if (arcs) {
        arcs.replaceChildren()
        LINKS.forEach(() => {
          const el = document.createElementNS('http://www.w3.org/2000/svg', 'path')
          el.setAttribute('class', 'login-arc')
          arcs.appendChild(el)
        })
      }
      const nodes = nodeRef.current
      if (nodes) {
        nodes.replaceChildren()
        HUBS.forEach((h) => {
          const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
          const halo = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
          halo.setAttribute('r', '7')
          halo.setAttribute('class', 'login-hub-halo')
          const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
          dot.setAttribute('r', '2.6')
          dot.setAttribute('class', 'login-hub')
          const label = document.createElementNS('http://www.w3.org/2000/svg', 'text')
          label.setAttribute('class', 'login-hub-label')
          label.setAttribute('y', String(h[3]))
          label.textContent = h[0]
          g.append(halo, dot, label)
          nodes.appendChild(g)
        })
      }
      paint()
      if (!reduced) raf = requestAnimationFrame(tick)
    })()

    return () => {
      dead = true
      if (raf) cancelAnimationFrame(raf)
    }
  }, [reduced])

  function onPointerMove(e: ReactPointerEvent<SVGSVGElement>) {
    const projection = projRef.current
    const svg = svgRef.current
    if (!projection || !svg) return
    const ctm = svg.getScreenCTM()
    if (!ctm) return
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const loc = pt.matrixTransform(ctm.inverse())
    const ll = projection.invert?.([loc.x, loc.y])
    const lands = landRef.current?.children
    let hit: NamedFeature | null = null
    if (ll && Number.isFinite(ll[0]) && Number.isFinite(ll[1])) {
      hit = featuresRef.current.find((f) => geoContains(f, ll)) || null
    }
    featuresRef.current.forEach((f, i) => {
      lands?.[i]?.classList.toggle('on', f === hit)
    })
    if (hit?.properties.name) {
      hoverRef.current = true
      setTip({ name: hit.properties.name, x: e.clientX + 14, y: e.clientY + 14 })
    } else {
      hoverRef.current = false
      setTip(null)
    }
  }

  function onPointerLeave() {
    hoverRef.current = false
    setTip(null)
    landRef.current?.querySelectorAll('.on').forEach((el) => el.classList.remove('on'))
  }

  return (
    <>
      <svg
        ref={svgRef}
        className="login-globe"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Rotating world globe. Hover a country to see its name."
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
      >
        <defs>
          <radialGradient id="cw-ocean" cx="38%" cy="36%" r="70%">
            <stop offset="0%" stopColor="#16325c" />
            <stop offset="70%" stopColor="#0b1b33" />
            <stop offset="100%" stopColor="#050b18" />
          </radialGradient>
          <filter id="arc-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path ref={sphereRef} className="login-sphere" />
        <path ref={gratRef} className="login-grat" />
        <g ref={landRef} />
        <g ref={arcRef} filter="url(#arc-glow)" />
        <g ref={nodeRef} />
      </svg>
      {tip &&
        createPortal(
          <div className="login-country-tip" style={{ left: tip.x, top: tip.y }}>
            {tip.name}
          </div>,
          document.body,
        )}
    </>
  )
}
