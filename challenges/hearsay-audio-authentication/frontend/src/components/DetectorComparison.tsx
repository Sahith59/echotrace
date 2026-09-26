import { useEffect, useRef, useState } from 'react'
import { LoaderCircle, ScanLine } from 'lucide-react'
import './DetectorComparison.css'

type Model = { name?: string; version?: string; weights_sha256?: string }
type Comparison = {
  status: 'generated'; primary_score: number | null; candidate_score: number
  primary_model: Model; model: Model; input_sha256: string; duration_s: number
  generated_at: string; experimental: boolean; limitation: string
}
type Status = { available: boolean; reason?: string | null }
const score = (value: number | null) => value != null && Number.isFinite(value) ? `${(value * 100).toFixed(1)} / 100` : 'Unavailable'
class ComparisonError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}
async function read<T>(url: string, signal: AbortSignal, method = 'GET'): Promise<T> {
  const response = await fetch(url, { method, signal })
  const body = await response.json()
  if (!response.ok) throw new ComparisonError(typeof body.detail === 'string' ? body.detail : 'Detector comparison could not be completed.', response.status)
  return body
}

function ComparisonForRecording({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [report, setReport] = useState<Comparison | null>(null)
  const [error, setError] = useState('')
  const [ineligible, setIneligible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)
  const pending = useRef<AbortController | null>(null)
  const endpoint = `/api/analyses/${encodeURIComponent(jobId)}/detector-comparison`
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setIneligible(false)
    Promise.all([
      read<Status>('/api/detector-comparison/status', controller.signal),
      read<Comparison | { status: 'not_generated' }>(endpoint, controller.signal),
    ]).then(([availability, saved]) => {
      if (controller.signal.aborted) return
      setStatus(availability); setReport(saved.status === 'generated' ? saved : null)
    }).catch(reason => { if (!controller.signal.aborted) {
      setError(reason instanceof Error ? reason.message : 'Could not load the comparison.')
      setIneligible(reason instanceof ComparisonError && [404, 422].includes(reason.status))
    } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => { controller.abort(); pending.current?.abort() }
  }, [endpoint, refresh])

  async function generate() {
    const controller = new AbortController()
    pending.current = controller
    setBusy(true); setError('')
    try {
      const saved = await read<Comparison>(endpoint, controller.signal, 'POST')
      if (!controller.signal.aborted) setReport(saved)
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Detector comparison failed.')
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }

  return <section className="detail-section case-panel detector-comparison" aria-label="Second-detector comparison">
    <div className="section-heading"><div><span className="eyebrow">RESEARCH COMPARISON</span><h2>Second-detector comparison</h2></div><ScanLine size={18} /></div>
    <p className="detail-note">Check the same recording with a separately trained NII speech detector. Local processing · up to 30 seconds. This research model has not replaced the primary detector.</p>
    {loading && <p className="case-help" role="status">Loading comparison…</p>}
    {error && <p className="case-help" role="alert">{error}</p>}
    {report ? <>
      <div className="detector-scorecards">
        <div><span>Primary assessment</span><h3>{report.primary_model?.name || 'Primary detector'}</h3><strong>{score(report.primary_score)}</strong></div>
        <div><span>Research assessment</span><h3>{report.model?.name || 'NII detector'}</h3><strong>{score(report.candidate_score)}</strong></div>
      </div>
      <p className="case-help">These uncalibrated scores are not averaged. Agreement does not prove authenticity; disagreement is a reason to review the recording and each model’s measured limits.</p>
      <details className="technical-details"><summary>Comparison provenance</summary>
        <p className="case-help">{report.limitation}</p><dl>
        <dt>Input SHA-256</dt><dd>{report.input_sha256}</dd>
        <dt>Research weights SHA-256</dt><dd>{report.model?.weights_sha256 || 'Unavailable'}</dd>
        <dt>Generated</dt><dd>{report.generated_at || 'Unavailable'}</dd>
      </dl></details>
    </> : !loading && !ineligible && <>
      {status?.available ? <button className="outline-button" onClick={generate} disabled={busy}>
        {busy && <LoaderCircle size={14} className="spin" />}{busy ? 'Running second detector…' : 'Run second detector'}
      </button> : <><p className="case-help">{status?.reason || 'Detector comparison availability could not be verified.'}</p><button className="outline-button" onClick={() => setRefresh(value => value + 1)}>Check comparison availability</button></>}
    </>}
  </section>
}

export default function DetectorComparison({ jobId }: { jobId: string }) {
  return <ComparisonForRecording key={jobId} jobId={jobId} />
}
