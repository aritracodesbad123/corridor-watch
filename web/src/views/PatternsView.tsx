import { useEffect, useState } from 'react'
import { api } from '../api'

type Axis = { axis: string; count?: number }

type Pattern = {
  pattern_id?: string
  name?: string
  description?: string
  version?: number
  match_count?: number
  confirmed_cases?: number
  signal_count?: number
  avg_match_score?: number
  graph_signature?: string
  temporal_signature?: string
  axes?: Axis[]
  family?: string
  summary?: string
}

export function PatternsView() {
  const [rows, setRows] = useState<Pattern[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    void api<Pattern[] | { patterns?: Pattern[] }>('/patterns')
      .then((data) => {
        if (Array.isArray(data)) setRows(data)
        else if (data && Array.isArray(data.patterns)) setRows(data.patterns)
        else setRows([])
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed'))
  }, [])

  return (
    <div>
      <div className="page-head">
        <h2>Crime Pattern DNA library</h2>
        <p>
          This is institutional memory: confirmed investigations become reusable fingerprints, not a
          one-off alert. Coverage and match scores are measured from the ledger.
        </p>
      </div>
      {error && (
        <p className="error" style={{ padding: '0 22px' }}>
          {error}
        </p>
      )}
      <div className="dna-grid">
        {rows.map((p, i) => {
          const score =
            p.avg_match_score == null ? '—' : `${Math.round(p.avg_match_score * 100)}%`
          return (
            <div className="card" key={String(p.pattern_id || p.name || i)}>
              <div className="kv">
                <span className="mono">
                  {p.pattern_id || p.name || `DNA-${i + 1}`}
                  {p.version != null ? ` · v${p.version}` : ''}
                </span>
                <span>
                  {p.match_count ?? 0} matches · {p.confirmed_cases ?? 0} confirmed
                </span>
              </div>
              <b>{p.name || p.pattern_id}</b>
              <p className="muted">{p.description || p.summary || ''}</p>
              {(p.axes || []).map((a) => (
                <div key={a.axis}>
                  <div className="dna-axis">
                    <span>{a.axis}</span>
                    <span>{a.count ?? 0}</span>
                  </div>
                  <div className="bar">
                    <i style={{ width: `${Math.min(100, (a.count || 0) * 18)}%` }} />
                  </div>
                </div>
              ))}
              <div className="kv">
                <span>signals</span>
                <span>{p.signal_count ?? 0}</span>
              </div>
              <div className="kv">
                <span>avg match</span>
                <span>{score}</span>
              </div>
              <div className="muted">
                graph {p.graph_signature || '—'} · time {p.temporal_signature || '—'}
              </div>
            </div>
          )
        })}
        {!rows.length && !error && (
          <p className="muted" style={{ padding: 22 }}>
            Library empty or still seeding.
          </p>
        )}
      </div>
    </div>
  )
}
