import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CaseReview from './CaseReview'
const fetchMock = vi.fn()
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/speaker/status') return response({ available: true, ready: true })
    if (url === '/api/claims/status') return response({ provider: { available: false, reason: 'Configure xAI locally.' }, transcription: { available: true, ready: true } })
    if (url.endsWith('/speaker-comparison')) return response({ detail: 'Not found' }, 404)
    if (url.endsWith('/transcript')) return response({ status: 'not_generated', versions: [] })
    return response({ claims: [] })
  })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); fetchMock.mockReset() })
it('keeps independent evidence separate and requires reference consent', async () => {
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  await screen.findByText('Speaker reference')
  expect(screen.getByRole('button', { name: 'Compare reference' })).toBeDisabled()
  expect(screen.getByText(/not an identity verdict/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /download case json/i })).toHaveAttribute('href', '/api/analyses/a/case-report')
})
it('discloses unavailable AI while allowing a sourced analyst review', async () => {
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  expect(await screen.findByText('Configure xAI locally.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Review with Grok' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save analyst review' })).toBeDisabled()
})
it('loads a transcript with seekable segments and preserves correction version', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url: string, init?: RequestInit) => url.endsWith('/transcript') ? Promise.resolve(response({ status: 'generated', version: 2, source: 'automatic', text: 'The launch was successful.', segments: [{ id: 0, start_s: 3, end_s: 5, text: 'The launch was successful.' }] })) : original(url, init))
  const seek = vi.fn()
  render(<CaseReview jobId="a" onSeek={seek} />)
  await userEvent.click(await screen.findByRole('button', { name: /3.0.*The launch/ }))
  expect(seek).toHaveBeenCalledWith(3)
  await userEvent.type(screen.getByLabelText('Correct transcript'), ' Updated')
  await userEvent.click(screen.getByRole('button', { name: 'Save correction' }))
  expect(fetchMock).toHaveBeenCalledWith('/api/analyses/a/transcript', expect.objectContaining({ method: 'PUT', body: JSON.stringify({ base_version: 2, text: 'The launch was successful. Updated' }) }))
})
it('shows a server failure and permits retry without fabricating evidence', async () => {
  fetchMock.mockRejectedValue(new Error('Offline'))
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Offline')
  expect(screen.getByRole('button', { name: 'Reload evidence' })).toBeEnabled()
})
it('saves analyst evidence with an explicit stance matching the verdict', async () => {
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  await screen.findByText('Configure xAI locally.')
  await userEvent.click(screen.getByText('Record an analyst review'))
  await userEvent.type(screen.getByLabelText('Claim to review'), 'A verifiable statement.')
  await userEvent.selectOptions(screen.getByLabelText('Assessment'), 'supported')
  await userEvent.type(screen.getByLabelText('Reasoning'), 'The source directly supports this statement.')
  await userEvent.type(screen.getByLabelText('Source URL'), 'https://example.org/source')
  await userEvent.click(screen.getByRole('button', { name: 'Save analyst review' }))
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
  expect(JSON.parse(call[1].body).analyst_review.evidence[0].stance).toBe('supports')
})
it('does not offer voice inference before pinned model setup is ready', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url: string, init?: RequestInit) => url === '/api/speaker/status' ? Promise.resolve(response({available:true,ready:false,reason:'Prepare the speaker model.'})) : original(url,init))
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  await screen.findByText('Prepare the speaker model.')
  await userEvent.upload(screen.getByLabelText('Reference recording'), new File(['audio'], 'reference.wav', {type:'audio/wav'}))
  await userEvent.click(screen.getByRole('checkbox', {name:/permission to process/}))
  expect(screen.getByRole('button', {name:'Compare reference'})).toBeDisabled()
})
it('keeps successful words visible while disclosing a failed subsequent transcription attempt', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url: string, init?: RequestInit) => url.endsWith('/transcript') ? Promise.resolve(response({status:'generated',version:1,text:'Previously transcribed words.',segments:[],latest_attempt:{status:'error',version:2,error:'Local transcription failed.'}})) : original(url,init))
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  expect(await screen.findByDisplayValue('Previously transcribed words.')).toBeInTheDocument()
  expect(screen.getByText(/Local transcription failed/)).toBeInTheDocument()
})
