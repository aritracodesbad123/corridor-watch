import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, isFiu } from '../api'
import { useAuth } from '../auth'

type Kv = Record<string, unknown>

type CommandCenter = {
  live_tps?: number
  p95_ingest_ms?: number
  pubsub_backlog?: number | string
  cloud_run_instances?: number | string
  active_investigations?: number
  database?: string
  environment?: string
  investigation_path?: string
  observability_note?: string
  light?: boolean
  ingestion?: Record<string, number>
  ingestion_latency_ms?: { p95?: number }
  suspicious_networks?: Record<string, number | string>
  workflow?: Record<string, number>
  live_stream?: Record<string, unknown>
  pubsub?: Record<string, unknown>
  network_visibility?: {
    network_visibility_pct?: number
    partial_network?: boolean
    home_institution?: string
    note?: string
    unknown?: { boundaries?: number | string }
  }
  institutions?: unknown[]
  active_corridors?: Array<{ corridor: string; suspicious_count?: number; count?: number; risk?: string }>
  slos?: Record<string, { target?: string; status?: string; p95_ms?: number; note?: string }>
  alerts?: Array<{ severity?: string; id?: string; detail?: string }>
  showcase?: {
    title?: string
    hero_txn_id?: string
    story?: string
    corridors?: string[]
    institutions?: unknown[]
  }
  middle_bank?: {
    hero_txn_id?: string
    home_institution?: string
    observed_path?: string
    unknown?: string[]
    visibility_note?: string
    story?: string
  }
  scale_evidence?: {
    measured_tps?: number | null
    status?: string
    note?: string
    primary_bottleneck?: string
  }
  scorecard?: {
    detection?: { metrics?: Record<string, unknown> }
    ingest?: Record<string, unknown>
    investigation_compression?: Record<string, unknown>
    impact?: Record<string, unknown>
    false_positives?: Record<string, unknown>
  }
  pattern_dna?: Record<string, number | string>
}

function kv(label: string, value: unknown) {
  return (
    <div className="kv">
      <span>{label}</span>
      <span>{value == null || value === '' ? '—' : String(value)}</span>
    </div>
  )
}

export function HomeView() {
  const [light, setLight] = useState<CommandCenter | null>(null)
  const [full, setFull] = useState<CommandCenter | null>(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { session } = useAuth()

  useEffect(() => {
    let cancelled = false
    async function loadLight() {
      try {
        const d = await api<CommandCenter>('/command-center?light=1')
        if (!cancelled) {
          setLight(d)
          setError('')
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load')
      }
    }
    async function loadFull() {
      try {
        const d = await api<CommandCenter>('/command-center')
        if (!cancelled) setFull(d)
      } catch {
        /* light path still useful */
      }
    }
    void loadLight()
    void loadFull()
    const tLight = setInterval(() => void loadLight(), 4000)
    const tFull = setInterval(() => void loadFull(), 20000)
    return () => {
      cancelled = true
      clearInterval(tLight)
      clearInterval(tFull)
    }
  }, [])

  const d: CommandCenter = { ...(light || {}), ...(full || {}) }
  const mid = d.middle_bank || {}
  const hero = mid.hero_txn_id || 'CW-MID-02'
  const scale = d.scale_evidence || {}
  const ing = d.ingestion || {}
  const sn = d.suspicious_networks || {}
  const wf = d.workflow || {}
  const nv = d.network_visibility || {}
  const sc = d.scorecard || {}
  const det = (sc.detection?.metrics || {}) as Kv
  const ingestBench = (sc.ingest || {}) as Kv
  const comp = (sc.investigation_compression || sn) as Kv
  const impact = (sc.impact || {}) as Kv
  const dna = d.pattern_dna || {}
  const show = d.showcase || {}
  const pct = nv.network_visibility_pct
  const measuring = !full

  return (
    <div>
      <div className="page-head">
        <h2>Home</h2>
        <p>
          The transaction is not the crime. The network is. Detect → evidence → Gemini (grounded) →
          human → Crime Pattern DNA.
        </p>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="l">Live TPS</div>
          <div className="n">{d.live_tps ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="l">P95 ingest (ms)</div>
          <div className="n">{d.p95_ingest_ms ?? d.ingestion_latency_ms?.p95 ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Pub/Sub backlog</div>
          <div className="n">{d.pubsub_backlog ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Cloud Run instances</div>
          <div className="n">{d.cloud_run_instances ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="l">Suspicious networks</div>
          <div className="n">
            {sn.network_investigations ?? sn.network_items_reviewed ?? '—'}
          </div>
        </div>
        <div className="stat">
          <div className="l">Active investigations</div>
          <div className="n">{d.active_investigations ?? '—'}</div>
        </div>
      </div>

      {error && (
        <p className="error" style={{ padding: '0 22px' }}>
          {error}
        </p>
      )}

      <div className="pad">
        <div className="grid2">
          <div className="card">
            <h3>Today’s impact</h3>
            {kv(
              'Network detection',
              `${det.recall ?? '—'} recall · ${det.precision ?? '—'} precision`,
            )}
            {kv(
              'Investigation compression',
              `${comp.baseline_items_reviewed ?? comp.flagged_transactions ?? 0} wires → ${comp.network_items_reviewed ?? comp.network_investigations ?? 0} networks (${comp.compression_ratio ?? '—'}×)`,
            )}
            {kv(
              'Pattern DNA matches',
              `${dna.pattern_matches ?? 0} · avg ${dna.average_match_strength ?? '—'}%`,
            )}
            {kv('False-positive reduction', impact.false_positive_reduction ?? '—')}
            <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
              {String(impact.note || 'Measured on the synthetic ledger.')}
            </p>
          </div>
          <div className="card">
            <h3>Scale evidence</h3>
            {kv('Measured', `${scale.measured_tps ?? ingestBench.achieved_tps ?? '—'} TPS`)}
            {kv('Status', scale.status || '—')}
            {kv('Primary bottleneck', scale.primary_bottleneck || '—')}
            <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
              {scale.note ||
                'Sustained ingest under SLO: 814 TPS. 5,000 TPS is a target, not a claim.'}
            </p>
          </div>
        </div>

        <div className="grid2" style={{ marginTop: 12 }}>
          <div className="card">
            <h3>Active corridors</h3>
            {(d.active_corridors || []).slice(0, 6).map((c) =>
              kv(c.corridor, `${c.suspicious_count ?? 0} / ${c.count ?? 0} · ${c.risk ?? '—'}`),
            )}
            {!d.active_corridors?.length && (
              <div className="muted">{measuring ? 'Measuring…' : 'No corridor stats yet.'}</div>
            )}
          </div>
          <div className="card">
            <h3>Ingest / investigation</h3>
            {kv('received', ing.transactions_received_total ?? 0)}
            {kv('processed', ing.transactions_processed_total ?? 0)}
            {kv('duplicates', ing.transactions_duplicate_total ?? 0)}
            {kv('ingest p95 ms', d.p95_ingest_ms ?? d.ingestion_latency_ms?.p95 ?? 0)}
            {kv('network compression', `${sn.compression_ratio ?? 0}x`)}
            {kv(
              'workflow',
              `open ${wf.open ?? 0} · review ${wf.analyst_review ?? 0} · referred ${wf.referred_fiu ?? 0} · FIU ${wf.escalated_fiu ?? 0} · closed ${wf.closed ?? 0}`,
            )}
            {kv('database', d.database || '—')}
            {kv('environment', d.environment || '—')}
            {kv(
              'live stream',
              `${d.live_stream?.running ? 'RUNNING' : 'idle'} · ${String(d.live_stream?.transport || 'in_process')}`,
            )}
            {kv('stream published', d.live_stream?.accepted ?? 0)}
            {kv('stream flagged', d.live_stream?.queued_for_investigation ?? 0)}
            {kv(
              'pubsub',
              d.pubsub?.wired
                ? `WIRED · ${String(d.pubsub.topic)} → ${String(d.pubsub.subscription)}`
                : d.environment === 'local'
                  ? 'local in-process'
                  : String(d.pubsub?.error || 'not confirmed'),
            )}
            {kv('investigation path', d.investigation_path || String(d.pubsub?.investigation_path || '—'))}
            {kv(
              'network visibility',
              `${nv.network_visibility_pct ?? '—'}% · ${nv.partial_network ? 'partial' : 'complete'}`,
            )}
            {kv('institutions in view', (d.institutions || []).length)}
            {kv('home bank', nv.home_institution || 'BANK_SG')}
            {d.observability_note && (
              <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
                {d.observability_note}
              </p>
            )}
          </div>
          <div className="card">
            <h3>SLOs / alerts</h3>
            {Object.entries(d.slos || {})
              .filter(([, v]) => v && v.target)
              .map(([k, v]) =>
                kv(
                  k,
                  `${v.status || '—'} · ${v.p95_ms != null ? `p95 ${v.p95_ms}ms` : v.note || v.target}`,
                ),
              )}
            {(d.alerts || []).length
              ? (d.alerts || []).map((a, i) =>
                  kv(`${a.severity || ''} ${a.id || ''}`.trim() || `alert-${i}`, a.detail || '—'),
                )
              : kv('firing', 'none')}
          </div>
        </div>

        <div className="grid2" style={{ marginTop: 12 }}>
          <div className="card">
            <h3>Partial network — middle bank</h3>
            {kv('Home institution', mid.home_institution || 'BANK_SG')}
            {kv('Observed path', mid.observed_path || 'BANK_IN → BANK_SG → BANK_PH')}
            {kv('Unresolved', (mid.unknown || []).join(' · ') || 'Bank D / off-ramp')}
            <p>{mid.visibility_note || mid.story || 'PARTIAL NETWORK OBSERVED'}</p>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn" type="button" onClick={() => navigate(`/investigate/${hero}`)}>
                Open {hero}
              </button>
              {isFiu(session?.role || '') && <span className="chip on">FIU actions enabled</span>}
            </div>
          </div>
          <div className="card">
            <h3>{show.title || 'Lotus Ring'}</h3>
            {measuring && !show.hero_txn_id ? (
              <div className="muted">Measuring…</div>
            ) : (
              <>
                {kv(show.title || 'Lotus Ring', show.hero_txn_id || '—')}
                <p>{show.story || ''}</p>
                <div className="muted">
                  {(show.corridors || []).join(' · ')}
                  {(show.institutions || []).length
                    ? ` · ${(show.institutions || []).length} banks`
                    : ''}
                </div>
                {show.hero_txn_id && (
                  <div style={{ marginTop: 8 }}>
                    <button
                      className="btn"
                      type="button"
                      onClick={() => navigate(`/investigate/${show.hero_txn_id}`)}
                    >
                      Open hero case
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="grid2" style={{ marginTop: 12 }}>
          <div className="card">
            <h3>Measured scorecard</h3>
            {measuring && !sc.detection ? (
              <div className="muted">Measuring…</div>
            ) : (
              <>
                {kv('precision / recall', `${det.precision ?? '—'} / ${det.recall ?? '—'}`)}
                {kv(
                  'false-positive rate',
                  det.false_positive_rate ??
                    (sc.false_positives as Kv | undefined)?.benchmark_false_positive_rate ??
                    '—',
                )}
                {kv(
                  'analyst clear-rate',
                  (sc.false_positives as Kv | undefined)?.analyst_clear_rate ?? '—',
                )}
                {kv(
                  'compression',
                  `${comp.flagged_transactions || 0} flags → ${comp.network_investigations || 0} networks (${comp.compression_ratio || '—'}x)`,
                )}
                {kv('load-test mode', ingestBench.mode ?? '—')}
                {kv(
                  'measured ingest TPS',
                  `${ingestBench.achieved_tps ?? '—'} of ${ingestBench.requested_rate ?? '—'} requested`,
                )}
                {kv('publish TPS', ingestBench.achieved_publish_tps ?? '—')}
                {kv('ledger processed', ingestBench.processed_from_ledger ?? '—')}
                {kv(
                  'Pub/Sub backlog',
                  `${ingestBench.pubsub_backlog_start ?? '—'} → ${ingestBench.pubsub_backlog_end ?? '—'}`,
                )}
                {kv(
                  'Cloud Run instances',
                  ingestBench.cloud_run_instances ?? d.cloud_run_instances ?? '—',
                )}
                <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
                  {String(
                    ingestBench.note ||
                      (sc.false_positives as Kv | undefined)?.note ||
                      'Numbers are measured, not claimed. in_process ≠ HTTP ≠ Pub/Sub.',
                  )}
                </p>
              </>
            )}
          </div>
          <div className="card">
            <h3>Network visibility</h3>
            {kv(
              'Coverage',
              pct == null
                ? 'Measured after full Home load — not a guilt score'
                : `${pct}% — not a guilt score`,
            )}
            {pct != null && (
              <div
                style={{
                  height: 8,
                  background: '#e2e8f0',
                  borderRadius: 4,
                  margin: '8px 0',
                  overflow: 'hidden',
                }}
              >
                <div style={{ height: '100%', width: `${pct}%`, background: '#3FA796' }} />
              </div>
            )}
            {kv('Unknown boundaries', nv.unknown?.boundaries ?? '—')}
            <p className="muted" style={{ marginBottom: 0, fontSize: 12.5 }}>
              {nv.note ||
                mid.visibility_note ||
                'Observed hops only. Downstream beyond BANK_PH is unresolved.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
