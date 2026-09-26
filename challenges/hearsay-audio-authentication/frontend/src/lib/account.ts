import { goTo } from './navigate'

export type AccountUser = {
  id: string
  email: string
  name: string
  avatar_url: string | null
  created_at: string
  has_password: boolean
  google_linked: boolean
  email_verified: boolean
}

export type Preferences = {
  ai_interpretation: boolean
  default_view: 'investigation' | 'batch'
  time_format: '12h' | '24h'
  motion: 'system' | 'reduce'
}

export type ActiveSession = { id?: string; current?: boolean; created_at?: string; last_seen_at?: string; user_agent?: string | null }

export type AccountSummary = {
  user: AccountUser
  preferences: Preferences
  active_sessions: number | ActiveSession[]
  recordings: number | unknown[]
}

export type AccountState =
  | { status: 'checking' }
  | { status: 'disabled' }
  | { status: 'signed-out' }
  | { status: 'signed-in'; user: AccountUser }

export class AccountRequestError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

export async function accountRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(path, init) }
  catch { throw new AccountRequestError('Cannot reach the server. Check your connection and try again.', 0) }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`
    throw new AccountRequestError(detail, response.status)
  }
  return response.json() as Promise<T>
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH', body: unknown): Promise<T> {
  return accountRequest<T>(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export async function loadAccountState(): Promise<AccountState> {
  try {
    const { user } = await accountRequest<{ user: AccountUser | null }>('/api/auth/me')
    return user ? { status: 'signed-in', user } : { status: 'signed-out' }
  } catch {
    return { status: 'disabled' }
  }
}

export async function logOut(): Promise<void> {
  await accountRequest('/api/auth/logout', { method: 'POST' })
  goTo('/')
}

export function countOf(value: number | unknown[] | undefined): number {
  if (Array.isArray(value)) return value.length
  return typeof value === 'number' ? value : 0
}

export function initials(user: Pick<AccountUser, 'name' | 'email'>): string {
  const source = user.name.trim() || user.email
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2)).toUpperCase()
}
