import '@testing-library/jest-dom/vitest'
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MatchedComparison from './MatchedComparison'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('plays a verified same-passage pair and submits both audio files for analysis', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const path = String(input)
    if (path === '/api/examples/paired-demo') return Promise.resolve(new Response(JSON.stringify({
      available: true, original_filename: 'jane_eyre_21_f000371.wav', synthetic_filename: 'jane_eyre_21_f000371.wav',
    })))
    if (path.endsWith('/audio') || path.endsWith('/original-audio')) return Promise.resolve(new Response(new Blob([new Uint8Array([1, 2, 3])]), { status: 200 }))
    throw Error(`Unexpected request: ${path}`)
  }))
  const onAnalyze = vi.fn().mockResolvedValue(undefined)
  render(<MatchedComparison jobs={[]} busy={false} onAnalyze={onAnalyze} onOpen={vi.fn()} />)
  expect(await screen.findByLabelText('Play original human reading')).toHaveAttribute('src', '/api/examples/paired-demo/original-audio')
  expect(screen.getByLabelText('Play generated reading')).toHaveAttribute('src', '/api/examples/b9bcdda92ac7de4e/audio')
  await userEvent.setup().click(screen.getByRole('button', { name: 'Analyze both recordings' }))
  await waitFor(() => expect(onAnalyze).toHaveBeenCalledTimes(1))
  const files = onAnalyze.mock.calls[0][0] as File[]
  expect(files.map(file => file.name)).toEqual([
    'comparison-human-jane_eyre_21_f000371.wav', 'comparison-generated-jane_eyre_21_f000371.wav',
  ])
  expect(files.every(file => file.size > 0)).toBe(true)
})

it('keeps the comparison unavailable when the matched source was not verified', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ available: false }))))
  render(<MatchedComparison jobs={[]} busy={false} onAnalyze={vi.fn()} onOpen={vi.fn()} />)
  expect(await screen.findByText(/Paired audio is not prepared locally/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Analyze both recordings' })).toBeDisabled()
})
