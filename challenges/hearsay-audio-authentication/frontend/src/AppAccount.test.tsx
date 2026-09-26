import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

const accountUser = {
  id: 'u1', email: 'analyst@example.test', name: 'Ada Analyst', avatar_url: null, created_at: '2026-09-01T12:00:00Z',
  has_password: true, google_linked: true, email_verified: true,
}

function stubServer({ accounts, preferences }: { accounts: boolean; preferences?: Record<string, unknown> }) {
  const fetcher = vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/api/auth/me') return Promise.resolve(accounts ? json({ user: accountUser }) : json({ detail: 'Not Found' }, 404))
    if (path === '/api/analyses') return Promise.resolve(json([]))
    if (path === '/api/health') return Promise.resolve(json({ status: 'ok' }))
    if (path === '/api/account/preferences') return Promise.resolve(json({ preferences: {
      ai_interpretation: true, default_view: 'investigation', time_format: '12h', motion: 'system', ...preferences,
    } }))
    if (path === '/api/account') return Promise.resolve(json({ user: accountUser, preferences: {}, active_sessions: 1, recordings: 0 }))
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('account integration', () => {
  it('hides all account UI when the server runs without accounts', async () => {
    const fetcher = stubServer({ accounts: false })
    render(<App />)
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith('/api/auth/me', undefined))
    expect(await screen.findByText('Local processing available')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Your account' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Log out' })).not.toBeInTheDocument()
    expect(fetcher.mock.calls.some(([input]) => String(input).startsWith('/api/account'))).toBe(false)
    expect(screen.getByRole('heading', { name: /Every recording deserves/ })).toBeInTheDocument()
  })

  it('shows the signed-in account and opens profile and settings in the main column', async () => {
    stubServer({ accounts: true })
    const user = userEvent.setup()
    render(<App />)
    const block = await screen.findByRole('region', { name: 'Your account' })
    expect(within(block).getByText('Ada Analyst')).toBeInTheDocument()
    expect(within(block).getByText('analyst@example.test')).toBeInTheDocument()
    expect(within(block).getByText('AA')).toBeInTheDocument()

    await user.click(within(block).getByRole('button', { name: 'Profile' }))
    expect(await screen.findByRole('heading', { name: 'Your profile' })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    expect(await screen.findByRole('heading', { name: 'Settings', level: 1 })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Workspace' }))
    expect(await screen.findByRole('heading', { name: /Every recording deserves/ })).toBeInTheDocument()
  })

  it('opens Batch & export first and forces reduced motion when preferences ask for it', async () => {
    stubServer({ accounts: true, preferences: { default_view: 'batch', motion: 'reduce' } })
    const { unmount } = render(<App />)
    expect(await screen.findByRole('heading', { name: 'Batch & export' })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('motion-reduced')
    unmount()
    expect(document.documentElement).not.toHaveClass('motion-reduced')
  })
})
