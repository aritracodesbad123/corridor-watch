import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api, authHeaders, canRunStream, isMrm } from '../api'
import { useAuth } from '../auth'

type Props = {
  health?: { gemini?: string; ok?: boolean } | null
  streamLabel: string
  streamLive: boolean
  onStartStream: () => void
  onStopStream: () => void
  streamBusy?: boolean
}

export function Shell({
  health,
  streamLabel,
  streamLive,
  onStartStream,
  onStopStream,
  streamBusy,
}: Props) {
  const { session, logout } = useAuth()
  const role = session?.role || ''
  const mrm = isMrm(role)
  const [mrmBusy, setMrmBusy] = useState('')
  const [search, setSearch] = useState('')
  const [panel, setPanel] = useState<{ title: string; body: string } | null>(null)
  const [toast, setToast] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const caseMatch = location.pathname.match(/\/investigate\/([^/]+)/)
  const exportId = caseMatch?.[1] ? decodeURIComponent(caseMatch[1]) : ''
  const initials = (session?.display_name || session?.role || 'CW')
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  function showToast(msg: string) {
    setToast(msg)
    window.setTimeout(() => setToast(''), 4000)
  }

  async function runMrmJson(path: string, title: string) {
    setMrmBusy(title)
    try {
      const data = await api(path)
      setPanel({ title, body: JSON.stringify(data, null, 2) })
    } catch (e) {
      setPanel({
        title,
        body: JSON.stringify({ error: e instanceof Error ? e.message : String(e) }, null, 2),
      })
    } finally {
      setMrmBusy('')
    }
  }

  async function runRedteam() {
    if (!confirm('Inject adversarial scenarios into the local DB and re-score?')) return
    setMrmBusy('redteam')
    try {
      const data = await api<{ detected?: number; evaded?: number; ran?: number }>(
        '/phase2/redteam',
        { method: 'POST' },
      )
      showToast(
        `Red-team done: ${data.detected ?? '?'} detected / ${data.evaded ?? '?'} evaded of ${data.ran ?? '?'}`,
      )
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Red-team failed')
    } finally {
      setMrmBusy('')
    }
  }

  async function runReset() {
    if (!confirm('Wipe red-team test injections and restore the baseline ledger?')) return
    setMrmBusy('reset')
    try {
      const data = await api<{ message?: string }>('/phase2/redteam/reset', { method: 'POST' })
      showToast(data.message || 'Dataset reset to clean baseline.')
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setMrmBusy('')
    }
  }

  async function exportCase() {
    if (!exportId) return
    try {
      const res = await fetch(`/api/alerts/${encodeURIComponent(exportId)}/export`, {
        headers: authHeaders(),
        credentials: 'same-origin',
      })
      if (!res.ok) throw new Error(await res.text() || res.statusText)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `case-${exportId}.html`
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Export failed')
    }
  }

  async function onGlobalSearch() {
    const q = search.trim()
    if (!q) return
    try {
      const rows = await api<
        Array<{ txn_id: string; sender_id?: string; receiver_id?: string }>
      >('/alerts?sort=newest')
      const hit = rows.find(
        (a) => a.txn_id === q || a.sender_id === q || a.receiver_id === q,
      )
      if (hit) {
        navigate(`/investigate/${encodeURIComponent(hit.txn_id)}`)
        return
      }
    } catch {
      /* fall through to explorer */
    }
    navigate(`/corridors?q=${encodeURIComponent(q)}`)
  }

  return (
    <div className="app-shell">
      <aside className="sidenav">
        <div className="sidenav-brand">
          <svg width="28" height="28" viewBox="0 0 48 48" fill="none" aria-hidden="true">
            <path
              d="M24 4l16 6v12c0 11.2-7.2 21.4-16 24-8.8-2.6-16-12.8-16-24V10l16-6z"
              stroke="#60A5FA"
              strokeWidth="2.2"
            />
            <circle cx="24" cy="22" r="7" stroke="#93C5FD" strokeWidth="2" />
            <circle cx="24" cy="22" r="2.4" fill="#93C5FD" />
          </svg>
          <div>
            <b>CORRIDOR WATCH</b>
            <span>Confirmed cases become Crime Pattern DNA</span>
          </div>
        </div>
        <NavLink to="/" end className={({ isActive }) => `nav-btn${isActive ? ' on' : ''}`}>
          Home
        </NavLink>
        <NavLink to="/corridors" className={({ isActive }) => `nav-btn${isActive ? ' on' : ''}`}>
          Corridor Explorer
        </NavLink>
        <NavLink to="/investigate" className={({ isActive }) => `nav-btn${isActive ? ' on' : ''}`}>
          Investigations
        </NavLink>
        <NavLink to="/patterns" className={({ isActive }) => `nav-btn${isActive ? ' on' : ''}`}>
          Pattern DNA
        </NavLink>
        <div className="sidenav-foot">
          <div>System online</div>
          <div className="ver">React console · motion</div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-meta">
            <input
              className="global-search"
              type="search"
              placeholder="Search by account, transaction, device, or identifier"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void onGlobalSearch()
              }}
            />
            <span className={`chip${health?.ok ? ' on' : ''}`}>
              gemini: {health?.gemini || '…'}
            </span>
            <span className={`chip${streamLive ? ' on' : ''}`}>{streamLabel}</span>
            {canRunStream(role) && (
              <>
                <button className="btn secondary" type="button" disabled={streamBusy} onClick={onStartStream}>
                  Start stream
                </button>
                <button className="btn secondary" type="button" disabled={streamBusy} onClick={onStopStream}>
                  Stop stream
                </button>
              </>
            )}
            {mrm && (
              <>
                <button
                  className="btn secondary"
                  type="button"
                  disabled={!!mrmBusy}
                  onClick={() => void runMrmJson('/phase2/mrm', 'MRM draft')}
                >
                  {mrmBusy === 'MRM draft' ? '…' : 'MRM draft'}
                </button>
                <button
                  className="btn secondary"
                  type="button"
                  disabled={!!mrmBusy}
                  onClick={() => void runMrmJson('/phase2/rules/mine', 'Mined rules')}
                >
                  {mrmBusy === 'Mined rules' ? '…' : 'Mined rules'}
                </button>
                <button
                  className="btn secondary"
                  type="button"
                  disabled={!!mrmBusy}
                  onClick={() => void runRedteam()}
                >
                  {mrmBusy === 'redteam' ? '…' : 'Run red-team'}
                </button>
                <button
                  className="btn secondary"
                  type="button"
                  disabled={!!mrmBusy}
                  onClick={() => void runReset()}
                >
                  {mrmBusy === 'reset' ? '…' : 'Reset dataset'}
                </button>
              </>
            )}
            <button
              className="btn secondary"
              type="button"
              disabled={!exportId}
              onClick={() => void exportCase()}
            >
              Export case
            </button>
          </div>
          <div className="topbar-meta">
            <span className="chip on">
              {session?.display_name || session?.role} · {session?.analyst_id}
            </span>
            <span
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: '#0F172A',
                color: '#fff',
                display: 'grid',
                placeItems: 'center',
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              {initials}
            </span>
            <button className="btn secondary" type="button" onClick={() => void logout()}>
              Sign out
            </button>
          </div>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </div>

      {toast && (
        <div className="shell-toast" role="status">
          {toast}
        </div>
      )}

      {panel && (
        <div
          className="shell-modal-backdrop"
          role="presentation"
          onClick={() => setPanel(null)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setPanel(null)
          }}
        >
          <div
            className="shell-modal"
            role="dialog"
            aria-modal="true"
            aria-label={panel.title}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="shell-modal-head">
              <strong>{panel.title}</strong>
              <button className="btn secondary" type="button" onClick={() => setPanel(null)}>
                Close
              </button>
            </div>
            <pre className="shell-modal-body">{panel.body}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
