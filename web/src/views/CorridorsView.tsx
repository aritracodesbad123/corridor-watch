import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { ExplorerEntity, ExplorerGraph, type NetNode, type Network } from '../components/ExplorerGraph'

type CorridorRow = {
  corridor: string
  volume?: number
  count?: number
  suspicious_count?: number
  suspicious_rate?: number
  unique_accounts?: number
  network_count?: number
  patterns?: string[]
  risk?: string
}

type AlertRow = {
  txn_id: string
  corridor?: string
  primary_pattern?: string
  ts?: string
  showcase?: string
  sender_id?: string
  receiver_id?: string
}

function money(n?: number) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`
  return `$${Math.round(v)}`
}

export function CorridorsView() {
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<CorridorRow[]>([])
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [network, setNetwork] = useState<Network | null>(null)
  const [selected, setSelected] = useState<NetNode | null>(null)
  const [mode, setMode] = useState<'graph' | 'table'>('graph')
  const [risk, setRisk] = useState('')
  const [q, setQ] = useState(() => searchParams.get('q') || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const qq = searchParams.get('q')
    if (qq != null) setQ(qq)
  }, [searchParams])

  const filtered = useMemo(() => {
    let out = rows
    if (risk) out = out.filter((c) => (c.risk || '') === risk)
    if (q.trim()) {
      const needle = q.trim().toLowerCase()
      out = out.filter((c) =>
        `${c.corridor} ${(c.patterns || []).join(' ')}`.toLowerCase().includes(needle),
      )
    }
    return out
  }, [rows, risk, q])

  const insights = useMemo(() => {
    const high = filtered.filter((c) => c.risk === 'high').length
    const volume = filtered.reduce((s, c) => s + Number(c.volume || 0), 0)
    const networks = filtered.reduce((s, c) => s + Number(c.network_count || 0), 0)
    return { high, volume, networks, shown: filtered.length }
  }, [filtered])

  const onSelect = useCallback((node: NetNode | null, net: Network) => {
    setSelected(node)
    setNetwork(net)
  }, [])

  async function runQuery() {
    setBusy(true)
    setError('')
    try {
      const [corridorData, alertData] = await Promise.all([
        api<CorridorRow[] | { corridors?: CorridorRow[] }>('/corridors'),
        api<AlertRow[]>('/alerts?sort=newest').catch(() => [] as AlertRow[]),
      ])
      const list = Array.isArray(corridorData)
        ? corridorData
        : Array.isArray(corridorData?.corridors)
          ? corridorData.corridors
          : []
      setRows(list)
      setAlerts(Array.isArray(alertData) ? alertData : [])

      const needle = q.trim().toLowerCase()
      let hero = 'CW-MID-02'
      const hit = (Array.isArray(alertData) ? alertData : []).find(
        (a) =>
          a.txn_id.toLowerCase() === needle ||
          (a.sender_id || '').toLowerCase() === needle ||
          (a.receiver_id || '').toLowerCase() === needle,
      )
      const mid = (Array.isArray(alertData) ? alertData : []).find((a) => a.showcase === 'middle_bank')
      const show = (Array.isArray(alertData) ? alertData : []).find((a) => a.showcase)
      if (hit) hero = hit.txn_id
      else if (mid) hero = mid.txn_id
      else if (show) hero = show.txn_id

      const net = await api<Network>(`/alerts/${encodeURIComponent(hero)}/network`)
      setNetwork({ ...net, hero_txn_id: hero })
      setSelected(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void runQuery()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const recent = alerts.slice(0, 6)

  return (
    <div>
      <div className="page-head">
        <h2>Corridor Explorer</h2>
        <p>
          Explore connections, uncover hidden flows, and investigate suspicious activity across the
          financial corridor.
        </p>
      </div>

      <div className="explorer-filters">
        <select
          aria-label="Filter by risk level"
          value={risk}
          onChange={(e) => setRisk(e.target.value)}
        >
          <option value="">All risk levels</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <input
          type="text"
          placeholder="Search entity, account, or corridor"
          aria-label="Search entity, account, or corridor"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void runQuery()
          }}
        />
        <button type="button" className="btn" disabled={busy} onClick={() => void runQuery()}>
          {busy ? 'Running…' : 'Run query'}
        </button>
      </div>

      {error && (
        <p className="error" style={{ padding: '0 24px' }}>
          {error}
        </p>
      )}

      <div className="explorer-grid">
        <div className="card graph-card">
          <div className="graph-toolbar">
            <div>
              <b>Entity network graph</b>
              <div className="muted">
                Visualize relationships and trace money flow, device links, and common attributes.
              </div>
            </div>
            <div className="seg">
              <button
                type="button"
                className={mode === 'graph' ? 'on' : ''}
                onClick={() => setMode('graph')}
              >
                Graph
              </button>
              <button
                type="button"
                className={mode === 'table' ? 'on' : ''}
                onClick={() => setMode('table')}
              >
                Table
              </button>
            </div>
          </div>

          {mode === 'graph' ? (
            <ExplorerGraph network={network} onSelect={onSelect} />
          ) : (
            <div style={{ overflow: 'auto' }}>
              <table className="wide-table">
                <thead>
                  <tr>
                    <th>Corridor</th>
                    <th>Volume</th>
                    <th>Count</th>
                    <th>Suspicious</th>
                    <th>Accounts</th>
                    <th>Networks</th>
                    <th>Patterns</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.corridor}>
                      <td className="row-corridor">{c.corridor}</td>
                      <td>{money(c.volume)}</td>
                      <td>{c.count ?? '—'}</td>
                      <td>
                        {c.suspicious_count ?? 0} ({Math.round((c.suspicious_rate || 0) * 100)}%)
                      </td>
                      <td>{c.unique_accounts ?? '—'}</td>
                      <td>{c.network_count ?? '—'}</td>
                      <td>{(c.patterns || []).join(', ') || '—'}</td>
                      <td>{c.risk || '—'}</td>
                    </tr>
                  ))}
                  {!filtered.length && (
                    <tr>
                      <td colSpan={8} className="muted">
                        No corridor data.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          <div className="viz-legend" style={{ marginTop: 10 }}>
            <span>
              <i style={{ background: '#3B82F6' }} /> Account
            </span>
            <span>
              <i style={{ background: '#F59E0B' }} /> Transaction
            </span>
            <span>
              <i style={{ background: '#8B5CF6' }} /> Location
            </span>
            <span>
              <i style={{ background: '#EF4444' }} /> Risk
            </span>
            <span>
              <i style={{ background: '#C4A36A' }} /> External intel
            </span>
            <span>
              <i style={{ background: '#94A3B8' }} /> Unknown hop
            </span>
          </div>
        </div>

        <div className="card">
          <ExplorerEntity node={selected} network={network} />
        </div>
      </div>

      <div className="explorer-bottom">
        <div className="card">
          <h3>Quick insights</h3>
          <div className="stats" style={{ padding: 0, gridTemplateColumns: '1fr 1fr' }}>
            <div className="stat">
              <div className="l">High-risk corridors</div>
              <div className="n">{insights.high}</div>
            </div>
            <div className="stat">
              <div className="l">Networks</div>
              <div className="n">{insights.networks}</div>
            </div>
            <div className="stat">
              <div className="l">Measured volume</div>
              <div className="n">{money(insights.volume)}</div>
            </div>
            <div className="stat">
              <div className="l">Corridors shown</div>
              <div className="n">{insights.shown}</div>
            </div>
          </div>
        </div>
        <div className="card">
          <h3>Recent activity</h3>
          <ul className="activity">
            {recent.map((a) => (
              <li key={a.txn_id}>
                <span>
                  {a.txn_id} · {a.corridor}
                </span>
                <span>{a.primary_pattern || ''}</span>
              </li>
            ))}
            {!recent.length && <li className="muted">No recent alerts</li>}
          </ul>
        </div>
        <div className="card">
          <h3>Investigation timeline</h3>
          <ul className="activity">
            {recent.map((a) => (
              <li key={`t-${a.txn_id}`}>
                <span>{(a.ts || '').replace('T', ' ').slice(0, 16)}</span>
                <span>{a.txn_id}</span>
              </li>
            ))}
            {!recent.length && <li className="muted">No timeline yet</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}
