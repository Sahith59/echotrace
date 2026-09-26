import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type User = {
  id: string
  name: string
  email: string
  avatar_url: string | null
  created_at: string
  has_password: boolean
  google_linked: boolean
  email_verified: boolean
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new Error('Cannot reach the ECHOTRACE server. Check that it is running and try again.')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : `The request failed (${response.status}). Try again.`)
  }
  return data as T
}

type Session = {
  user: User | null
  notice: string | null
  signup: (input: { name: string; email: string; password: string }) => Promise<User>
  login: (input: { email: string; password: string }) => Promise<User>
  logout: () => Promise<void>
  clearNotice: () => void
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    fetch('/api/auth/me')
      .then(response => response.json())
      .then(data => { if (live) setUser(data?.user ?? null) })
      .catch(() => { if (live) setUser(null) })
    return () => { live = false }
  }, [])

  const signup = useCallback(async (input: { name: string; email: string; password: string }) => {
    const { user: created } = await postJson<{ user: User }>('/api/auth/signup', input)
    setUser(created)
    setNotice(`Account created. Welcome, ${created.name}.`)
    return created
  }, [])

  const login = useCallback(async (input: { email: string; password: string }) => {
    const { user: signedIn } = await postJson<{ user: User }>('/api/auth/login', input)
    setUser(signedIn)
    setNotice(`Signed in as ${signedIn.name}.`)
    return signedIn
  }, [])

  const logout = useCallback(async () => {
    await postJson('/api/auth/logout', {})
    setUser(null)
    setNotice('Signed out.')
  }, [])

  const value = useMemo(() => ({ user, notice, signup, login, logout, clearNotice: () => setNotice(null) }),
    [user, notice, signup, login, logout])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside SessionProvider')
  return session
}
