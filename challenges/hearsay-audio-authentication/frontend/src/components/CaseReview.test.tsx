import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CaseReview from './CaseReview'
const fetchMock = vi.fn()
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/speaker/status') return response({ available: true, ready: true })
    if (url === '/api/claims/status') return response({ provider: { available: false, provider: 'groq', reason: 'Hosted Groq claim search is disabled; record an analyst review instead.' }, transcription: { available: true, ready: true } })
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
  expect(await screen.findByText(/Hosted Groq claim search is disabled/)).toBeInTheDocument()
  expect(screen.getAllByRole('button', { hidden: true }).find(button => button.textContent?.includes('Review with Groq'))).toBeDisabled()
  expect(screen.getByRole('checkbox', { name: 'Allow this claim to be sent to Groq.' })).toBeDisabled()
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
  await screen.findByText(/Hosted Groq claim search is disabled/)
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
it('compares a consented reference and removes saved metadata', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url:string, init?:RequestInit) => {
    if (url.endsWith('/speaker-comparison') && init?.method === 'POST') return Promise.resolve(response({similarity:{cosine:.734,calibration:'uncalibrated'},reference:{label:'Interview'},limitations:[]}))
    if (init?.method === 'DELETE') return Promise.resolve(new Response(null,{status:204}))
    return original(url,init)
  })
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  await screen.findByText(/Hosted Groq claim search is disabled/)
  await userEvent.upload(screen.getByLabelText('Reference recording'),new File(['audio'],'ref.wav',{type:'audio/wav'}))
  await userEvent.type(screen.getByLabelText('Reference label'),'Interview')
  await userEvent.click(screen.getByRole('checkbox',{name:/permission to process/}))
  await userEvent.click(screen.getByRole('button',{name:'Compare reference'}))
  expect(await screen.findByText('0.734')).toBeInTheDocument()
  const post = fetchMock.mock.calls.find(([,init])=>init?.method==='POST')!
  expect(post[1].body.get('consent')).toBe('true')
  await userEvent.click(screen.getByRole('button',{name:'Remove saved comparison'}))
  await waitFor(() => expect(screen.queryByText('0.734')).not.toBeInTheDocument())
})
it('creates a local transcript and displays a source-cited AI review only after consent', async () => {
  const original = fetchMock.getMockImplementation()!
  let reviewed=false
  fetchMock.mockImplementation((url:string, init?:RequestInit) => {
    if(url === '/api/claims/status') return Promise.resolve(response({provider:{available:true},transcription:{available:true,ready:true}}))
    if(url.endsWith('/transcript') && init?.method==='POST') return Promise.resolve(response({status:'generated',version:1,source:'automatic',text:'Check this statement.',segments:[]}))
    if(url.endsWith('/claims') && init?.method==='POST') { reviewed=true;return Promise.resolve(response({id:'review'})) }
    if(url.endsWith('/claims') && reviewed) return Promise.resolve(response({claims:[{id:'review',text:'Check this statement.',verdict:'supported',method:'grok_web_search',rationale:'Fixture source supports the statement.',evidence:[{url:'https://example.org/source',title:'Fixture source',publisher:'Example',quote:'Test excerpt.'}],stale_transcript:true}]}))
    return original(url,init)
  })
  render(<CaseReview jobId="a" onSeek={() => {}} />)
  await waitFor(()=>expect(screen.getByRole('button',{name:'Create transcript'})).toBeEnabled())
  await userEvent.click(screen.getByRole('button',{name:'Create transcript'}))
  expect(await screen.findByDisplayValue('Check this statement.')).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('Claim to review'),'Check this statement.')
  const groqButton = screen.getByRole('button', { name: /Review with Groq/, hidden: true })
  expect(groqButton).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox',{name:'Allow this claim to be sent to Groq.'}))
  await userEvent.click(groqButton)
  expect(await screen.findByRole('link',{name:'Fixture source'})).toHaveAttribute('href','https://example.org/source')
  expect(screen.getByText(/Transcript changed/)).toBeInTheDocument()
  const post = fetchMock.mock.calls.find(([url,init])=>url.endsWith('/claims') && init?.method==='POST')!
  expect(JSON.parse(post[1].body)).toEqual({text:'Check this statement.',transcript_version:1,external_search_consent:true})
})
it('shows action errors without replacing an existing successful transcript', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url:string,init?:RequestInit)=>url.endsWith('/transcript') ? Promise.resolve(init?.method==='POST' ? response({detail:'Decoder failed.'},503) : response({status:'generated',version:1,text:'Saved text.',segments:[]})) : original(url,init))
  render(<CaseReview jobId="a" onSeek={()=>{}} />)
  await screen.findByDisplayValue('Saved text.')
  await userEvent.click(screen.getByRole('button',{name:'Transcribe again'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('Decoder failed.')
  expect(screen.getByDisplayValue('Saved text.')).toBeInTheDocument()
})
it('carries the selected transcript passage and time range into a claim review', async () => {
  const original = fetchMock.getMockImplementation()!
  fetchMock.mockImplementation((url:string,init?:RequestInit)=>url.endsWith('/transcript') ? Promise.resolve(response({status:'generated',version:1,text:'A specific statement.',segments:[{id:1,start_s:1,end_s:3,text:'A specific statement.'}]})) : original(url,init))
  render(<CaseReview jobId="a" onSeek={()=>{}} />)
  await userEvent.click(await screen.findByRole('button',{name:'Review passage 1 as a claim'}))
  expect(screen.getByLabelText('Claim to review')).toHaveValue('A specific statement.')
  await userEvent.click(screen.getByText('Record an analyst review'))
  await userEvent.type(screen.getByLabelText('Reasoning'),'No source has been reviewed.')
  await userEvent.click(screen.getByRole('button',{name:'Save analyst review'}))
  const call=fetchMock.mock.calls.find(([,init])=>init?.method==='POST')!
  expect(JSON.parse(call[1].body).span).toEqual({start_s:1,end_s:3})
})
