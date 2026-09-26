import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PilotExamples from './PilotExamples'

const catalog = {
  dataset: 'Pilot collection',
  note: 'Known references',
  examples: [
    { id: 'real-01', filename: 'person.wav', label: 'genuine', available: true },
    { id: 'fake-02', filename: 'voice.wav', label: 'synthetic', available: true },
    { id: 'gone-03', filename: 'missing.wav', label: 'synthetic', available: false },
  ],
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}

async function openPicker(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText('Try a known recording'))
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('PilotExamples', () => {
  it('loads on expansion, shows reference labels, and previews the selected recording', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.mocked(fetch).mockResolvedValue(jsonResponse(catalog))
    render(<PilotExamples onAnalyze={vi.fn()} busy={false} />)
    expect(fetchMock).not.toHaveBeenCalled()
    await openPicker(user)
    const select = await screen.findByLabelText('Recording')
    expect(fetchMock).toHaveBeenCalledWith('/api/examples', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(screen.getByText('Pilot collection · Known references')).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: /missing\.wav.*unavailable/ })).toBeDisabled()
    expect(screen.getByText('Reference label:').parentElement).toHaveTextContent('genuine')
    expect(screen.getByLabelText('Preview person.wav')).toHaveAttribute('src', '/api/examples/real-01/audio')
    await user.selectOptions(select, 'fake-02')
    expect(screen.getByText('Reference label:').parentElement).toHaveTextContent('synthetic')
    expect(screen.getByLabelText('Preview voice.wav')).toHaveAttribute('src', '/api/examples/fake-02/audio')
  })

  it('fetches sample bytes and passes a labeled File to the existing analysis path', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(catalog))
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob([new Uint8Array([82, 73, 70, 70])], { type: 'audio/wav' }) } as Response)
    const onAnalyze = vi.fn(async (_file: File) => {})
    render(<PilotExamples onAnalyze={onAnalyze} busy={false} />)
    await openPicker(user)
    await screen.findByLabelText('Recording')
    await user.click(screen.getByRole('button', { name: 'Analyze this sample' }))
    await waitFor(() => expect(onAnalyze).toHaveBeenCalledOnce())
    expect(fetchMock).toHaveBeenLastCalledWith('/api/examples/real-01/audio')
    const file = onAnalyze.mock.calls[0][0]
    expect(file).toBeInstanceOf(File)
    expect(file.name).toBe('known-genuine-person.wav')
    expect(file.type).toBe('audio/wav')
    expect(file.size).toBe(4)
  })

  it('reports catalog failure and can retry; a missing collection has no analyze action', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: 'Dataset unavailable' }, 503))
      .mockResolvedValueOnce(jsonResponse({ dataset: 'Pilot', note: '', reason: 'Audio files were not found.', examples: [] }))
    render(<PilotExamples onAnalyze={vi.fn()} busy={false} />)
    await openPicker(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('Dataset unavailable')
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Audio files were not found.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Analyze this sample' })).not.toBeInTheDocument()
  })

  it('disables analysis while busy and reports audio fetch failures', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(catalog))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Audio missing' }, 404))
    const onAnalyze = vi.fn()
    const { rerender } = render(<PilotExamples onAnalyze={onAnalyze} busy />)
    await openPicker(user)
    await screen.findByLabelText('Recording')
    expect(screen.getByRole('button', { name: 'Analyze this sample' })).toBeDisabled()
    rerender(<PilotExamples onAnalyze={onAnalyze} busy={false} />)
    await user.click(screen.getByRole('button', { name: 'Analyze this sample' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Audio missing')
    expect(onAnalyze).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('shows unavailable audio state when preview fails', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(jsonResponse(catalog))
    render(<PilotExamples onAnalyze={vi.fn()} busy={false} />)
    await openPicker(user)
    const preview = await screen.findByLabelText('Preview person.wav')
    preview.dispatchEvent(new Event('error'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Preview is unavailable')
  })

  it('explains when all catalog entries are missing', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(jsonResponse({
      dataset: 'Pilot', note: '', reason: 'Files are missing from this installation.',
      examples: [{ id: 'gone', filename: 'gone.wav', label: 'genuine', available: false }],
    }))
    render(<PilotExamples onAnalyze={vi.fn()} busy={false} />)
    await openPicker(user)
    expect(await screen.findByText('Files are missing from this installation.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Recording')).not.toBeInTheDocument()
  })

  it('reports an error returned by the analysis callback', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(catalog))
      .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['audio'], { type: 'audio/wav' }) } as Response)
    render(<PilotExamples onAnalyze={vi.fn().mockRejectedValue(new Error('Upload rejected'))} busy={false} />)
    await openPicker(user)
    await screen.findByLabelText('Recording')
    await user.click(screen.getByRole('button', { name: 'Analyze this sample' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Upload rejected')
  })
})
