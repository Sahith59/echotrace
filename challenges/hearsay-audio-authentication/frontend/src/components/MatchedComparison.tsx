import { useEffect, useState } from 'react'
import './MatchedComparison.css'

type Pair = { available: boolean; original_filename: string; synthetic_filename: string | null; reason?: string }
type PairJob = { id: string; filename: string; status: string; result: { synthetic_score: number | null; model?: { name?: string } } | null }
type Props = {
  jobs: PairJob[]
  busy: boolean
  onAnalyze: (files: File[]) => Promise<void>
  onOpen: (id: string) => void
}

const ORIGINAL_URL = '/api/examples/paired-demo/original-audio'
const GENERATED_URL = '/api/examples/b9bcdda92ac7de4e/audio'
const ORIGINAL_NAME = 'comparison-human-jane_eyre_21_f000371.wav'
const GENERATED_NAME = 'comparison-generated-jane_eyre_21_f000371.wav'

function Result({ job, onOpen }: { job?: PairJob; onOpen: (id: string) => void }) {
  if (!job) return <p className="matched-result">Not analyzed in this comparison yet</p>
  if (job.status !== 'completed') return <p className="matched-result" role="status">Analysis {job.status}</p>
  const score = job.result?.synthetic_score
  return <div className="matched-result">
    <span>Detector score <strong>{score == null ? 'Unavailable' : `${Math.round(score * 100)} / 100`}</strong></span>
    <button type="button" onClick={() => onOpen(job.id)}>Open analysis →</button>
  </div>
}

export default function MatchedComparison({ jobs, busy, onAnalyze, onOpen }: Props) {
  const [pair, setPair] = useState<Pair | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/examples/paired-demo', { signal: controller.signal })
      .then(async response => { if (!response.ok) throw Error('The paired audio is unavailable.'); return response.json() as Promise<Pair> })
      .then(setPair)
      .catch(() => { if (!controller.signal.aborted) setError('The paired audio could not be loaded.') })
    return () => controller.abort()
  }, [])

  const humanJob = jobs.find(job => job.filename === ORIGINAL_NAME)
  const generatedJob = jobs.find(job => job.filename === GENERATED_NAME)
  const pending = [humanJob, generatedJob].some(job => job && (job.status === 'queued' || job.status === 'running'))

  async function analyzePair() {
    if (!pair?.available || loading || busy || pending) return
    setLoading(true); setError('')
    try {
      const responses = await Promise.all([fetch(ORIGINAL_URL), fetch(GENERATED_URL)])
      if (responses.some(response => !response.ok)) throw Error('One of the audio files could not be loaded.')
      const blobs = await Promise.all(responses.map(response => response.blob()))
      await onAnalyze([
        new File([blobs[0]], ORIGINAL_NAME, { type: 'audio/wav' }),
        new File([blobs[1]], GENERATED_NAME, { type: 'audio/wav' }),
      ])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The comparison could not be started.')
    } finally { setLoading(false) }
  }

  return <section className="matched-comparison" aria-labelledby="matched-title">
    <div className="matched-heading"><div><span className="eyebrow">START HERE · LISTENING DEMO</span><h2 id="matched-title">Hear the human and generated versions.</h2></div><p>Both clips speak the same Jane Eyre passage. Listen first, then see what the detector says about each recording.</p></div>
    <div className="matched-grid">
      <div className="matched-card"><span className="matched-index">01 / HUMAN READING</span><h3>Original human audio</h3><p>Recorded speech from the public source dataset.</p><audio controls preload="metadata" src={pair?.available ? ORIGINAL_URL : undefined} aria-label="Play original human reading" /><Result job={humanJob} onOpen={onOpen} /></div>
      <div className="matched-card"><span className="matched-index">02 / GENERATED READING</span><h3>Chatterbox-generated audio</h3><p>Computer-generated speech of the same passage.</p><audio controls preload="metadata" src={pair?.available ? GENERATED_URL : undefined} aria-label="Play generated reading" /><Result job={generatedJob} onOpen={onOpen} /></div>
    </div>
    <div className="matched-footer"><div><strong>What this comparison demonstrates</strong><p>Separate, uncalibrated scores for two known-label recordings. The voices may differ; this is a same-passage comparison, not a voice-clone identity test. These clips are illustrative, not an independent accuracy benchmark.</p></div><button type="button" className="primary-button" disabled={!pair?.available || busy || loading || pending} onClick={analyzePair}>{loading ? 'Preparing audio…' : pending ? 'Analyzing pair…' : humanJob && generatedJob ? 'Run comparison again' : 'Analyze both recordings'}</button></div>
    {pair && !pair.available && <p className="matched-error" role="status">Paired audio is not prepared locally. Run the documented example setup with <code>--include-paired-reference</code>.</p>}
    {error && <p className="matched-error" role="alert">{error}</p>}
  </section>
}
