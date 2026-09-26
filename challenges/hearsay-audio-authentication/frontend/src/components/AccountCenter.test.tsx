import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AccountCenter, { type AccountTab } from './AccountCenter'
import type { AccountUser, Preferences } from '@/lib/account'

const baseUser: AccountUser = {
  id: 'u1', email: 'analyst@example.test', name: 'Ada Analyst', avatar_url: null, created_at: '2026-09-01T12:00:00Z',
  has_password: true, google_linked: false, email_verified: true,
}
const basePreferences: Preferences = { ai_interpretation: true, default_view: 'investigation', time_format: '12h', motion: 'system' }

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

type Route = (init?: RequestInit) => Response
function stubRoutes(routes: Record<string, Route>) {
  const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/api/account' && !routes[path]) return Promise.resolve(json({ user: baseUser, preferences: basePreferences, active_sessions: 2, recordings: 5 }))
    const route = routes[path]
    return route ? Promise.resolve(route(init)) : Promise.reject(new Error(`Unexpected request: ${path}`))
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}
function bodyOf(fetcher: ReturnType<typeof stubRoutes>, path: string) {
  const call = fetcher.mock.calls.find(([input]) => String(input) === path)
  return call ? JSON.parse(call[1]?.body as string) : undefined
}

function renderCenter(tab: AccountTab, overrides: Partial<Parameters<typeof AccountCenter>[0]> = {}) {
  const props = {
    user: baseUser, tab, preferences: basePreferences, onTabChange: vi.fn(), onBack: vi.fn(),
    onUserChange: vi.fn(), onPreferencesChange: vi.fn(), onRecordingsDeleted: vi.fn(), ...overrides,
  }
  render(<AccountCenter {...props} />)
  return props
}

const { assign } = vi.hoisted(() => ({ assign: vi.fn() }))
vi.mock('@/lib/navigate', () => ({ goTo: assign }))
beforeEach(() => { assign.mockReset() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('profile', () => {
  it('shows account facts and saves an edited display name', async () => {
    const updated = { ...baseUser, name: 'Ada Lovelace' }
    const fetcher = stubRoutes({ '/api/account/profile': () => json({ user: updated }) })
    const props = renderCenter('profile')
    const user = userEvent.setup()

    expect(await screen.findByText('5')).toBeInTheDocument()
    expect(screen.getByText('Not linked')).toBeInTheDocument()
    const name = screen.getByLabelText('Display name')
    await user.clear(name)
    await user.type(name, 'Ada Lovelace')
    await user.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByText('Name saved.')).toBeInTheDocument()
    expect(bodyOf(fetcher, '/api/account/profile')).toEqual({ name: 'Ada Lovelace' })
    expect(fetcher.mock.calls.find(([input]) => String(input) === '/api/account/profile')?.[1]?.method).toBe('PATCH')
    expect(props.onUserChange).toHaveBeenCalledWith(updated)
  })

  it('shows the server validation message next to the name field', async () => {
    stubRoutes({ '/api/account/profile': () => json({ detail: 'Name is too long.' }, 422) })
    renderCenter('profile')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Display name'), 'x')
    await user.click(screen.getByRole('button', { name: 'Save name' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Name is too long.')
  })

  it('labels a Google-only account as setting a password and omits the current password', async () => {
    const fetcher = stubRoutes({ '/api/account/password': () => json({ changed: true }) })
    const props = renderCenter('profile', { user: { ...baseUser, has_password: false, google_linked: true } })
    const user = userEvent.setup()

    expect(screen.getByRole('heading', { name: 'Set a password' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('New password'), 'long-enough-pass')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    expect(await screen.findByText(/Password set/)).toBeInTheDocument()
    expect(bodyOf(fetcher, '/api/account/password')).toEqual({ new: 'long-enough-pass' })
    expect(props.onUserChange).toHaveBeenCalledWith(expect.objectContaining({ has_password: true }))
  })

  it('asks for the current password when changing it and shows a wrong-password error', async () => {
    const fetcher = stubRoutes({ '/api/account/password': () => json({ detail: 'Current password is incorrect.' }, 403) })
    renderCenter('profile')
    const user = userEvent.setup()

    expect(screen.getByRole('heading', { name: 'Change password' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Current password'), 'wrong-password')
    await user.type(screen.getByLabelText('New password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 10 characters')
    expect(bodyOf(fetcher, '/api/account/password')).toBeUndefined()

    await user.click(screen.getByRole('button', { name: 'Show passwords' }))
    expect(screen.getByLabelText('New password')).toHaveAttribute('type', 'text')
    await user.type(screen.getByLabelText('New password'), '-now-long-enough')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect.')
    expect(bodyOf(fetcher, '/api/account/password')).toEqual({ current: 'wrong-password', new: 'short-now-long-enough' })
  })

  it('signs out other devices and reports how many sessions ended', async () => {
    stubRoutes({ '/api/account/sessions/revoke-others': () => json({ revoked: 2 }) })
    renderCenter('profile')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sign out of other devices' }))
    expect(await screen.findByText('Signed out of 2 other sessions.')).toBeInTheDocument()
  })
})

describe('settings', () => {
  it('sends only the changed preference and reports the saved state upward', async () => {
    const saved = { ...basePreferences, ai_interpretation: false }
    const fetcher = stubRoutes({ '/api/account/preferences': () => json({ preferences: saved }) })
    const props = renderCenter('settings')
    await userEvent.setup().click(screen.getByRole('checkbox', { name: 'Allow AI interpretation' }))

    await vi.waitFor(() => expect(props.onPreferencesChange).toHaveBeenCalledWith(saved))
    const call = fetcher.mock.calls.find(([input]) => String(input) === '/api/account/preferences')
    expect(call?.[1]?.method).toBe('PATCH')
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({ ai_interpretation: false })
  })

  it('saves the default view selection and shows an error next to a failed control', async () => {
    const fetcher = stubRoutes({ '/api/account/preferences': () => json({ detail: 'Unsupported value.' }, 422) })
    renderCenter('settings')
    await userEvent.setup().selectOptions(screen.getByLabelText('Open the app in'), 'batch')
    expect(bodyOf(fetcher, '/api/account/preferences')).toEqual({ default_view: 'batch' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Not saved: Unsupported value.')
  })

  it('requires typed DELETE before deleting all recordings', async () => {
    const fetcher = stubRoutes({ '/api/account/recordings/delete': () => json({ deleted: 3 }) })
    const props = renderCenter('settings')
    const user = userEvent.setup()
    const section = screen.getByRole('region', { name: 'Export and remove' })
    const button = within(section).getByRole('button', { name: 'Delete all recordings' })
    expect(button).toBeDisabled()

    await user.type(within(section).getByLabelText('Type DELETE to confirm'), 'delete')
    expect(button).toBeDisabled()
    await user.clear(within(section).getByLabelText('Type DELETE to confirm'))
    await user.type(within(section).getByLabelText('Type DELETE to confirm'), 'DELETE')
    await user.click(button)

    expect(await within(section).findByText('Deleted 3 recordings.')).toBeInTheDocument()
    expect(bodyOf(fetcher, '/api/account/recordings/delete')).toEqual({ confirm: 'DELETE' })
    expect(props.onRecordingsDeleted).toHaveBeenCalled()
    expect(bodyOf(fetcher, '/api/account/delete')).toBeUndefined()
  })

  it('requires typed DELETE before deleting the account, then returns to the home page', async () => {
    const fetcher = stubRoutes({ '/api/account/delete': () => json({ deleted: true }) })
    renderCenter('settings')
    const user = userEvent.setup()
    const section = screen.getByRole('region', { name: 'Delete account' })
    const button = within(section).getByRole('button', { name: 'Delete account' })
    expect(button).toBeDisabled()

    await user.type(within(section).getByLabelText('Type DELETE to confirm'), 'DELETE')
    await user.click(button)

    await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('/'))
    expect(bodyOf(fetcher, '/api/account/delete')).toEqual({ confirm: 'DELETE' })
    expect(bodyOf(fetcher, '/api/account/recordings/delete')).toBeUndefined()
  })
})
