import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  api,
  clearSession,
  getStoredSession,
  getToken,
  saveSession,
  type Session,
} from './api'

type AuthState = {
  session: Session | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(getStoredSession())
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setSession(null)
      setLoading(false)
      return
    }
    try {
      const me = await api<Session>('/auth/me')
      setSession(me)
      const token = getToken()
      if (token) saveSession(me, token)
    } catch {
      clearSession()
      setSession(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const data = await api<Session & { token: string }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const { token, ...rest } = data
    saveSession(rest, token)
    setSession(rest)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } catch {
      /* ignore */
    }
    clearSession()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, loading, login, logout, refresh }),
    [session, loading, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
