import { describe, expect, it, vi } from 'vitest'
import { installAuthRedirect, loginPath, needsSignIn } from './auth-redirect'

const ORIGIN = 'https://echotrace.test'

function fakeWindow(status: number) {
  const assign = vi.fn()
  const fetchMock = vi.fn(() => Promise.resolve(new Response('{}', { status })))
  const target = {
    fetch: fetchMock as unknown as typeof fetch,
    location: { origin: ORIGIN, pathname: '/app/', search: '?view=batch', hash: '#queue', assign } as unknown as Location,
  }
  return { target, assign, fetchMock }
}

describe('needsSignIn', () => {
  it('flags 401 responses from same-origin product API routes', () => {
    expect(needsSignIn('/api/analyses', 401, ORIGIN)).toBe(true)
    expect(needsSignIn(new URL('/api/account', ORIGIN), 401, ORIGIN)).toBe(true)
    expect(needsSignIn(new Request(`${ORIGIN}/api/exports`), 401, ORIGIN)).toBe(true)
  })

  it('ignores the session probe, other statuses, non-API paths and other origins', () => {
    expect(needsSignIn('/api/auth/me', 401, ORIGIN)).toBe(false)
    expect(needsSignIn('/api/analyses', 403, ORIGIN)).toBe(false)
    expect(needsSignIn('/textures/soft-atmosphere.png', 401, ORIGIN)).toBe(false)
    expect(needsSignIn('https://api.groq.com/api/analyses', 401, ORIGIN)).toBe(false)
  })
})

describe('installAuthRedirect', () => {
  it('builds the login path with the full current location encoded', () => {
    expect(loginPath({ pathname: '/app/', search: '?view=batch', hash: '#queue' })).toBe('/login?next=%2Fapp%2F%3Fview%3Dbatch%23queue')
  })

  it('redirects to login on a 401 and still returns the response', async () => {
    const { target, assign } = fakeWindow(401)
    installAuthRedirect(target)
    const response = await target.fetch('/api/analyses')
    expect(response.status).toBe(401)
    expect(assign).toHaveBeenCalledWith('/login?next=%2Fapp%2F%3Fview%3Dbatch%23queue')
  })

  it('does not redirect when the session probe returns 401 or a product call succeeds', async () => {
    const unauthorized = fakeWindow(401)
    installAuthRedirect(unauthorized.target)
    await unauthorized.target.fetch('/api/auth/me')
    expect(unauthorized.assign).not.toHaveBeenCalled()

    const ok = fakeWindow(200)
    installAuthRedirect(ok.target)
    await ok.target.fetch('/api/analyses', { method: 'GET' })
    expect(ok.assign).not.toHaveBeenCalled()
    expect(ok.fetchMock).toHaveBeenCalledWith('/api/analyses', { method: 'GET' })
  })

  it('restores the original fetch when uninstalled', () => {
    const { target, fetchMock } = fakeWindow(200)
    const uninstall = installAuthRedirect(target)
    expect(target.fetch).not.toBe(fetchMock)
    uninstall()
    expect(target.fetch).toBe(fetchMock)
  })
})
