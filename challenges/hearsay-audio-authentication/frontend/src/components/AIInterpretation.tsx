import { InfoButton } from './ui/info-button'
import { useEffect, useRef, useState } from 'react'
import { CircleAlert, LoaderCircle, Sparkles } from 'lucide-react'
import './AIInterpretation.css'

type ProviderStatus = { available: boolean; provider: 'groq' | 'xai'; model: string | null; reason: string | null }
type Evidence = { id: string; label: string; value: unknown; unit?: string }
type Generated = {
  status: 'generated'
  provider: 'groq' | 'xai'
  model: string
  prompt_version: string
  evidence_sha256: string
  generated_at: string
  report: { summary: string; findings: { text: string; evidence_ids: string[] }[]; next_steps: string[] }
  evidence: Evidence[]
}
type View = {
  jobId: string
  phase: 'loading' | 'ready' | 'generating' | 'error'
  provider: ProviderStatus | null
  report: Generated | null
  error: string | null
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(url, init) }
  catch { throw new Error('Cannot reach the local analysis server.') }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

function evidenceValue(value: unknown, unit?: string): string {
  if (value == null) return 'Unavailable'
  if (typeof value === 'object' && !Array.isArray(value)) {
    const window = value as Record<string, unknown>
    if (typeof window.start_s === 'number' && typeof window.end_s === 'number' && typeof window.score === 'number') {
      return `${window.start_s}–${window.end_s} s · score ${window.score}`
    }
    return JSON.stringify(value)
  }
  return `${String(value)}${unit ? ` ${unit}` : ''}`
}

export default function AIInterpretation({ jobId, evidenceRevision }: { jobId: string; evidenceRevision?: string }) {
  const [view, setView] = useState<View>({ jobId, phase: 'loading', provider: null, report: null, error: null })
  const [reload, setReload] = useState(0)
  const [referencesOpen,setReferencesOpen]=useState(false)
  const [highlight,setHighlight]=useState('')
  const currentJob = useRef(jobId)
  currentJob.current = jobId
  const active = view.jobId === jobId ? view : { jobId, phase: 'loading' as const, provider: null, report: null, error: null }

  useEffect(() => {
    let live = true
    const controller = new AbortController()
    setView({ jobId, phase: 'loading', provider: null, report: null, error: null })
    Promise.all([
      request<ProviderStatus>('/api/interpretation/status', { signal: controller.signal }),
      request<Generated | { status: 'not_generated' }>(`/api/analyses/${encodeURIComponent(jobId)}/interpretation`, { signal: controller.signal }),
    ]).then(([provider, cached]) => {
      if (live) setView({ jobId, phase: 'ready', provider, report: cached.status === 'generated' ? cached : null, error: null })
    }).catch((error: unknown) => {
      if (live) setView({ jobId, phase: 'error', provider: null, report: null, error: error instanceof Error ? error.message : 'Interpretation could not be loaded.' })
    })
    return () => { live = false; controller.abort() }
  }, [jobId, reload, evidenceRevision])

  async function generate() {
    if (active.phase === 'generating' || active.phase === 'loading') return
    setView(previous => ({ ...previous, phase: 'generating', error: null }))
    try {
      const report = await request<Generated>(`/api/analyses/${encodeURIComponent(jobId)}/interpretation`, { method: 'POST' })
      if (currentJob.current === jobId) setView(previous => ({ ...previous, phase: 'ready', report, error: null }))
    } catch (error) {
      if (currentJob.current === jobId) setView(previous => ({ ...previous, phase: 'error', error: error instanceof Error ? error.message : 'Interpretation could not be generated.' }))
    }
  }

  const citedIds = new Set(active.report?.report.findings.flatMap(finding => finding.evidence_ids) || [])
  const citedEvidence = active.report?.evidence.filter(item => citedIds.has(item.id)) || []

  return <section className="detail-section ai-interpretation" aria-labelledby="ai-interpretation-title">
    <div className="section-heading"><div><span className="eyebrow">07 / AI REVIEW</span><h2 id="ai-interpretation-title">AI interpretation</h2></div><InfoButton label="AI interpretation">Groq writes a brief from supplied measured evidence. It does not receive the recording and cannot change detector scores. Check each finding against its measurement references.</InfoButton></div>
    <p className="ai-interpretation-caveat">Groq receives the primary detector’s measured findings only; no audio, filenames, or transcripts. Its summary can err and is not a detection result.</p>
    {active.phase === 'loading' && <p className="ai-interpretation-state" role="status"><LoaderCircle size={14} className="spin" /> Checking interpretation…</p>}
    {active.report && <div className="ai-interpretation-report">
      <div className="ai-interpretation-meta">Generated with {active.report.provider === 'xai' ? 'Grok (xAI)' : 'Groq'} · {active.report.model}</div>
      <p className="ai-interpretation-summary">{active.report.report.summary}</p>
      {active.report.report.findings.length > 0 && <><h3>Findings</h3><ul>{active.report.report.findings.map((finding, index) => <li key={index}>{finding.text}{finding.evidence_ids.length > 0 && <span className="ai-interpretation-refs"> {finding.evidence_ids.map(id=><button key={id} aria-label={`Show measurement ${id}`} onClick={()=>{setReferencesOpen(true);setHighlight(id);requestAnimationFrame(()=>document.getElementById(`measurement-${jobId}-${id}`)?.scrollIntoView?.({block:'nearest'}))}}>{id}</button>)}</span>}</li>)}</ul></>}
      {active.report.report.next_steps.length > 0 && <><h3>Suggested next steps</h3><ul>{active.report.report.next_steps.map((step, index) => <li key={index}>{step}</li>)}</ul></>}
      {citedEvidence.length > 0 && <details className="ai-interpretation-evidence" open={referencesOpen} onToggle={e=>setReferencesOpen(e.currentTarget.open)}><summary>Measurement references</summary><dl>{citedEvidence.map(item => <div key={item.id} id={`measurement-${jobId}-${item.id}`} className={highlight===item.id?'measurement-highlight':undefined}><dt>{item.id} · {item.label}</dt><dd>{evidenceValue(item.value, item.unit)}</dd></div>)}</dl></details>}
    </div>}
    {!active.report && active.phase !== 'loading' && <>
      {active.error && <p className="ai-interpretation-error" role="alert"><CircleAlert size={15} /> {active.error}</p>}
      {active.error && !active.provider && <button className="outline-button" onClick={() => setReload(value => value + 1)}>Retry loading interpretation</button>}
      {!active.error && active.provider && !active.provider.available && <p className="ai-interpretation-state">AI interpretation is unavailable. {active.provider.reason || 'The Groq provider is not configured.'}</p>}
      {!active.error && active.provider && !active.provider.available && <button className="outline-button" onClick={() => setReload(value => value + 1)}>Check configuration</button>}
      {active.provider?.available && <><p className="ai-interpretation-state">Generate a written interpretation on demand using {active.provider.model || 'Groq'}.</p><button className="outline-button" onClick={generate} disabled={active.phase === 'generating'}>{active.phase === 'generating' ? <><LoaderCircle size={14} className="spin" /> Generating interpretation…</> : <><Sparkles size={14} /> {active.error ? 'Retry interpretation' : 'Generate interpretation'}</>}</button></>}
      {active.phase === 'generating' && <p className="ai-interpretation-state" role="status">Groq is interpreting the measurements. This may take a moment.</p>}
    </>}
  </section>
}
