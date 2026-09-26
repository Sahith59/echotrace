import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App, { intervalTime } from './App'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
}

const niiModel = {
  name: 'NII wav2vec-small-anti-deepfake', version: '9a13264b',
  weights_sha256: 'a'.repeat(64), config_sha256: 'b'.repeat(64),
}

function completedResult(score: number | null, model = niiModel) {
  return {
    schema_version: '1.1', input: { filename: 'recording.wav', duration_s: 8, sha256: 'c'.repeat(64) },
    synthetic_score: score, score_kind: 'uncalibrated', model, waveform: [], intervals: [],
    evidence: [], limitations: ['Public benchmark only.'], runtime_s: 1,
  }
}

function workspaceFetch(jobs: unknown[], exportFailure?: string) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    if (path === '/api/analyses') return Promise.resolve(jsonResponse(jobs))
    if (path === '/api/health') return Promise.resolve(jsonResponse({ status: 'ok' }))
    if (path === '/api/model/evaluation') return Promise.resolve(jsonResponse({
      scope: 'Public benchmark.', serving_model: niiModel.name, experiments: [], serving_benchmarks: [],
    }))
    if (path === '/api/interpretation/status') return Promise.resolve(jsonResponse({ available: false, reason: 'Not configured.' }))
    if (path.endsWith('/interpretation')) return Promise.resolve(jsonResponse({ status: 'not_generated' }))
    if (path === '/api/speaker/status') return Promise.resolve(jsonResponse({ available: false, ready: false }))
    if (path === '/api/claims/status') return Promise.resolve(jsonResponse({
      provider: { available: false, reason: 'Hosted search disabled.' }, transcription: { available: false },
    }))
    if (path.endsWith('/speaker-comparison')) return Promise.resolve(new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 }))
    if (path.endsWith('/transcript')) return Promise.resolve(jsonResponse({ status: 'not_generated', versions: [] }))
    if (path.endsWith('/claims')) return Promise.resolve(jsonResponse({ claims: [] }))
    if (path.endsWith('/analyst-review')) return Promise.resolve(jsonResponse({ status: 'needs_review', notes: '', version: 0, updated_at: null }))
    if (path === '/api/exports' && init?.method === 'POST') return Promise.resolve(
      exportFailure
        ? new Response(JSON.stringify({ detail: exportFailure }), { status: 409, headers: { 'Content-Type': 'application/json' } })
        : new Response('file_id,filename,synthetic_score\n'),
    )
    return Promise.reject(new Error(`Unexpected request: ${path}`))
  })
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

describe('scored interval time labels', () => {
  it('keeps overlapping windows distinguishable without changing the playback clock', () => {
    expect(intervalTime(4.0375)).toBe('00:04.04')
    expect(intervalTime(4.4625)).toBe('00:04.46')
    expect(intervalTime(8.5)).toBe('00:08.50')
  })
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

describe('initial connection state', () => {
  it('does not report a server failure before the first health request finishes', async () => {
    let resolveHealth!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input) === '/api/health') return new Promise<Response>(resolve => { resolveHealth = resolve })
      return Promise.resolve(jsonResponse([]))
    }))
    render(<App />)
    expect(screen.getByText('Connecting to local server')).toBeInTheDocument()
    expect(screen.queryByText('Server unavailable')).not.toBeInTheDocument()
    resolveHealth(jsonResponse({ status: 'ok' }))
    expect(await screen.findByText('Local processing available')).toBeInTheDocument()
  })
})

describe('analyst workspace journey', () => {
  it('keeps failed and unscored recordings visible while filtering, and labels their models honestly', async () => {
    const now = new Date()
    const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1)
    const jobs = [
      { id: 'nii', filename: 'nii-result.wav', status: 'completed', stage: 'completed', created_at: now.toISOString(), result: completedResult(.72), error: null, analyst_review: { status: 'review_complete', notes: '', version: 1 } },
      { id: 'unscored', filename: 'unscored.wav', status: 'completed', stage: 'completed', created_at: now.toISOString(), result: completedResult(null), error: null, analyst_review: { status: 'needs_review', notes: '', version: 0 } },
      { id: 'failed', filename: 'failed.wav', status: 'failed', stage: 'failed', created_at: yesterday.toISOString(), result: null, error: 'Primary detector unavailable.', analyst_review: { status: 'needs_review', notes: '', version: 0 } },
    ]
    vi.stubGlobal('fetch', workspaceFetch(jobs))
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Batch & export/ }))
    await screen.findByRole('heading', { name: 'Batch & export' })
    const table = screen.getByRole('table')

    expect(within(table).getByText('nii-result.wav')).toBeInTheDocument()
    expect(within(table).getByText('unscored.wav')).toBeInTheDocument()
    expect(within(table).getByText('failed.wav')).toBeInTheDocument()
    expect(within(table).getAllByText(niiModel.name)).toHaveLength(2)
    expect(within(table).getByText('No model result')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Select unscored.wav' })).toBeDisabled()

    await user.selectOptions(screen.getByLabelText('Analysis'), 'failed')
    expect(within(table).getByText('failed.wav')).toBeInTheDocument()
    expect(within(table).queryByText('nii-result.wav')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Analysis'), 'completed')
    expect(within(table).getByText('unscored.wav')).toBeInTheDocument()

    await user.click(screen.getByText('Date added'))
    const todayLabel = now.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    await user.click(screen.getByRole('button', { name: todayLabel }))
    expect(screen.getByRole('status')).toHaveTextContent('2 of 3 recordings')
    expect(within(table).getByText('unscored.wav')).toBeInTheDocument()
    expect(within(table).queryByText('failed.wav')).not.toBeInTheDocument()
  })

  it('shows the backend mixed-model rejection without discarding the selected batch', async () => {
    const legacy = { name: 'AASIST-L', version: 'legacy', weights_sha256: 'd'.repeat(64), config_sha256: 'e'.repeat(64) }
    const jobs = [
      { id: 'nii', filename: 'new.wav', status: 'completed', stage: 'completed', created_at: '2026-09-26T15:00:00Z', result: completedResult(.8), error: null },
      { id: 'old', filename: 'old.wav', status: 'completed', stage: 'completed', created_at: '2026-09-26T14:00:00Z', result: completedResult(.2, legacy), error: null },
    ]
    const reason = 'CSV export requires every recording to use the same identified model.'
    vi.stubGlobal('fetch', workspaceFetch(jobs, reason))
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Batch & export/ }))
    await screen.findByRole('heading', { name: 'Batch & export' })
    await user.click(screen.getByRole('checkbox', { name: 'Select new.wav' }))
    await user.click(screen.getByRole('checkbox', { name: 'Select old.wav' }))
    await user.click(screen.getByRole('button', { name: 'Export selected CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(reason)
    expect(screen.getByText('2 selected for export')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Select new.wav' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Select old.wav' })).toBeChecked()
  })

  it('switches case steps without exposing other panels or losing an analyst draft', async () => {
    const jobs = [{ id: 'case', filename: 'case.wav', status: 'completed', stage: 'completed', created_at: '2026-09-26T15:00:00Z', result: completedResult(.61), error: null }]
    vi.stubGlobal('fetch', workspaceFetch(jobs))
    const user = userEvent.setup()
    render(<App />)
    await user.click((await screen.findAllByRole('button', { name: /case\.wav/ }))[0])
    const steps = await screen.findByRole('navigation', { name: 'Investigation steps' })
    expect(screen.getByRole('heading', { name: 'Audio timeline' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Record the next step' })).not.toBeInTheDocument()

    await user.click(within(steps).getByRole('button', { name: /Case evidence/ }))
    const notes = await screen.findByLabelText('Analyst notes')
    await user.type(notes, 'Verify against the original source.')
    expect(screen.queryByRole('heading', { name: 'Audio timeline' })).not.toBeInTheDocument()

    await user.click(within(steps).getByRole('button', { name: /Check reliability/ }))
    expect(screen.getByRole('heading', { name: 'Measurement limitations' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Record the next step' })).not.toBeInTheDocument()
    await user.click(within(steps).getByRole('button', { name: /Case evidence/ }))
    expect(await screen.findByLabelText('Analyst notes')).toHaveValue('Verify against the original source.')
  })

  it('does not present a completed stress child from another model as a numeric comparison', async () => {
    const changedWeights = { ...niiModel, weights_sha256: 'f'.repeat(64) }
    const jobs = [
      { id: 'original', filename: 'original.wav', status: 'completed', stage: 'completed', created_at: '2026-09-26T15:00:00Z', result: completedResult(.4), error: null },
      { id: 'child', filename: 'original-noise.wav', status: 'completed', stage: 'completed', created_at: '2026-09-26T15:01:00Z', parent_id: 'original', transform: { kind: 'noise' }, result: completedResult(.9, changedWeights), error: null },
    ]
    vi.stubGlobal('fetch', workspaceFetch(jobs))
    const user = userEvent.setup()
    render(<App />)
    await user.click((await screen.findAllByRole('button', { name: /original\.wav/ }))[0])
    const steps = await screen.findByRole('navigation', { name: 'Investigation steps' })
    await user.click(within(steps).getByRole('button', { name: /Check reliability/ }))
    expect(await screen.findByText(/different model.*not comparable/i)).toBeInTheDocument()
    expect(screen.queryByText('Original 40% → derived 90%')).not.toBeInTheDocument()
    expect(screen.queryByText('+50 pts')).not.toBeInTheDocument()
  })
})
