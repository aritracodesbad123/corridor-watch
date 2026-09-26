import {
  forceCenter,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationNodeDatum,
} from 'd3-force'
import { select } from 'd3-selection'
import { zoom, zoomIdentity } from 'd3-zoom'
import { useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

type NetNode = {
  id: string
  name?: string
  kind?: string
  country?: string
  risk_score?: number
  focus?: boolean
  visibility?: string
  external?: boolean
  pattern?: string
  x?: number
  y?: number
}

type NetEdge = {
  source: string | NetNode
  target: string | NetNode
  amount?: number
  corridor?: string
  highlight?: boolean
}

type Network = {
  nodes?: NetNode[]
  edges?: NetEdge[]
  hero_txn_id?: string
}

function color(d: NetNode) {
  if (d.visibility === 'unknown' || d.kind === 'unknown_entity') return '#94A3B8'
  if (d.visibility === 'external') return '#C4A36A'
  if (d.kind === 'location') return '#8B5CF6'
  if (Number(d.risk_score || 0) >= 80 || d.focus) return '#EF4444'
  return '#3B82F6'
}

export function ExplorerGraph({
  network,
  onSelect,
}: {
  network: Network | null
  onSelect: (node: NetNode | null, net: Network) => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomRef = useRef<ReturnType<typeof zoom<SVGSVGElement, unknown>> | null>(null)

  const prepared = useMemo(() => {
    if (!network) return null
    const nodes: (NetNode & SimulationNodeDatum)[] = (network.nodes || []).map((n) => ({ ...n }))
    const idset = new Set(nodes.map((n) => n.id))
    ;(network.nodes || []).forEach((n) => {
      if (!n.country || n.country === '??') return
      const lid = `LOC-${n.country}`
      if (!idset.has(lid)) {
        nodes.push({ id: lid, name: n.country, kind: 'location', country: n.country, risk_score: 0 })
        idset.add(lid)
      }
    })
    const links: NetEdge[] = (network.edges || []).map((e) => ({
      source: e.source,
      target: e.target,
      amount: e.amount,
      corridor: e.corridor,
      highlight: e.highlight,
    }))
    ;(network.nodes || []).forEach((n) => {
      if (n.country && n.country !== '??') {
        links.push({ source: n.id, target: `LOC-${n.country}`, amount: 0 })
      }
    })
    return { nodes, links, hero: network.hero_txn_id, raw: network }
  }, [network])

  useEffect(() => {
    if (!prepared || !wrapRef.current || !svgRef.current) return
    const el = wrapRef.current
    const W = el.clientWidth || 640
    const H = el.clientHeight || 360
    const svg = select(svgRef.current)
    svg.selectAll('*').remove()
    svg.attr('viewBox', `0 0 ${W} ${H}`)
    const root = svg.append('g')
    const nodes = prepared.nodes
    const links = prepared.links.map((l) => ({ ...l }))

    const sim = forceSimulation(nodes)
      .force(
        'link',
        forceLink(links as { source: string; target: string }[])
          .id((d) => (d as NetNode).id)
          .distance(90),
      )
      .force('charge', forceManyBody().strength(-180))
      .force('center', forceCenter(W / 2, H / 2))

    const link = root
      .append('g')
      .attr('stroke', '#CBD5E1')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke-width', (d) => (d.highlight ? 2.2 : 1))
      .attr('stroke', (d) => (d.highlight ? '#F59E0B' : '#CBD5E1'))

    const node = root
      .append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .style('cursor', 'pointer')
      .on('click', (_, d) => onSelect(d, prepared.raw))

    node
      .append('circle')
      .attr('r', (d) => (d.focus ? 14 : 9))
      .attr('fill', (d) => color(d))
    node
      .append('text')
      .text((d) => d.id)
      .attr('x', 12)
      .attr('y', 4)
      .attr('fill', '#334155')
      .attr('font-size', 10)

    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.4, 4])
      .on('zoom', (ev) => root.attr('transform', ev.transform.toString()))
    svg.call(z)
    zoomRef.current = z

    sim.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as NetNode).x || 0)
        .attr('y1', (d) => (d.source as NetNode).y || 0)
        .attr('x2', (d) => (d.target as NetNode).x || 0)
        .attr('y2', (d) => (d.target as NetNode).y || 0)
      node.attr('transform', (d) => `translate(${d.x || 0},${d.y || 0})`)
    })

    const focus = nodes.find((n) => n.focus) || nodes[0] || null
    onSelect(focus, prepared.raw)

    return () => {
      sim.stop()
    }
  }, [prepared, onSelect])

  function scaleBy(factor: number) {
    if (!svgRef.current || !zoomRef.current) return
    select(svgRef.current).call(zoomRef.current.scaleBy, factor)
  }
  function resetZoom() {
    if (!svgRef.current || !zoomRef.current) return
    select(svgRef.current).call(zoomRef.current.transform, zoomIdentity)
  }

  return (
    <div>
      <div className="map-zoom-bar" style={{ position: 'static', marginBottom: 8 }}>
        <button type="button" className="map-zoom-btn" onClick={() => scaleBy(1.25)} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="map-zoom-btn" onClick={() => scaleBy(0.8)} aria-label="Zoom out">
          −
        </button>
        <button type="button" className="map-zoom-btn" onClick={resetZoom} aria-label="Reset zoom">
          reset
        </button>
      </div>
      <div id="explorer-graph" ref={wrapRef} className="explorer-graph">
        {!network && <div className="muted" style={{ padding: 24 }}>Loading graph…</div>}
        <svg ref={svgRef} width="100%" height="100%" />
      </div>
    </div>
  )
}

export function ExplorerEntity({
  node,
  network,
}: {
  node: NetNode | null
  network: Network | null
}) {
  const navigate = useNavigate()
  if (!node) {
    return <div className="muted">Select a node to inspect an account, location, or risk signal.</div>
  }
  const links = (network?.edges || []).filter((e) => {
    const s = typeof e.source === 'string' ? e.source : e.source.id
    const t = typeof e.target === 'string' ? e.target : e.target.id
    return s === node.id || t === node.id
  })
  const score = Number(node.risk_score || 0)
  const pill = score >= 80 ? 'high' : score >= 50 ? 'medium' : 'low'
  return (
    <div>
      <div className="kv">
        <span>{node.id}</span>
        <span className={`pill ${pill}`}>{node.kind || 'account'}</span>
      </div>
      <div className="muted" style={{ margin: '6px 0 10px' }}>
        {node.name || node.country || ''}
      </div>
      <div className="entity-k">
        <span>Account / entity</span>
        <span>{node.id}</span>
      </div>
      <div className="entity-k">
        <span>Country</span>
        <span>{node.country || '—'}</span>
      </div>
      <div className="entity-k">
        <span>Risk score</span>
        <span>{score || '—'} / 100</span>
      </div>
      <div className="entity-k">
        <span>Connections</span>
        <span>{links.length}</span>
      </div>
      <div className="entity-k">
        <span>Pattern</span>
        <span>{node.pattern || '—'}</span>
      </div>
      <h3 style={{ marginTop: 14 }}>Key indicators</h3>
      {node.focus && <div className="ind">Focal account on this corridor network</div>}
      {node.visibility && (
        <div className="ind">
          Visibility: {node.visibility}
          {node.visibility === 'unknown' ? ' — unresolved hop, not an accusation' : ''}
        </div>
      )}
      {node.external && <div className="ind">External / unregistered counterparty</div>}
      {score >= 75 && <div className="ind">High-risk score on this entity</div>}
      {network?.hero_txn_id && (
        <button
          type="button"
          className="btn"
          style={{ width: '100%', marginTop: 14 }}
          onClick={() => navigate(`/investigate/${network.hero_txn_id}`)}
        >
          View full investigation →
        </button>
      )}
    </div>
  )
}

export type { NetNode, Network }
