import { useEffect, useRef, useState } from 'react'
import { FileText, Mic, Search, Download, Play, LoaderCircle } from 'lucide-react'
import './CaseReview.css'

type Segment = { id: number; start_s: number; end_s: number; text: string }
type Transcript = { status: string; version?: number; text?: string; source?: string; segments?: Segment[]; error?: string; latest_attempt?: {status:string; version:number; error?:string} }
type Source = { url: string; title?: string; publisher?: string; quote?: string }
type Claim = { id: string; text: string; verdict: string; method: string; rationale: string; evidence: Source[]; stale_transcript?: boolean; error?: string }
type Speaker = { similarity: { cosine: number; calibration: string }; reference: { label: string }; limitations: string[] }
type Service = { available: boolean; ready?: boolean; reason?: string }
type Status = { provider: Service; transcription: Service }
async function request<T>(url: string, init?: RequestInit, missing?: T): Promise<T> {
  const response = await fetch(url, init)
  if (response.status === 404 && missing !== undefined) return missing
  if (response.status === 204) return null as T
  const value = await response.json()
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : `Request failed (${response.status}).`)
  return value as T
}
const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
const words = (text: string) => text.replaceAll('_', ' ')

// Keyed inner component prevents evidence/actions for one recording leaking into another.
export default function CaseReview(props: { jobId: string; onSeek: (seconds: number) => void }) {
  return <EvidenceWorkspace key={props.jobId} {...props} />
}
function EvidenceWorkspace({ jobId, onSeek }: { jobId: string; onSeek: (seconds: number) => void }) {
  const base = `/api/analyses/${encodeURIComponent(jobId)}`
  const [speakerStatus, setSpeakerStatus] = useState<Service | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [speaker, setSpeaker] = useState<Speaker | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [claims, setClaims] = useState<Claim[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [reference, setReference] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [label, setLabel] = useState('')
  const [correction, setCorrection] = useState('')
  const [claim, setClaim] = useState('')
  const [externalConsent, setExternalConsent] = useState(false)
  const [verdict, setVerdict] = useState('insufficient_evidence')
  const [rationale, setRationale] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceTitle, setSourceTitle] = useState('')
  const live = useRef(true)
  async function load() {
    setLoading(true); setError('')
    try {
      const [ss, cs, sp, tr, cl] = await Promise.all([
        request<Service>('/api/speaker/status'), request<Status>('/api/claims/status'),
        request<Speaker | null>(`${base}/speaker-comparison`, undefined, null),
        request<Transcript>(`${base}/transcript`), request<{ claims: Claim[] }>(`${base}/claims`),
      ])
      if (!live.current) return
      setSpeakerStatus(ss); setStatus(cs); setSpeaker(sp); setTranscript(tr); setCorrection(tr.text || ''); setClaims(cl.claims)
    } catch (e) { if (live.current) setError(e instanceof Error ? e.message : 'Could not load case evidence.') }
    finally { if (live.current) setLoading(false) }
  }
  useEffect(() => { live.current = true; void load(); return () => { live.current = false } }, [])
  async function act(name: string, action: () => Promise<void>) {
    if (busy) return
    setBusy(name); setError('')
    try { await action() } catch (e) { if (live.current) setError(e instanceof Error ? e.message : 'The request could not be completed.') }
    finally { if (live.current) setBusy('') }
  }
  const disabled = loading || !!busy
  async function saveClaim(ai: boolean) {
    await act(ai ? 'Searching sources' : 'Saving review', async () => {
      const body = { text: claim.trim(), ...(transcript?.version ? { transcript_version: transcript.version } : {}), external_search_consent: ai && externalConsent,
        ...(!ai ? { analyst_review: { verdict, rationale: rationale.trim(), evidence: sourceUrl.trim() ? [{ url: sourceUrl.trim(), title: sourceTitle.trim() || undefined, stance: verdict === 'supported' ? 'supports' : verdict === 'contradicted' ? 'contradicts' : 'context' }] : [] } } : {}) }
      await request(`${base}/claims`, json('POST', body))
      const result = await request<{ claims: Claim[] }>(`${base}/claims`)
      if (live.current) { setClaims(result.claims); setClaim(''); setRationale(''); setSourceUrl(''); setSourceTitle(''); setExternalConsent(false) }
    })
  }
  return <section className="case-review" aria-label="Independent case evidence">
    <div className="case-intro"><div><span className="eyebrow">INDEPENDENT EVIDENCE</span><h2>Beyond the waveform</h2><p>Three different questions. Separate evidence for each answer.</p></div><div className="case-downloads"><a className="outline-button" href={`${base}/case-report`} download><Download size={15} /> Download case JSON</a><a className="outline-button" href={`${base}/case-report.html`} target="_blank" rel="noreferrer">Printable report</a></div></div>
    {loading && <p role="status">Loading case evidence…</p>}
    {busy && <p role="status" className="case-progress"><LoaderCircle size={15} className="spin" />{busy}… Keep this recording open.</p>}
    {error && <div role="alert" className="case-error">{error}<button className="text-button" onClick={load} disabled={!!busy}>Reload evidence</button></div>}
    <div className="case-columns">
      <section className="detail-section case-panel" aria-labelledby="speaker-title">
        <div className="section-heading"><div><span className="eyebrow">08 / VOICE COMPARISON</span><h2 id="speaker-title">Speaker reference</h2></div><Mic size={18} /></div>
        <p className="detail-note">Compare this recording with a trusted voice sample. Similarity is not an identity verdict; a clone or replay can also sound similar.</p>
        {speaker && <div className="speaker-result"><span>Cosine similarity · uncalibrated</span><strong>{speaker.similarity.cosine.toFixed(3)}</strong><p>Reference: {speaker.reference.label}</p><small>Scale −1 to 1. This is not a confidence percentage.</small><button className="text-button" disabled={disabled} onClick={() => act('Removing comparison', async () => { await request(`${base}/speaker-comparison`, { method: 'DELETE' }); if (live.current) setSpeaker(null) })}>Remove saved comparison</button></div>}
        <label className="case-field">Reference recording<input type="file" accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.opus" onChange={e => setReference(e.target.files?.[0] || null)} /></label>
        <label className="case-field">Reference label<input maxLength={80} placeholder="e.g. Consented interview" value={label} onChange={e => setLabel(e.target.value)} /></label>
        <label className="case-check"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>I have permission to process this trusted voice reference.</span></label>
        <p className="case-help">2–120 seconds · 20 MiB maximum. Reference audio is deleted after comparison; its hash and comparison remain until removed.</p>
        {speakerStatus?.reason && <p className="case-help">{speakerStatus.reason}</p>}
        <button className="outline-button" disabled={disabled || !reference || !consent || !speakerStatus?.available || !speakerStatus?.ready} onClick={() => act('Comparing voices', async () => { const form = new FormData(); form.append('file', reference!); form.append('consent', 'true'); if (label.trim()) form.append('reference_label', label.trim()); const result = await request<Speaker>(`${base}/speaker-comparison`, { method: 'POST', body: form }); if (live.current) setSpeaker(result) })}>Compare reference</button>
      </section>
      <section className="detail-section case-panel" aria-labelledby="transcript-title">
        <div className="section-heading"><div><span className="eyebrow">09 / WORDS SPOKEN</span><h2 id="transcript-title">Transcript</h2></div><FileText size={18} /></div>
        <p className="detail-note">Transcribe locally, listen, and correct errors before reviewing claims. Transcription can mishear speech or invent words in noise.</p>
        {status?.transcription.reason && <p className="case-help">{status.transcription.reason}</p>}
        <button className="outline-button" disabled={disabled || !status?.transcription.available} onClick={() => act('Transcribing locally', async () => { const result = await request<Transcript>(`${base}/transcript`, { method: 'POST' }); if (live.current) { setTranscript(result); setCorrection(result.text || '') } })}>{transcript?.version ? 'Transcribe again' : 'Create transcript'}</button>
        {transcript?.latest_attempt?.status === 'error' && <p className="case-error">Latest transcription attempt failed: {transcript.latest_attempt.error} Your previous transcript is preserved.</p>}
        {transcript?.error && <p className="case-error">{transcript.error}</p>}
        {transcript?.version && <><p className="case-help">Version {transcript.version} · {words(transcript.source || 'automatic')}</p><div className="transcript-segments">{transcript.segments?.map((segment, index) => <button key={index} onClick={() => onSeek(segment.start_s)}><span><Play size={12} /> {segment.start_s.toFixed(1)}–{segment.end_s.toFixed(1)}s</span>{segment.text}</button>)}</div><label className="case-field">Correct transcript<textarea rows={5} value={correction} maxLength={16000} onChange={e => setCorrection(e.target.value)} /></label><button className="outline-button" disabled={disabled || !correction.trim() || correction === transcript.text} onClick={() => act('Saving correction', async () => { const result = await request<Transcript>(`${base}/transcript`, json('PUT', { base_version: transcript.version, text: correction })); if (live.current) { setTranscript(result); setCorrection(result.text || '') }; const resultClaims = await request<{ claims: Claim[] }>(`${base}/claims`); if (live.current) setClaims(resultClaims.claims) })}>Save correction</button><p className="case-help">Corrections create a new version. Reviews of older wording remain visible and are marked stale.</p></>}
      </section>
    </div>
    <section className="detail-section case-panel" aria-labelledby="claims-title">
      <div className="section-heading"><div><span className="eyebrow">10 / SOURCE REVIEW</span><h2 id="claims-title">Check a factual claim</h2></div><Search size={18} /></div>
      <p className="detail-note">Review a specific, checkable statement against external evidence. This does not detect lies or establish a speaker’s intent. Private or subjective statements may remain unresolved.</p>
      <label className="case-field">Claim to review<textarea rows={2} maxLength={2000} value={claim} onChange={e => setClaim(e.target.value)} placeholder="Enter one factual statement from the recording." /></label>
      <div className="claim-methods"><div><h3>Search with Grok</h3><p className="case-help">Only this claim is sent to xAI for web search. Audio and the full transcript stay local.</p><label className="case-check"><input type="checkbox" checked={externalConsent} onChange={e => setExternalConsent(e.target.checked)} /><span>Allow this claim to be sent to xAI.</span></label>{!status?.provider.available && <p className="case-help">{status?.provider.reason || 'Checking AI configuration…'}</p>}<button className="outline-button" disabled={disabled || !claim.trim() || !externalConsent || !status?.provider.available} onClick={() => saveClaim(true)}>Review with Grok</button></div>
      <details><summary>Record an analyst review</summary><p className="case-help">Your assessment is labeled as analyst-written, separately from AI output.</p><label className="case-field">Assessment<select value={verdict} onChange={e => setVerdict(e.target.value)}><option value="insufficient_evidence">Insufficient evidence</option><option value="supported">Supported by sources</option><option value="contradicted">Contradicted by sources</option><option value="uncheckable">Uncheckable</option></select></label><label className="case-field">Reasoning<textarea value={rationale} maxLength={1500} onChange={e => setRationale(e.target.value)} /></label><label className="case-field">Source URL<input type="url" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} placeholder="https://…" /></label><label className="case-field">Source title<input value={sourceTitle} maxLength={300} onChange={e => setSourceTitle(e.target.value)} /></label><button className="outline-button" disabled={disabled || !claim.trim() || !rationale.trim() || (['supported', 'contradicted'].includes(verdict) && !sourceUrl.trim())} onClick={() => saveClaim(false)}>Save analyst review</button></details></div>
      <div className="claim-results">{claims.map(item => <article key={item.id}><div className="claim-result-meta"><span>{words(item.verdict || 'uncheckable')}</span><small>{words(item.method || 'review')}</small></div><h3>{item.text}</h3>{item.stale_transcript && <p className="case-error">Transcript changed. Review this claim again against the corrected wording.</p>}<p>{item.rationale}</p>{item.error && <p className="case-error">{item.error}</p>}<ul>{item.evidence?.map((source, index) => <li key={index}>{/^https?:\/\//i.test(source.url) ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || source.url}</a> : <span>Unavailable source</span>}{source.publisher && <small> · {source.publisher}</small>}{source.quote && <blockquote>{source.quote}</blockquote>}</li>)}</ul></article>)}</div>
      {!claims.length && !loading && <p className="case-help">No claims reviewed for this recording yet.</p>}
    </section>
  </section>
}
