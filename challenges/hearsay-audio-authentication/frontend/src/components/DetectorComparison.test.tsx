import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DetectorComparison from './DetectorComparison'

const report = { status: 'generated', primary_score: .09, candidate_score: .98,
  primary_model: { name: 'AASIST-L' }, model: { name: 'NII candidate', weights_sha256: 'abc' },
  experimental: true, limitation: 'Not validated on sponsor data.', input_sha256: 'file-hash' }
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('runs a second detector only on demand and keeps its score separate', async () => {
  const fetcher = vi.fn((url: string, options?: RequestInit) => Promise.resolve(response(
    url.endsWith('/status') ? { available: true } : options?.method === 'POST' ? report : { status: 'not_generated' },
  )))
  vi.stubGlobal('fetch', fetcher)
  render(<DetectorComparison jobId="sample" />)
  const button = await screen.findByRole('button', { name: 'Run second detector' })
  expect(fetcher.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
  await userEvent.click(button)
  expect(await screen.findByText('98.0 / 100')).toBeInTheDocument()
  expect(screen.getByText('9.0 / 100')).toBeInTheDocument()
  expect(screen.getByText('AASIST-L')).toBeInTheDocument()
  expect(screen.getByText('NII candidate')).toBeInTheDocument()
  expect(screen.getByText(/not averaged/i)).toBeInTheDocument()
  expect(screen.getByText('Not validated on sponsor data.')).toBeInTheDocument()
})

it('explains unavailable weights without offering a fake comparison', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(response(url.endsWith('/status')
    ? { available: false, reason: 'Verified candidate weights are unavailable.' } : { status: 'not_generated' }))))
  render(<DetectorComparison jobId="sample" />)
  expect(await screen.findByText('Verified candidate weights are unavailable.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Run second detector' })).not.toBeInTheDocument()
})

it('shows a rejected input without manufacturing a score and permits retry', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => Promise.resolve(
    options?.method === 'POST' ? response({ detail: 'Comparison supports at most 30 seconds.' }, 422)
      : response(url.endsWith('/status') ? { available: true } : { status: 'not_generated' }),
  )))
  render(<DetectorComparison jobId="sample" />)
  await userEvent.click(await screen.findByRole('button', { name: 'Run second detector' }))
  expect(await screen.findByText('Comparison supports at most 30 seconds.')).toBeInTheDocument()
  expect(screen.queryByText(/\/ 100/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run second detector' })).toBeEnabled()
})

it('loads a saved comparison without spending inference and clears it when the recording changes', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(response(url.endsWith('/status')
    ? { available: true } : url.includes('/first/') ? report : { status: 'not_generated' })))
  vi.stubGlobal('fetch', fetcher)
  const view = render(<DetectorComparison jobId="first" />)
  expect(await screen.findByText('98.0 / 100')).toBeInTheDocument()
  view.rerender(<DetectorComparison jobId="second" />)
  expect(await screen.findByRole('button', { name: 'Run second detector' })).toBeEnabled()
  expect(screen.queryByText('98.0 / 100')).not.toBeInTheDocument()
  expect(fetcher).not.toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ method: 'POST' }))
})

it('can recover from an initial network failure', async () => {
  let offline = true
  vi.stubGlobal('fetch', vi.fn((url: string) => offline ? Promise.reject(Error('Local server unavailable.')) : Promise.resolve(response(
    url.endsWith('/status') ? { available: true } : { status: 'not_generated' },
  ))))
  render(<DetectorComparison jobId="sample" />)
  expect(await screen.findByText('Local server unavailable.')).toBeInTheDocument()
  offline = false
  await userEvent.click(screen.getByRole('button', { name: 'Check comparison availability' }))
  expect(await screen.findByRole('button', { name: 'Run second detector' })).toBeEnabled()
})

it('does not show an old in-flight comparison on a different recording', async () => {
  let finish!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => options?.method === 'POST'
    ? new Promise<Response>(resolve => { finish = resolve }) : Promise.resolve(response(
      url.endsWith('/status') ? { available: true } : { status: 'not_generated' },
    ))))
  const view = render(<DetectorComparison jobId="first" />)
  await userEvent.click(await screen.findByRole('button', { name: 'Run second detector' }))
  expect(screen.getByRole('button', { name: 'Running second detector…' })).toBeDisabled()
  view.rerender(<DetectorComparison jobId="second" />)
  finish(response(report))
  expect(await screen.findByRole('button', { name: 'Run second detector' })).toBeEnabled()
  expect(screen.queryByText('98.0 / 100')).not.toBeInTheDocument()
})
