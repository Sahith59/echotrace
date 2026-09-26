import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AIInterpretation from './AIInterpretation'

const status = { available: true, provider: 'groq', model: 'openai/gpt-oss-120b', reason: null }
const generated = {
  status: 'generated', provider: 'groq', model: 'openai/gpt-oss-120b', prompt_version: '1',
  evidence_sha256: 'abc', generated_at: '2026-09-25T12:00:00Z',
  report: {
    summary: 'Review the uncertain acoustic pattern.',
    findings: [{ text: 'One metric is elevated.', evidence_ids: ['energy'] }],
    next_steps: ['Listen to the flagged interval.'],
  },
  evidence: [
    { id: 'energy', label: 'Spectral energy', value: 0.82, unit: 'ratio' },
    { id: 'window_001', label: 'Review window', value: { start_s: 1.25, end_s: 2.75, score: 0.81 } },
  ],
}
const response = (body: unknown, code = 200) => new Response(JSON.stringify(body), {
  status: code, headers: { 'Content-Type': 'application/json' },
})
const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('AIInterpretation', () => {
  it('loads cached interpretation without generating and shows cited measurement values', async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith('/status') ? status : generated,
    )))
    render(<AIInterpretation jobId="job-a" />)
    expect(await screen.findByText('Review the uncertain acoustic pattern.')).toBeInTheDocument()
    expect(screen.getByText('One metric is elevated.')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByText('Measurement references'))
    expect(screen.getByText(/Spectral energy/)).toBeInTheDocument()
    expect(screen.getByText(/0\.82/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/analyses/job-a/interpretation', expect.objectContaining({ method: 'POST' }))
  })

  it('offers on-demand generation and shows a busy state until it finishes', async () => {
    let resolvePost!: (value: Response) => void
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/status')) return Promise.resolve(response(status))
      if (init?.method === 'POST') return new Promise<Response>(resolve => { resolvePost = resolve })
      return Promise.resolve(response({ status: 'not_generated' }))
    })
    render(<AIInterpretation jobId="job-a" />)
    const user = userEvent.setup()
    const button = await screen.findByRole('button', { name: /generate interpretation/i })
    expect(screen.getByText(/on demand/i)).toBeInTheDocument()
    await user.click(button)
    expect(screen.getByRole('button', { name: /generating interpretation/i })).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledWith('/api/analyses/job-a/interpretation', expect.objectContaining({ method: 'POST' }))
    resolvePost(response(generated))
    expect(await screen.findByText('Review the uncertain acoustic pattern.')).toBeInTheDocument()
  })

  it('explains when the provider is unavailable', async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith('/status') ? { ...status, available: false, reason: 'Groq key is missing' } : { status: 'not_generated' },
    )))
    render(<AIInterpretation jobId="job-a" />)
    expect(await screen.findByText(/Groq key is missing/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /generate interpretation/i })).not.toBeInTheDocument()
  })

  it('rechecks configuration after the provider becomes available', async () => {
    let checks = 0
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(
      url.endsWith('/status')
        ? (++checks === 1 ? { ...status, available: false, reason: 'Groq key is missing' } : status)
        : { status: 'not_generated' },
    )))
    render(<AIInterpretation jobId="job-a" />)
    expect(await screen.findByText(/Groq key is missing/)).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: /check configuration/i }))
    expect(await screen.findByRole('button', { name: /generate interpretation/i })).toBeInTheDocument()
  })

  it('renders a structured review window as time and score', async () => {
    const windowReport = {
      ...generated,
      report: { ...generated.report, findings: [{ text: 'Review this window.', evidence_ids: ['window_001'] }] },
    }
    fetchMock.mockImplementation((url: string) => Promise.resolve(response(url.endsWith('/status') ? status : windowReport)))
    render(<AIInterpretation jobId="job-a" />)
    await userEvent.setup().click(await screen.findByText('Measurement references'))
    expect(screen.getByText(/1\.25.*2\.75.*0\.81/)).toBeInTheDocument()
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
  })

  it('shows a generation error and permits retry', async () => {
    let posts = 0
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/status')) return Promise.resolve(response(status))
      if (init?.method === 'POST') return Promise.resolve(++posts === 1 ? response({ detail: 'Model timed out' }, 503) : response(generated))
      return Promise.resolve(response({ status: 'not_generated' }))
    })
    render(<AIInterpretation jobId="job-a" />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /generate interpretation/i }))
    expect(await screen.findByText('Model timed out')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry interpretation/i }))
    expect(await screen.findByText('Review the uncertain acoustic pattern.')).toBeInTheDocument()
    expect(posts).toBe(2)
  })

  it('can retry loading after a temporary API error', async () => {
    let statusCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/status')) return Promise.resolve(++statusCalls === 1 ? response({ detail: 'Status unavailable' }, 503) : response(status))
      return Promise.resolve(response({ status: 'not_generated' }))
    })
    render(<AIInterpretation jobId="job-a" />)
    expect(await screen.findByText('Status unavailable')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: /retry loading interpretation/i }))
    expect(await screen.findByRole('button', { name: /generate interpretation/i })).toBeInTheDocument()
  })

  it('does not show a previous job response after switching jobs', async () => {
    let resolveOld!: (value: Response) => void
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/status')) return Promise.resolve(response(status))
      if (url.includes('job-a')) return new Promise<Response>(resolve => { resolveOld = resolve })
      return Promise.resolve(response({ status: 'not_generated' }))
    })
    const view = render(<AIInterpretation jobId="job-a" />)
    await waitFor(() => expect(resolveOld).toBeDefined())
    view.rerender(<AIInterpretation jobId="job-b" />)
    expect(await screen.findByRole('button', { name: /generate interpretation/i })).toBeInTheDocument()
    resolveOld(response(generated))
    await waitFor(() => expect(screen.queryByText('Review the uncertain acoustic pattern.')).not.toBeInTheDocument())
  })
})
