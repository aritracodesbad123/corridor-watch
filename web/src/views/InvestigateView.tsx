import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, isFiu, isMrm } from '../api'
import { useAuth } from '../auth'
import { DebatePanel, PrecedentsResult, SessionCard, SofResult, VerdictPanel } from '../components/CasePanels'
import { CorridorMap, geoSummary, type Geo } from '../components/CorridorMap'
import { MoneyFlowDag, type MoneyFlowNetwork } from '../components/MoneyFlowDag'

type AlertRow = {
  txn_id: string
  corridor?: string
  amount?: number
  risk_score?: number
  primary_pattern?: string
  showcase?: string
  workflow_state?: string
  currency?: string
}

type AccountCtx = {
  risk_features?: Record<string, number | string>
  recent_activity?: Array<Record<string, unknown>>
  sessions?: unknown
  [key: string]: unknown
}

type CaseDetail = {
  transaction: Record<string, unknown>
  sender: AccountCtx
  receiver: AccountCtx
  network?: Record<string, unknown>
  workflow_state?: string
  cached_verdict?: Record<string, unknown> | null
  dag_steps?: Array<{ id: number | string; name: string; description?: string }>
  pattern_matches?: PatternMatch[]
  visibility?: Record<string, unknown>
  boundaries?: Array<{ boundary_id?: string; direction?: string; description?: string }>
  analyst_decisions?: Array<{ decision: string; decided_at: string; notes?: string }>
  debate?: Record<string, unknown>
  [key: string]: unknown
}

type PatternMatch = {
  name?: string
  pattern_id?: string
  match_strength?: number
  score?: number
  matched_signals?: string[]
  missing_signals?: string[]
}

const WF_ORDER = ['open', 'analyst_review', 'referred_fiu', 'escalated_fiu', 'closed'] as const
const WF_LABELS: Record<string, string> = {
  open: 'Open',
  analyst_review: 'Analyst review',
  referred_fiu: 'Sent to FIU',
  escalated_fiu: 'FIU lead',
  closed: 'Audit closed',
}

function showcaseLabel(showcase?: string) {
  if (showcase === 'middle_bank') return 'MIDDLE BANK · PARTIAL · '
  if (showcase) return 'LOTUS RING · '
  return ''
}

const TABS = [
  'overview',
  'network',
  'map',
  'behavior',
  'verdict',
  'debate',
  'docverify',
  'whatif',
  'sar',
  'decision',
] as const

type Tab = (typeof TABS)[number]

const TAB_LABEL: Record<Tab, string> = {
  overview: 'Overview',
  network: 'Money flow',
  map: 'Corridor map',
  behavior: 'Behavioral',
  verdict: 'Verdict',
  debate: 'AI Debate',
  docverify: 'Doc Verifier',
  whatif: 'What-If',
  sar: 'SAR Filing',
  decision: 'Workflow',
}

function riskSeverity(score?: number) {
  if ((score || 0) >= 80) return 'high'
  if ((score || 0) >= 50) return 'medium'
  return 'low'
}

function riskClass(score?: number) {
  const band = riskSeverity(score)
  if (band === 'high') return 'hi'
  if (band === 'medium') return 'mid'
  return 'lo'
}

function patternBars(risk: Record<string, number | string> | undefined) {
  if (!risk) return <div className="muted">none</div>
  const scores = risk.pattern_scores
  let entries: [string, number][] = []
  if (typeof scores === 'string') {
    try {
      entries = Object.entries(JSON.parse(scores) as Record<string, number>)
    } catch {
      entries = []
    }
  } else if (scores && typeof scores === 'object') {
    entries = Object.entries(scores as Record<string, number>)
  }
  if (!entries.length) {
    const primary = String(risk.primary_pattern || '')
    const score = Number(risk.risk_score || 0)
    if (primary) entries = [[primary, score]]
  }
  if (!entries.length) return <div className="muted">none</div>
  return (
    <>
      {entries.map(([k, v]) => (
        <div key={k}>
          <div className="kv">
            <span>{k}</span>
            <span>{v}</span>
          </div>
          <div className="bar">
            <i style={{ width: `${Math.min(100, Number(v) || 0)}%` }} />
          </div>
        </div>
      ))}
    </>
  )
}

function fmtFeatures(acc: AccountCtx | undefined) {
  const r = acc?.risk_features || {}
  const bits = [
    r.account_age_days != null ? `age ${r.account_age_days}d` : null,
    r.pass_through_ratio != null ? `pass-through ${r.pass_through_ratio}` : null,
    r.shared_device_count != null ? `devices ${r.shared_device_count}` : null,
  ].filter(Boolean)
  return bits.join(' · ') || '—'
}

export function InvestigateView() {
  const { txnId } = useParams()
  const navigate = useNavigate()
  const { session } = useAuth()
  const role = session?.role || ''
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [verdict, setVerdict] = useState<Record<string, unknown> | null>(null)
  const [debate, setDebate] = useState<Record<string, unknown> | null>(null)
  const [audit, setAudit] = useState<unknown[]>([])
  const [sar, setSar] = useState('')
  const [sarJurisdiction, setSarJurisdiction] = useState<'fincen' | 'mas' | 'austrac'>('fincen')
  const [whatIf, setWhatIf] = useState('')
  const [docStatus, setDocStatus] = useState('')
  const [disposition, setDisposition] = useState('hold_payment')
  const [notes, setNotes] = useState('')
  const [wfOut, setWfOut] = useState('')
  const [queueCorridor, setQueueCorridor] = useState('')
  const [queuePattern, setQueuePattern] = useState('')
  const [queueSeverity, setQueueSeverity] = useState('')
  const [queueSort, setQueueSort] = useState<'newest' | 'oldest' | 'risk'>('newest')
  const [age, setAge] = useState(180)
  const [ptr, setPtr] = useState(0.5)
  const [hold, setHold] = useState(30)
  const [dev, setDev] = useState(1)
  const [sideOut, setSideOut] = useState<'sof' | 'mem' | ''>('')
  const [sofData, setSofData] = useState<Parameters<typeof SofResult>[0]['data']>(null)
  const [memData, setMemData] = useState<Parameters<typeof PrecedentsResult>[0]['data']>(null)
  const [investPayload, setInvestPayload] = useState<Record<string, unknown> | null>(null)

  const current = txnId || ''

  const loadAlerts = useCallback(async () => {
    const rows = await api<AlertRow[]>(`/alerts?sort=${encodeURIComponent(queueSort)}`)
    setAlerts(Array.isArray(rows) ? rows : [])
  }, [queueSort])

  const loadCase = useCallback(async (id: string) => {
    if (!id) {
      setDetail(null)
      return
    }
    const d = await api<CaseDetail>(`/alerts/${encodeURIComponent(id)}`)
    setDetail(d)
    if (d.cached_verdict) {
      setVerdict(d.cached_verdict)
      setInvestPayload({ verdict: d.cached_verdict, cached: true })
    }
    const wf = (d as { whatif_features?: Record<string, number> }).whatif_features
    if (wf) {
      if (wf.account_age_days != null) setAge(Number(wf.account_age_days))
      if (wf.pass_through_ratio != null) setPtr(Number(wf.pass_through_ratio))
      if (wf.avg_hold_time_minutes != null) setHold(Number(wf.avg_hold_time_minutes))
      if (wf.shared_device_count != null) setDev(Number(wf.shared_device_count))
    }
  }, [])

  useEffect(() => {
    void loadAlerts().catch((e) => setMsg(String(e.message || e)))
    const t = setInterval(() => void loadAlerts().catch(() => {}), 8000)
    return () => clearInterval(t)
  }, [loadAlerts])

  useEffect(() => {
    if (!current && alerts.length) {
      const mid = alerts.find((a) => a.showcase === 'middle_bank') || alerts[0]
      navigate(`/investigate/${mid.txn_id}`, { replace: true })
      return
    }
    if (current) {
      setMsg('')
      void loadCase(current).catch((e) => setMsg(String(e.message || e)))
    }
  }, [current, alerts, navigate, loadCase])

  useEffect(() => {
    if (!current) return
    void api<unknown[]>(`/alerts/${encodeURIComponent(current)}/audit`)
      .then(setAudit)
      .catch(() => setAudit([]))
    setSideOut('')
    setSofData(null)
    setMemData(null)
  }, [current])

  const t = detail?.transaction
  const network = (detail?.network || {}) as Record<string, unknown>
  const nodes = useMemo(() => {
    const n = network.nodes
    return Array.isArray(n) ? (n as Record<string, unknown>[]) : []
  }, [network])
  const edges = useMemo(() => {
    const e = network.edges
    return Array.isArray(e) ? (e as Record<string, unknown>[]) : []
  }, [network])
  const vis = (detail?.visibility || network.visibility || {}) as Record<string, unknown>
  const sRisk = (detail?.sender?.risk_features || {}) as Record<string, number | string>
  const rRisk = (detail?.receiver?.risk_features || {}) as Record<string, number | string>

  async function runInvestigate(mode: 'deterministic' | 'gemini' | 'auto') {
    if (!current) return
    setBusy(mode)
    setMsg('')
    try {
      const data = await api<Record<string, unknown>>(`/alerts/${encodeURIComponent(current)}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          force: mode !== 'auto',
        }),
      })
      const v = (data.verdict || data) as Record<string, unknown>
      setVerdict(v)
      setInvestPayload(data)
      await loadCase(current)
      setTab('verdict')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Investigate failed')
    } finally {
      setBusy('')
    }
  }

  async function runDebate() {
    if (!current) return
    setBusy('debate')
    setMsg('')
    try {
      const data = await api<Record<string, unknown>>(`/alerts/${encodeURIComponent(current)}/debate`, {
        method: 'POST',
      })
      setDebate(data)
      setTab('debate')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Debate failed')
    } finally {
      setBusy('')
    }
  }

  async function applyIntel() {
    setBusy('intel')
    setMsg('')
    try {
      await api('/intelligence/simulate', { method: 'POST' })
      if (current) await loadCase(current)
      setMsg('Synthetic intelligence applied (external hop).')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Intel failed')
    } finally {
      setBusy('')
    }
  }

  async function submitDecision() {
    if (!current) return
    setBusy('decision')
    try {
      await api(`/alerts/${encodeURIComponent(current)}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: disposition, notes }),
      })
      await loadCase(current)
      setMsg('Decision recorded.')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Decision failed')
    } finally {
      setBusy('')
    }
  }

  async function runWorkflow(action: string) {
    if (!current) return
    setBusy(`wf-${action}`)
    setWfOut('')
    try {
      const data = await api<{ action?: string; workflow_state?: string }>(
        `/alerts/${encodeURIComponent(current)}/workflow`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, notes }),
        },
      )
      setWfOut(
        data.action === 'refer_fiu'
          ? 'Sent to FIU lead. It now appears on the FIU queue.'
          : `${data.action} → ${data.workflow_state}`,
      )
      await loadCase(current)
      await loadAlerts()
      void api<unknown[]>(`/alerts/${encodeURIComponent(current)}/audit`)
        .then(setAudit)
        .catch(() => {})
    } catch (e) {
      setWfOut(e instanceof Error ? e.message : 'Workflow failed')
    } finally {
      setBusy('')
    }
  }

  async function loadSar() {
    if (!current) return
    setBusy('sar')
    try {
      const data = await api<{
        full_narrative_text?: string
        narrative?: string
        jurisdiction?: string
        filing_form?: string
        mode?: string
      }>(`/alerts/${encodeURIComponent(current)}/sar?jurisdiction=${sarJurisdiction}`)
      const text = data.full_narrative_text || data.narrative || JSON.stringify(data, null, 2)
      setSar(
        [
          data.jurisdiction || sarJurisdiction,
          data.filing_form || '',
          data.mode ? `mode ${data.mode}` : '',
          '',
          text,
        ]
          .filter((x, i, a) => x || i === a.length - 1)
          .join('\n'),
      )
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'SAR failed')
    } finally {
      setBusy('')
    }
  }

  async function runWhatIf() {
    if (!current) return
    setBusy('whatif')
    try {
      const data = await api(`/alerts/${encodeURIComponent(current)}/counterfactual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_age_days: age,
          pass_through_ratio: ptr,
          avg_hold_time_minutes: hold,
          shared_device_count: dev,
        }),
      })
      setWhatIf(JSON.stringify(data, null, 2))
      setTab('whatif')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'What-if failed')
    } finally {
      setBusy('')
    }
  }

  async function runSof() {
    if (!current) return
    setBusy('sof')
    setSideOut('sof')
    setSofData(null)
    try {
      const explanation = String(detail?.transaction?.source_of_funds || '')
      const data = await api<NonNullable<Parameters<typeof SofResult>[0]['data']>>(
        `/phase2/sof/${encodeURIComponent(current)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ explanation, use_llm: true }),
        },
      )
      setSofData(data)
      void api<unknown[]>(`/alerts/${encodeURIComponent(current)}/audit`)
        .then(setAudit)
        .catch(() => {})
    } catch (e) {
      setSofData({ error: e instanceof Error ? e.message : 'SoF check failed' })
    } finally {
      setBusy('')
    }
  }

  async function runPrecedents() {
    if (!current) return
    setBusy('mem')
    setSideOut('mem')
    setMemData(null)
    try {
      const data = await api<NonNullable<Parameters<typeof PrecedentsResult>[0]['data']>>(
        `/phase2/memory/${encodeURIComponent(current)}`,
      )
      setMemData(data)
    } catch (e) {
      setMemData({ error: e instanceof Error ? e.message : 'Precedents failed' })
    } finally {
      setBusy('')
    }
  }

  const corridors = useMemo(
    () => [...new Set(alerts.map((a) => a.corridor).filter(Boolean) as string[])].sort(),
    [alerts],
  )
  const patterns = useMemo(
    () => [...new Set(alerts.map((a) => a.primary_pattern).filter(Boolean) as string[])].sort(),
    [alerts],
  )
  const filteredAlerts = useMemo(() => {
    let rows = alerts
    if (queueCorridor) rows = rows.filter((a) => a.corridor === queueCorridor)
    if (queuePattern) rows = rows.filter((a) => a.primary_pattern === queuePattern)
    if (queueSeverity) rows = rows.filter((a) => riskSeverity(a.risk_score) === queueSeverity)
    if (queueSort === 'risk') {
      rows = [...rows].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    }
    return rows
  }, [alerts, queueCorridor, queuePattern, queueSeverity, queueSort])

  const wfState = String(detail?.workflow_state || detail?.transaction?.workflow_state || 'open')
  const wfIdx = WF_ORDER.indexOf(wfState as (typeof WF_ORDER)[number])
  const decisions = detail?.analyst_decisions || []
  const bounds =
    detail?.boundaries ||
    ((network as { boundaries?: CaseDetail['boundaries'] }).boundaries || [])
  const obs = (vis.observed || {}) as Record<string, number>
  const ext = (vis.external || {}) as Record<string, number>
  const inf = (vis.inferred || {}) as Record<string, number>
  const unk = (vis.unknown || {}) as Record<string, number>
  const visPct =
    vis.network_visibility_pct ??
    (vis.network_visibility_score != null ? Math.round(Number(vis.network_visibility_score) * 100) : null)

  async function verifyDoc(file: File, continueAnalysis: boolean) {
    if (!current) return
    setBusy('doc')
    setDocStatus('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('continue_analysis', String(continueAnalysis))
      const token = localStorage.getItem('cw_token')
      const res = await fetch(`/api/alerts/${encodeURIComponent(current)}/verify-document`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
        credentials: 'same-origin',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || res.statusText)
      setDocStatus(JSON.stringify(data, null, 2))
      if (continueAnalysis) await loadCase(current)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Doc verify failed')
    } finally {
      setBusy('')
    }
  }


  return (
    <div className="invest-layout">
      <div className="queue">
        <div className="section-h">
          <span>Triage queue · {filteredAlerts.length}</span>
          <span>{queueCorridor || 'all'}</span>
        </div>
        <div className="queue-tools">
          <select
            title="Filter by corridor"
            value={queueCorridor}
            onChange={(e) => setQueueCorridor(e.target.value)}
          >
            <option value="">All corridors</option>
            {corridors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            title="Sort"
            value={queueSort}
            onChange={(e) => setQueueSort(e.target.value as typeof queueSort)}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="risk">Highest risk</option>
          </select>
          <select
            title="Filter by risk severity"
            value={queueSeverity}
            onChange={(e) => setQueueSeverity(e.target.value)}
          >
            <option value="">All severities</option>
            <option value="high">High · 80+</option>
            <option value="medium">Medium · 50–79</option>
            <option value="low">Low · under 50</option>
          </select>
          <select
            title="Filter by pattern"
            value={queuePattern}
            onChange={(e) => setQueuePattern(e.target.value)}
          >
            <option value="">All patterns</option>
            {patterns.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="rows" role="list">
          {filteredAlerts.map((a) => (
            <div
              key={a.txn_id}
              role="listitem"
              className={`row${a.txn_id === current ? ' active' : ''}${a.showcase === 'middle_bank' ? ' middle-bank' : ''}`}
              onClick={() => navigate(`/investigate/${a.txn_id}`)}
            >
              <div className={`risk ${riskClass(a.risk_score)}`}>{Math.round(a.risk_score || 0)}</div>
              <div className="row-main">
                <div className="row-corridor">
                  {showcaseLabel(a.showcase)}
                  {a.corridor || a.txn_id}
                </div>
                <div className="row-sub">
                  {a.txn_id} · {a.currency || 'USD'}{' '}
                  {Number(a.amount || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
                <div className="pat">{a.primary_pattern || a.workflow_state || ''}</div>
              </div>
            </div>
          ))}
          {!filteredAlerts.length && (
            <div className="empty">{alerts.length ? 'No cases at this severity.' : 'No alerts in queue.'}</div>
          )}
        </div>
      </div>

      <div className="detail">
        <div className="section-h">
          <span>Case detail</span>
          <span className="mono">{current || '—'}</span>
        </div>
        <div className="detail-body">
          {!detail || !t ? (
            <div className="empty">{msg || 'Select a case from the queue.'}</div>
          ) : (
            <>
              <div className="tabs" role="tablist">
                {TABS.map((name) => (
                  <button
                    key={name}
                    type="button"
                    role="tab"
                    className={`tab${tab === name ? ' on' : ''}`}
                    onClick={() => setTab(name)}
                  >
                    {TAB_LABEL[name]}
                  </button>
                ))}
              </div>

              {msg && <p className="error">{msg}</p>}

              {tab === 'overview' && (
                <div>
                  <div className="case-id">
                    CASE {String(t.txn_id)} · {String(t.primary_pattern || '')} ·{' '}
                    {String(t.workflow_state || detail.workflow_state || 'open')}
                    {t.showcase === 'middle_bank'
                      ? ' · MIDDLE BANK'
                      : t.showcase
                        ? ' · LOTUS RING'
                        : ''}
                    {visPct != null && (
                      <span className="vis-badge">
                        VISIBILITY {String(visPct)}% · NOT GUILT
                      </span>
                    )}
                    {(t.showcase === 'middle_bank' || Boolean(network.partial_network)) && (
                      <span className="vis-badge">PARTIAL NETWORK OBSERVED</span>
                    )}
                  </div>
                  <div className="amount">${Number(t.amount || 0).toLocaleString()}</div>
                  <div className="muted">
                    {String(t.corridor || '')} ·{' '}
                    {t.ts ? new Date(String(t.ts)).toLocaleString() : '—'} · purpose:{' '}
                    {String(t.purpose || '—')} · SoF: {String(t.source_of_funds || '—')}
                  </div>
                  <div className="flow">
                    <div className="node">
                      <div className="id">{String(t.sender_id)}</div>
                      <div className="age">{fmtFeatures(detail.sender)}</div>
                    </div>
                    <div className="muted">→</div>
                    <div className="node">
                      <div className="id">{String(t.receiver_id)}</div>
                      <div className="age">{fmtFeatures(detail.receiver)}</div>
                    </div>
                  </div>
                  <div className="card" style={{ marginBottom: 12 }}>
                    <h3>Network visibility</h3>
                    <div className="kv">
                      <span>Coverage</span>
                      <span>{visPct == null ? '—' : `${visPct}% — not a guilt score`}</span>
                    </div>
                    <div
                      style={{
                        height: 8,
                        background: '#E8ECF1',
                        borderRadius: 4,
                        margin: '8px 0 12px',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${Number(visPct) || 0}%`,
                          background: '#3FA796',
                        }}
                      />
                    </div>
                    <div className="kv">
                      <span>Observed</span>
                      <span>
                        {obs.nodes ?? 0} nodes · {obs.edges ?? 0} edges
                      </span>
                    </div>
                    <div className="kv">
                      <span>External</span>
                      <span>
                        {ext.nodes ?? 0} nodes · {ext.edges ?? 0} edges
                      </span>
                    </div>
                    <div className="kv">
                      <span>Inferred</span>
                      <span>
                        {inf.nodes ?? 0} nodes · {inf.edges ?? 0} edges
                      </span>
                    </div>
                    <div className="kv">
                      <span>Unknown boundaries</span>
                      <span>{unk.boundaries ?? bounds.length ?? 0}</span>
                    </div>
                    {(bounds || []).slice(0, 6).map((b, i) => (
                      <div className="muted" key={i}>
                        {b.boundary_id || ''} · {b.direction || ''} · {b.description || ''}
                      </div>
                    ))}
                    <p className="muted" style={{ marginBottom: 0, fontSize: 12 }}>
                      PARTIAL NETWORK OBSERVED when unknown hops remain. Incomplete visibility does
                      not lower risk.
                    </p>
                    {isFiu(role) && (
                      <button
                        className="btn secondary"
                        type="button"
                        style={{ marginTop: 10 }}
                        disabled={!!busy}
                        onClick={() => void applyIntel()}
                      >
                        {busy === 'intel' ? 'Applying…' : 'Apply synthetic intelligence'}
                      </button>
                    )}
                  </div>
                  <div className="grid2">
                    <div className="card">
                      <h3>Sender patterns</h3>
                      {patternBars(sRisk)}
                    </div>
                    <div className="card">
                      <h3>Receiver patterns</h3>
                      {patternBars(rRisk)}
                    </div>
                  </div>
                  <div className="grid2" style={{ marginTop: 12 }}>
                    <div className="card">
                      <h3>Sender activity</h3>
                      {(detail.sender.recent_activity || []).slice(0, 5).map((a, i) => (
                        <div className="kv" key={i}>
                          <span>
                            {a.sender_id === t.sender_id ? 'to' : 'from'}{' '}
                            {String(a.sender_id === t.sender_id ? a.receiver_id : a.sender_id)}
                          </span>
                          <span>${String(a.amount)}</span>
                        </div>
                      )) || <div className="muted">none</div>}
                    </div>
                    <div className="card">
                      <h3>Receiver activity</h3>
                      {(detail.receiver.recent_activity || []).slice(0, 5).map((a, i) => (
                        <div className="kv" key={i}>
                          <span>
                            {a.sender_id === t.receiver_id ? 'to' : 'from'}{' '}
                            {String(a.sender_id === t.receiver_id ? a.receiver_id : a.sender_id)}
                          </span>
                          <span>${String(a.amount)}</span>
                        </div>
                      )) || <div className="muted">none</div>}
                    </div>
                  </div>
                  {(detail.pattern_matches || []).length ? (
                    (detail.pattern_matches || []).slice(0, 3).map((m, i) => (
                      <div className="card" style={{ marginTop: 12 }} key={i}>
                        <h3>Pattern DNA: {m.name || m.pattern_id || ''}</h3>
                        <div className="kv">
                          <span>Match strength</span>
                          <span>
                            {m.match_strength ?? Math.round((m.score || 0) * 100)}%
                          </span>
                        </div>
                        <div className="muted" style={{ marginTop: 8 }}>
                          Matched
                        </div>
                        <ul className="tight">
                          {(m.matched_signals || []).length
                            ? (m.matched_signals || []).map((s) => <li key={s}>✓ {s}</li>)
                            : <li className="muted">none</li>}
                        </ul>
                        <div className="muted" style={{ marginTop: 8 }}>
                          Missing
                        </div>
                        <ul className="tight">
                          {(m.missing_signals || []).length
                            ? (m.missing_signals || []).map((s) => <li key={s}>○ {s}</li>)
                            : <li className="muted">none</li>}
                        </ul>
                      </div>
                    ))
                  ) : (
                    <div className="card" style={{ marginTop: 12 }}>
                      <h3>Pattern DNA</h3>
                      <div className="muted">No library match on this network yet.</div>
                    </div>
                  )}
                </div>
              )}

              {tab === 'network' && (
                <div>
                  <div className="card">
                    <h3>Money movement DAG</h3>
                    <p className="muted" style={{ margin: '0 0 6px' }}>
                      Accounts layered left→right by hop depth. Amber edge is this case; amounts on
                      edges. Scroll sideways if hops run past the frame.
                    </p>
                    <MoneyFlowDag network={network as MoneyFlowNetwork} />
                    <div className="viz-legend">
                      <span>
                        <i style={{ background: '#3FA796' }} /> focal / observed
                      </span>
                      <span>
                        <i style={{ background: '#3A4E6A' }} /> external intel
                      </span>
                      <span>
                        <i style={{ background: '#5A4A2A' }} /> inferred
                      </span>
                      <span>
                        <i style={{ background: '#2A2A2A' }} /> unknown boundary
                      </span>
                      <span>
                        <i style={{ background: '#E0A04A' }} /> focal transfer
                      </span>
                      <span>
                        {nodes.length} accounts · {edges.length} transfers
                      </span>
                    </div>
                  </div>
                  <div className="card" style={{ marginTop: 12 }}>
                    <h3>Investigation DAG (12 steps)</h3>
                    {(detail.dag_steps || []).map((s) => (
                      <div className="dag-step" key={String(s.id)}>
                        <div className="dag-n">{s.id}</div>
                        <div>
                          <b>{s.name}</b>
                          <div className="muted">{s.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {tab === 'map' && (
                <div>
                  <div className="card">
                    <h3>Corridor geography</h3>
                    <p className="muted" style={{ margin: '0 0 6px' }}>
                      Where money is revolving for this case neighborhood — real world map, country
                      nodes, aggregated corridor arcs.
                    </p>
                    <CorridorMap geo={(network.geo || {}) as Geo} />
                  </div>
                  <div className="grid2" style={{ marginTop: 12 }}>
                    <div className="card">
                      <h3>Corridor volumes</h3>
                      {geoSummary((network.geo || {}) as Geo)}
                    </div>
                    <div className="card">
                      <h3>Countries in play</h3>
                      {(((network.geo as Geo) || {}).countries || []).map((c, i) => (
                        <div className="kv" key={i}>
                          <span>
                            {c.country} · {c.label || ''}
                            {c.focus ? ' · focal' : ''}
                          </span>
                          <span>
                            in {String(c.in_amount ?? '—')} / out {String(c.out_amount ?? '—')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {tab === 'behavior' && (
                <div className="grid2">
                  <div className="card">
                    <h3>Sender biometrics</h3>
                    <SessionCard sessions={detail.sender?.sessions} />
                    <div className="kv" style={{ marginTop: 10 }}>
                      <span>behavioral risk</span>
                      <span>{String(sRisk.behavioral_risk ?? '—')}</span>
                    </div>
                    <div className="kv">
                      <span>shared devices</span>
                      <span>{String(sRisk.shared_device_count ?? 0)}</span>
                    </div>
                    <div className="kv">
                      <span>pass-through</span>
                      <span>{String(sRisk.pass_through_ratio ?? '—')}</span>
                    </div>
                    <div className="kv">
                      <span>device</span>
                      <span>{String(t.device_id || '—')}</span>
                    </div>
                  </div>
                  <div className="card">
                    <h3>Receiver biometrics</h3>
                    <SessionCard sessions={detail.receiver?.sessions} />
                    <div className="kv" style={{ marginTop: 10 }}>
                      <span>behavioral risk</span>
                      <span>{String(rRisk.behavioral_risk ?? '—')}</span>
                    </div>
                    <div className="kv">
                      <span>shared devices</span>
                      <span>{String(rRisk.shared_device_count ?? 0)}</span>
                    </div>
                    <div className="kv">
                      <span>pass-through</span>
                      <span>{String(rRisk.pass_through_ratio ?? '—')}</span>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'verdict' && (
                <div>
                  <p className="muted">
                    Demo spine: Evidence pack → Gemini brief → AI Debate → FIU decision → Pattern DNA.
                  </p>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                    <button className="btn" type="button" disabled={!!busy} onClick={() => void runInvestigate('auto')}>
                      {busy === 'auto' ? 'Running…' : 'Run investigation (auto)'}
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      disabled={!!busy}
                      onClick={() => void runInvestigate('deterministic')}
                    >
                      {busy === 'deterministic' ? 'Running…' : 'Deterministic DAG only'}
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      disabled={!!busy}
                      onClick={() => void runInvestigate('gemini')}
                    >
                      {busy === 'gemini' ? 'Calling Gemini…' : 'Force Gemini'}
                    </button>
                  </div>
                  <VerdictPanel data={investPayload || (verdict ? { verdict } : null)} />
                </div>
              )}

              {tab === 'debate' && (
                <div>
                  <p className="muted">Adversarial AI Debate (Prosecutor vs Defense). Models recommend — humans decide.</p>
                  <button className="btn" type="button" disabled={!!busy} onClick={() => void runDebate()}>
                    {busy === 'debate' ? 'Debating…' : 'Launch AI Debate'}
                  </button>
                  <DebatePanel data={debate || (detail.debate as Record<string, unknown>) || null} />
                </div>
              )}

              {tab === 'docverify' && (
                <div>
                  <p className="muted">
                    Upload SoF PDF/PNG. Fixtures under validation/fixtures/document_verify/.
                  </p>
                  <div className="field">
                    <label>Verify only</label>
                    <input
                      type="file"
                      accept=".pdf,image/*"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (f) void verifyDoc(f, false)
                      }}
                    />
                  </div>
                  <div className="field">
                    <label>Verify & continue analysis</label>
                    <input
                      type="file"
                      accept=".pdf,image/*"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (f) void verifyDoc(f, true)
                      }}
                    />
                  </div>
                  {docStatus && <pre className="pre">{docStatus}</pre>}
                </div>
              )}

              {tab === 'whatif' && (
                <div>
                  <p className="muted">
                    Counterfactual &quot;What-If&quot; Sensitivity Simulator — test how the case shifts when
                    account age, pass-through, hold time, or shared devices change.
                  </p>
                  <div className="field">
                    <label>
                      Account Age (Days): <span>{age}</span>
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={730}
                      value={age}
                      onChange={(e) => setAge(Number(e.target.value))}
                    />
                  </div>
                  <div className="field">
                    <label>
                      Pass-Through Ratio: <span>{ptr.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1.5}
                      step={0.01}
                      value={ptr}
                      onChange={(e) => setPtr(Number(e.target.value))}
                    />
                  </div>
                  <div className="field">
                    <label>
                      Avg Hold (minutes): <span>{hold}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1440}
                      value={hold}
                      onChange={(e) => setHold(Number(e.target.value))}
                    />
                  </div>
                  <div className="field">
                    <label>
                      Shared devices: <span>{dev}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={20}
                      value={dev}
                      onChange={(e) => setDev(Number(e.target.value))}
                    />
                  </div>
                  <button className="btn secondary" type="button" disabled={!!busy} onClick={() => void runWhatIf()}>
                    {busy === 'whatif' ? 'Simulating…' : 'Simulate What-If'}
                  </button>
                  {whatIf && <pre className="pre">{whatIf}</pre>}
                </div>
              )}

              {tab === 'sar' && (
                <div>
                  <div className="card">
                    <h3>Multi-Jurisdiction Regulatory Filing Generator (SAR / STR)</h3>
                    <p className="muted">
                      Generates official regulatory narrative sections for FinCEN (US), MAS
                      (Singapore), or AUSTRAC (Australia).
                    </p>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
                      <select
                        style={{ width: 220 }}
                        value={sarJurisdiction}
                        onChange={(e) =>
                          setSarJurisdiction(e.target.value as typeof sarJurisdiction)
                        }
                      >
                        <option value="fincen">FinCEN (US - Form 111 SAR)</option>
                        <option value="mas">MAS (Singapore - STR Form A)</option>
                        <option value="austrac">AUSTRAC (Australia - SMR Form B)</option>
                      </select>
                      <button
                        className="btn secondary"
                        type="button"
                        disabled={!!busy}
                        onClick={() => void loadSar()}
                      >
                        {busy === 'sar' ? 'Drafting…' : 'Generate SAR Narrative'}
                      </button>
                    </div>
                    {sar && <pre className="pre">{sar}</pre>}
                  </div>
                </div>
              )}

              {tab === 'decision' && (
                <div>
                  <div className="card">
                    <h3>Case workflow</h3>
                    <p className="muted">
                      Analyst review → FIU lead action → MRM audit close. High-risk dispositions
                      require FIU lead.
                    </p>
                    <div className="workflow">
                      {WF_ORDER.map((s, i) => (
                        <div
                          key={s}
                          className={`wf-step${s === wfState ? ' on' : i < wfIdx ? ' done' : ''}`}
                        >
                          {WF_LABELS[s]}
                        </div>
                      ))}
                    </div>
                    <div className="btn-row">
                      <button
                        className="btn secondary"
                        type="button"
                        disabled={!!busy}
                        onClick={() => void runWorkflow('start_review')}
                      >
                        Start analyst review
                      </button>
                      <button
                        className="btn secondary"
                        type="button"
                        disabled={!!busy}
                        onClick={() => void runWorkflow('refer_fiu')}
                      >
                        Send to FIU lead
                      </button>
                      {isFiu(role) && (
                        <>
                          <button
                            className="btn secondary"
                            type="button"
                            disabled={!!busy}
                            onClick={() => void runWorkflow('escalate')}
                          >
                            Take over (FIU)
                          </button>
                          <button
                            className="btn secondary"
                            type="button"
                            disabled={!!busy}
                            onClick={() => void runWorkflow('close')}
                          >
                            Close case
                          </button>
                        </>
                      )}
                      {isMrm(role) && (
                        <button
                          className="btn secondary"
                          type="button"
                          disabled={!!busy}
                          onClick={() => void runWorkflow('audit_ack')}
                        >
                          MRM audit acknowledge
                        </button>
                      )}
                    </div>
                    {wfOut && <div className="muted">{wfOut}</div>}
                  </div>
                  <div className="card" style={{ marginTop: 12 }}>
                    <h3>Disposition</h3>
                    <p className="muted">
                      Records the disposition and writes to institutional case memory.
                    </p>
                    <div className="field">
                      <label>Decision</label>
                      <select value={disposition} onChange={(e) => setDisposition(e.target.value)}>
                        <option value="clear">clear</option>
                        <option value="monitor">monitor</option>
                        <option value="hold_payment">hold_payment</option>
                        <option value="escalate_fiu">escalate_fiu</option>
                        <option value="freeze_account">freeze_account</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Notes</label>
                      <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
                    </div>
                    {['hold_payment', 'escalate_fiu', 'freeze_account'].includes(disposition) &&
                      !isFiu(role) &&
                      !isMrm(role) && (
                        <p className="error">High-risk dispositions require FIU lead.</p>
                      )}
                    <button
                      className="btn"
                      type="button"
                      disabled={!!busy}
                      onClick={() => void submitDecision()}
                    >
                      {busy === 'decision' ? 'Saving…' : 'Record decision'}
                    </button>
                    <h3 style={{ margin: '12px 0 6px', fontSize: 11, color: 'var(--muted)' }}>
                      HISTORY
                    </h3>
                    {decisions.length ? (
                      decisions.map((d, i) => (
                        <div key={i}>
                          <div className="kv">
                            <span>{d.decision}</span>
                            <span>{new Date(d.decided_at).toLocaleString()}</span>
                          </div>
                          <div className="muted" style={{ marginBottom: 6 }}>
                            {d.notes || ''}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="muted">No decisions yet.</div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="side">
        <div className="section-h">
          <span>Judgment tools</span>
        </div>
        <div className="side-body">
          <div className="card">
            <h3>Judgment tools</h3>
            <div className="btn-row" style={{ padding: 0 }}>
              <button
                className="btn secondary"
                type="button"
                disabled={!current || !!busy}
                onClick={() => void runSof()}
              >
                {busy === 'sof' ? 'Checking…' : 'SoF check'}
              </button>
              <button
                className="btn secondary"
                type="button"
                disabled={!current || !!busy}
                onClick={() => void runPrecedents()}
              >
                {busy === 'mem' ? 'Loading…' : 'Precedents'}
              </button>
            </div>
            {sideOut === 'sof' && <SofResult data={sofData} />}
            {sideOut === 'mem' && <PrecedentsResult data={memData} />}
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <h3>Precedents / memory</h3>
            {memData ? (
              <PrecedentsResult data={memData} />
            ) : (
              <div className="muted">Run Precedents to load institutional memory for this case.</div>
            )}
          </div>
          <div className="card" style={{ marginTop: 12 }}>
            <h3>Audit trail</h3>
            <div className="audit">
              {Array.isArray(audit) && audit.length
                ? audit.map((a, i) => (
                    <div key={i}>{typeof a === 'string' ? a : JSON.stringify(a)}</div>
                  ))
                : 'Open a case to load audit events.'}
            </div>
          </div>
          {current && (
            <button
              className="btn secondary"
              type="button"
              style={{ marginTop: 12 }}
              onClick={() => {
                void (async () => {
                  try {
                    const token = localStorage.getItem('cw_token')
                    const res = await fetch(`/api/alerts/${encodeURIComponent(current)}/export`, {
                      headers: token ? { Authorization: `Bearer ${token}` } : {},
                      credentials: 'same-origin',
                    })
                    if (!res.ok) throw new Error(res.statusText)
                    const blob = await res.blob()
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `case-${current}.html`
                    document.body.appendChild(a)
                    a.click()
                    a.remove()
                    URL.revokeObjectURL(url)
                  } catch (e) {
                    setMsg(e instanceof Error ? e.message : 'Export failed')
                  }
                })()
              }}
            >
              Export case
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
