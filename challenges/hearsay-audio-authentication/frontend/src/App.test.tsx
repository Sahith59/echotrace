import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/api/analyses') return Promise.resolve(jsonResponse([]))
    if (path === '/api/health') return Promise.resolve(jsonResponse({ status: 'ok' }))
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('mobile navigation', () => {
  it('moves focus into the drawer, contains keyboard focus, and restores the opener on Escape', async () => {
    const user = userEvent.setup()
    render(<App />)
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/health', undefined))

    const opener = screen.getByRole('button', { name: 'Open navigation' })
    await user.click(opener)

    const drawer = screen.getByRole('dialog', { name: 'Analysis history' })
    const close = screen.getByRole('button', { name: 'Close navigation' })
    const drawerAdd = screen.getAllByRole('button', { name: 'Add recording' })[0]
    expect(drawer).toHaveAttribute('aria-modal', 'true')
    expect(close).toHaveFocus()

    await user.tab({ shift: true })
    expect(drawerAdd).toHaveFocus()
    await user.tab()
    expect(close).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Analysis history' })).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('closes coherently after navigation and restores access to the page', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<App />)
    const opener = screen.getByRole('button', { name: 'Open navigation' })
    await user.click(opener)
    await user.click(screen.getByRole('button', { name: /Batch & export/ }))

    expect(screen.queryByRole('dialog', { name: 'Analysis history' })).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Batch & export' })).toBeInTheDocument()
    expect(opener).toHaveFocus()
    expect(document.querySelector('.main-column')).not.toHaveAttribute('inert')
    expect(screen.getByRole('complementary', { name: 'Analysis history' })).toBeInTheDocument()

    await user.click(opener)
    unmount()
    expect(document.body).not.toHaveStyle({ overflow: 'hidden' })
  })

  it('closes the drawer when the viewport changes to desktop and removes its listener on unmount', async () => {
    const user = userEvent.setup()
    let onChange: ((event: MediaQueryListEvent) => void) | undefined
    const removeEventListener = vi.fn()
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: true,
      media: '(max-width: 800px)',
      onchange: null,
      addEventListener: vi.fn((_type: string, listener: (event: MediaQueryListEvent) => void) => { onChange = listener }),
      removeEventListener,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))

    const { unmount } = render(<App />)
    await user.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getByRole('dialog', { name: 'Analysis history' })).toBeInTheDocument()
    onChange?.({ matches: false } as MediaQueryListEvent)

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Analysis history' })).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Open navigation' })).toHaveFocus()
    expect(document.querySelector('.main-column')).not.toHaveAttribute('inert')
    unmount()
    expect(removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })
})
