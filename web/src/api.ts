export type Session = {
  analyst_id: string
  role: string
  display_name: string
  permissions?: string[]
  token?: string
}

const TOKEN_KEY = 'cw_token'
const SESSION_KEY = 'cw_session'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

export function saveSession(session: Session, token: string) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(SESSION_KEY)
}

export function authHeaders(extra: Record<string, string> = {}): HeadersInit {
  const token = getToken()
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: 'same-origin',
  })
  const text = await res.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  if (!res.ok) {
    const msg =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : typeof body === 'string'
          ? body
          : res.statusText
    throw new ApiError(res.status, msg || `HTTP ${res.status}`)
  }
  return body as T
}

export function isFiu(role: string) {
  return role === 'fiu_lead'
}

export function isMrm(role: string) {
  return role === 'mrm_auditor'
}

export function canRunStream(role: string) {
  return isFiu(role) || isMrm(role)
}
