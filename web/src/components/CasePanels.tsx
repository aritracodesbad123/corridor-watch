import { useState } from 'react'

type Session = {
  bot_likelihood?: number
  copy_paste_risk?: number
  typing_deviation?: number
  navigation_velocity?: number
  geo_mismatch?: boolean
}

export function SessionCard({ sessions }: { sessions?: unknown }) {
  const list = Array.isArray(sessions) ? (sessions as Session[]) : []
  if (!list.length) return <div className="muted">No sessions</div>
  const s = list[0]
  const bot = Number(s.bot_likelihood || 0)
  return (
    <>
      <div className="kv">
        <span>bot likelihood</span>
        <span>{s.bot_likelihood ?? '—'}</span>
      </div>
      <div className="bar">
        <i style={{ width: `${Math.min(100, bot * 100)}%` }} />
      </div>
      <div className="kv">
        <span>copy-paste risk</span>
        <span>{s.copy_paste_risk ?? '—'}</span>
      </div>
      <div className="kv">
        <span>typing deviation</span>
        <span>{s.typing_deviation ?? '—'}</span>
      </div>
      <div className="kv">
        <span>nav velocity</span>
        <span>{s.navigation_velocity ?? '—'}</span>
      </div>
      <div className="kv">
        <span>geo mismatch</span>
        <span>{s.geo_mismatch ? 'yes' : 'no'}</span>
      </div>
    </>
  )
}

function pillClass(level?: string) {
  const l = (level || '').toLowerCase()
  if (l === 'high' || l === 'critical') return 'high'
  if (l === 'medium' || l === 'med') return 'medium'
  return 'low'
}

type Evidence = {
  evidence_id?: string
  type?: string
  confidence?: number
  description?: string
  source?: string
  source_ref?: string
}

type Report = {
  investigation_summary?: string
  risk_hypothesis?: string
  confidence?: number | string
  gemini_used?: boolean
  recommended_disposition?: string
  uncertainty?: string
  supporting_evidence?: Evidence[]
  contradicting_evidence?: Evidence[]
  alternative_explanations?: string[]
  recommended_next_checks?: string[]
  matched_patterns?: string[]
}

export function InvestigationReport({ report }: { report?: Report | null }) {
  const [focusId, setFocusId] = useState('')
  if (!report) return null
  const items = report.supporting_evidence || []

  function focusEvidence(id: string) {
    setFocusId(id)
    const card = document.querySelector(`.ev-card[data-eid="${CSS.escape(id)}"]`)
    card?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3>Grounded investigation (plain-English brief)</h3>
      <p style={{ lineHeight: 1.55 }}>{report.investigation_summary || ''}</p>
      <div className="muted" style={{ marginTop: 8 }}>
        <b>Why it looks this way:</b> {report.risk_hypothesis || ''}
      </div>
      <div className="kv">
        <span>confidence</span>
        <span>
          {report.confidence ?? '—'} · {report.gemini_used ? 'gemini' : 'deterministic'}
        </span>
      </div>
      <div className="kv">
        <span>recommended action</span>
        <span>{report.recommended_disposition || '—'}</span>
      </div>
      <div className="muted" style={{ marginTop: 6 }}>
        <b>Still unknown:</b> {report.uncertainty || '—'}
      </div>
      <h3 style={{ marginTop: 12 }}>Evidence a non-specialist can read</h3>
      <div>
        {items.length
          ? items.map((e) => (
              <button
                key={e.evidence_id}
                type="button"
                className="ev-chip"
                onClick={() => e.evidence_id && focusEvidence(e.evidence_id)}
              >
                {e.evidence_id}
              </button>
            ))
          : <span className="muted">No evidence IDs</span>}
      </div>
      {items.map((e) => (
        <div
          className={`ev-card${focusId && focusId === e.evidence_id ? ' on' : ''}`}
          key={`ev-${e.evidence_id || Math.random()}`}
          data-eid={e.evidence_id}
          id={e.evidence_id ? `ev-${e.evidence_id}` : undefined}
        >
          <div className="kv">
            <span>
              {e.evidence_id} · {e.type || ''}
            </span>
            <span>{Math.round((e.confidence || 0) * 100)}%</span>
          </div>
          <div>{e.description || ''}</div>
          <div className="muted">
            {e.source || ''} · {e.source_ref || ''}
          </div>
        </div>
      ))}
      {!!(report.contradicting_evidence || []).length && (
        <>
          <h3>What cuts against the risk story</h3>
          {(report.contradicting_evidence || []).map((e) => (
            <div className="ev-card" key={e.evidence_id}>
              <b>{e.evidence_id}</b> — {e.description || ''}
            </div>
          ))}
        </>
      )}
      <h3>Other possible explanations</h3>
      <ul className="tight">
        {(report.alternative_explanations || []).map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      <h3>What a human should do next</h3>
      <ul className="tight">
        {(report.recommended_next_checks || []).map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      {!!(report.matched_patterns || []).length && (
        <div className="muted">Pattern DNA: {(report.matched_patterns || []).join(', ')}</div>
      )}
    </div>
  )
}

const TOOL_LABEL: Record<string, string> = {
  get_account_context: 'Account history',
  get_shared_devices: 'Shared devices',
  get_session_biometrics: 'Login sessions',
  get_network_neighborhood: 'Corridor network',
}

function toolCallLine(calls: unknown) {
  if (!Array.isArray(calls)) return ''
  const seen = new Set<string>()
  const labels: string[] = []
  for (const raw of calls) {
    const name =
      raw && typeof raw === 'object' && 'tool' in raw ? String((raw as { tool?: string }).tool || '') : ''
    if (!name) continue
    const label = TOOL_LABEL[name] || name.replace(/_/g, ' ')
    if (seen.has(label)) continue
    seen.add(label)
    labels.push(label)
  }
  return labels.join(', ')
}

export function VerdictPanel({
  data,
}: {
  data: Record<string, unknown> | null
}) {
  if (!data) {
    return <div className="muted">Run investigation to populate verdict.</div>
  }
  const v = ((data.verdict as Record<string, unknown>) || data) as Record<string, unknown>
  const doc = data.document_verification as Record<string, unknown> | undefined
  const report = (data.investigation_report || v.investigation_report) as Report | undefined
  const dag = data.dag as
    | { run_id?: string; trace?: Array<{ step?: string; status?: string; description?: string }> }
    | undefined
  const level = String(v.risk_level || '')
  const tools = toolCallLine(v.tool_calls)
  return (
    <>
      <div className={`verdict ${pillClass(level)}`}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
          <span className={`pill ${pillClass(level)}`}>
            {level || '—'} · {String(v.risk_score ?? '—')}
          </span>
          <span className="case-id">
            {String(v.primary_pattern || '').replace(/_/g, ' ')} ·{' '}
            {String(v.provenance || (v.mode === 'gemini' ? 'grounded' : v.mode || ''))}
            {data.cached ? ' · cached' : ''}
          </span>
          {v.gemini_model ? <span className="case-id">{String(v.gemini_model)}</span> : null}
        </div>
        <p style={{ lineHeight: 1.55, margin: '0 0 8px' }}>{String(v.rationale || '')}</p>
        <div className="muted">
          <b style={{ color: 'var(--text)' }}>What to do next:</b> {String(v.recommended_action || '—')}
        </div>
        {tools && (
          <div className="muted" style={{ marginTop: 6 }}>
            <b>Evidence looked up:</b> {tools}
          </div>
        )}
        {v.note ? (
          <div className="muted" style={{ marginTop: 6 }}>
            {String(v.note)}
          </div>
        ) : null}
        {doc && (
          <div className="muted" style={{ marginTop: 8 }}>
            <b>Document evidence:</b> {String(doc.verification_status || '')} —{' '}
            {String(doc.verification_note || '')}
          </div>
        )}
      </div>
      <InvestigationReport report={report} />
      {dag?.trace?.length ? (
        <div className="card" style={{ marginTop: 12 }}>
          <h3>DAG run {dag.run_id || ''}</h3>
          <div className="dag">
            {dag.trace.map((s, i) => (
              <div className="dag-step" key={`${s.step}-${i}`}>
                <div className="dag-n">{i + 1}</div>
                <div>
                  <b>{s.step}</b> · {s.status}
                  <div className="muted">{s.description || ''}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </>
  )
}

function bullets(arr: unknown) {
  const list = Array.isArray(arr) ? arr.map(String) : []
  if (!list.length) return <li className="muted">none</li>
  return list.map((e) => <li key={e}>{e}</li>)
}

export function DebatePanel({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <div className="muted">Launch debate to populate prosecutor / defense / judge.</div>
  const card = (data.scorecard || {}) as Record<string, unknown>
  const j = (data.judge || {}) as Record<string, unknown>
  const p = (data.prosecutor || {}) as Record<string, unknown>
  const dfn = (data.defense || {}) as Record<string, unknown>
  return (
    <div className="grid2" style={{ marginTop: 12 }}>
      <div className="card">
        <h3>Prosecutor</h3>
        <p style={{ lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{String(p.argument || p.summary || '')}</p>
        <ul className="tight">{bullets(p.key_evidence || p.points)}</ul>
      </div>
      <div className="card">
        <h3>Defense</h3>
        <p style={{ lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{String(dfn.argument || dfn.summary || '')}</p>
        <ul className="tight">{bullets(dfn.key_evidence || dfn.points)}</ul>
      </div>
      <div className="card">
        <h3>Judge</h3>
        <div className="kv">
          <span>ruling</span>
          <span>{String(j.ruling || j.disposition || card.recommended_disposition || '—')}</span>
        </div>
        <p style={{ lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{String(j.rationale || j.summary || '')}</p>
        <ul className="tight">{bullets(j.concerns || j.next_checks)}</ul>
      </div>
      <div className="card">
        <h3>Scorecard</h3>
        {Object.entries(card).slice(0, 8).map(([k, v]) => (
          <div className="kv" key={k}>
            <span>{k}</span>
            <span>{typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

type SofData = {
  plausibility?: string
  severity?: string
  inconsistencies?: Array<{ code?: string; detail?: string }>
  draft_narrative?: string
  error?: string
}

export function SofResult({ data }: { data: SofData | null }) {
  if (!data) return null
  if (data.error) return <div className="error">{data.error}</div>
  const items = data.inconsistencies || []
  return (
    <div style={{ marginTop: 10, fontSize: 12.5 }}>
      <div>
        <b>{data.plausibility || '—'}</b>
        {data.severity ? ` · ${data.severity}` : ''}
      </div>
      <ul className="tight">
        {items.length
          ? items.map((i, idx) => (
              <li key={idx}>
                {i.code || 'issue'}: {i.detail || ''}
              </li>
            ))
          : <li>No inconsistencies</li>}
      </ul>
      {data.draft_narrative ? <p style={{ lineHeight: 1.5 }}>{data.draft_narrative}</p> : null}
    </div>
  )
}

type Precedent = {
  pattern?: string
  similarity?: number | string
  outcome?: string
  summary?: string
}

type MemoryData = {
  summary?: string
  precedents?: Precedent[]
  error?: string
}

export function PrecedentsResult({ data }: { data: MemoryData | null }) {
  if (!data) return null
  if (data.error) return <div className="error">{data.error}</div>
  return (
    <div style={{ marginTop: 10, fontSize: 12.5 }}>
      <p style={{ marginTop: 0 }}>{data.summary || ''}</p>
      <ul className="tight">
        {(data.precedents || []).map((p, i) => (
          <li key={i}>
            <b>{p.pattern || '—'}</b> ({p.similarity ?? '—'}) — {p.outcome || '—'}
            <br />
            <span className="muted">{p.summary || ''}</span>
          </li>
        ))}
        {!(data.precedents || []).length && <li className="muted">No precedents retrieved</li>}
      </ul>
    </div>
  )
}
