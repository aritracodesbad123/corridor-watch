import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { api, canRunStream } from './api'
import { AuthProvider, useAuth } from './auth'
import { Shell } from './components/Shell'
import { CorridorsView } from './views/CorridorsView'
import { HomeView } from './views/HomeView'
import { InvestigateView } from './views/InvestigateView'
import { LoginView } from './views/LoginView'
import { PatternsView } from './views/PatternsView'

function AuthenticatedApp() {
  const { session } = useAuth()
  const [health, setHealth] = useState<{ gemini?: string; gemini_model?: string; ok?: boolean } | null>(
    null,
  )
  const [stream, setStream] = useState<Record<string, unknown> | null>(null)
  const [streamBusy, setStreamBusy] = useState(false)

  const refreshStream = useCallback(async () => {
    try {
      const s = await api<Record<string, unknown>>('/simulate')
      setStream(s)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    void api<{ gemini?: string; gemini_model?: string; ok?: boolean }>('/health')
      .then((h) =>
        setHealth({
          ok: h.ok,
          gemini: h.gemini_model || h.gemini || 'ready',
        }),
      )
      .catch(() => setHealth({ ok: false, gemini: 'down' }))
    void refreshStream()
    const t = setInterval(() => void refreshStream(), 4000)
    return () => clearInterval(t)
  }, [refreshStream])

  const running = Boolean(stream?.running)
  const mins = Math.max(0, Math.floor(Number(stream?.remaining_seconds || 0) / 60))
  const streamLabel = running
    ? `stream: LIVE ${mins}m · flagged ${stream?.queued_for_investigation ?? 0}`
    : 'stream: idle'

  async function startStream() {
    if (!canRunStream(session?.role || '')) return
    setStreamBusy(true)
    try {
      const s = await api<Record<string, unknown>>('/simulate/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rate: 8,
          duration_seconds: 3600,
          scenario_mix: 'live',
          force: true,
        }),
      })
      setStream(s)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Start failed')
    } finally {
      setStreamBusy(false)
    }
  }

  async function stopStream() {
    setStreamBusy(true)
    try {
      const s = await api<Record<string, unknown>>('/simulate/stop', { method: 'POST' })
      setStream(s)
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Stop failed')
    } finally {
      setStreamBusy(false)
    }
  }

  return (
    <Routes>
      <Route
        element={
          <Shell
            health={health}
            streamLabel={streamLabel}
            streamLive={running}
            streamBusy={streamBusy}
            onStartStream={() => void startStream()}
            onStopStream={() => void stopStream()}
          />
        }
      >
        <Route index element={<HomeView />} />
        <Route path="corridors" element={<CorridorsView />} />
        <Route path="investigate" element={<InvestigateView />} />
        <Route path="investigate/:txnId" element={<InvestigateView />} />
        <Route path="patterns" element={<PatternsView />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function Gate() {
  const { session, loading } = useAuth()
  if (loading) {
    return (
      <div className="login-page">
        <p className="muted">Restoring session…</p>
      </div>
    )
  }
  if (!session) return <LoginView />
  return <AuthenticatedApp />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Gate />
      </BrowserRouter>
    </AuthProvider>
  )
}
