import { useEffect, useState } from 'react'
import './PilotExamples.css'

type PilotExample = {
  id: string
  filename: string
  label: 'genuine' | 'synthetic'
  available: boolean
}

type ExampleCatalog = {
  dataset: string
  note: string
  examples: PilotExample[]
  reason?: string
}

type PilotExamplesProps = {
  onAnalyze: (file: File) => Promise<void>
  busy: boolean
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed.'
}

async function responseError(response: Response) {
  const body = await response.json().catch(() => null) as { detail?: unknown; reason?: unknown } | null
  const detail = body?.detail ?? body?.reason
  return typeof detail === 'string' ? detail : `Request failed (${response.status}).`
}

function audioPath(id: string) {
  return `/api/examples/${encodeURIComponent(id)}/audio`
}

export default function PilotExamples({ onAnalyze, busy }: PilotExamplesProps) {
  const [open, setOpen] = useState(false)
  const [catalog, setCatalog] = useState<ExampleCatalog | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [audioError, setAudioError] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')
  const [fetchingAudio, setFetchingAudio] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!open || catalog) return
    const controller = new AbortController()
    setLoading(true)
    setLoadError('')
    fetch('/api/examples', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(await responseError(response))
        return response.json() as Promise<ExampleCatalog>
      })
      .then(data => {
        if (!data || !Array.isArray(data.examples)) throw new Error('The sample catalog is unavailable.')
        setCatalog(data)
        setSelectedId(data.examples.find(example => example.available)?.id ?? '')
      })
      .catch(error => {
        if (!controller.signal.aborted) setLoadError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [open, catalog, attempt])

  const selected = catalog?.examples.find(example => example.id === selectedId && example.available)

  async function analyzeSample() {
    if (!selected || busy || fetchingAudio) return
    setFetchingAudio(true)
    setAnalyzeError('')
    try {
      const response = await fetch(audioPath(selected.id))
      if (!response.ok) throw new Error(await responseError(response))
      const blob = await response.blob()
      if (!blob.size) throw new Error('The sample audio is empty.')
      const basename = selected.filename.split(/[\\/]/).pop() || `${selected.id}.wav`
      const file = new File([blob], `known-${selected.label}-${basename}`, {
        type: blob.type || 'audio/wav',
      })
      await onAnalyze(file)
    } catch (error) {
      setAnalyzeError(errorMessage(error))
    } finally {
      setFetchingAudio(false)
    }
  }

  return <details className="pilot-examples" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Try a known recording <span aria-hidden="true" className="pilot-examples-chevron">⌄</span></summary>
    <div className="pilot-examples-body">
      <p className="pilot-examples-intro">Compare the detector result with a known reference label. The label is for your review; it is not used to score the audio and does not train the model.</p>
      {loading && <p role="status" className="pilot-examples-status">Loading recordings…</p>}
      {loadError && <div role="alert" className="pilot-examples-status"><p>Recordings could not be loaded. {loadError}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Try again</button></div>}
      {catalog && <>
        <p className="pilot-examples-source">{catalog.dataset}{catalog.note ? ` · ${catalog.note}` : ''}</p>
        {catalog.examples.length === 0 && <p className="pilot-examples-status">{catalog.reason || 'No known recordings are configured.'}</p>}
        {catalog.examples.length > 0 && !catalog.examples.some(example => example.available) && <p className="pilot-examples-status">{catalog.reason || 'The known recordings are listed but their audio files are unavailable.'}</p>}
        {catalog.examples.some(example => example.available) && <>
          <label className="pilot-examples-label" htmlFor="pilot-example-select">Recording</label>
          <select id="pilot-example-select" value={selectedId} onChange={event => { setSelectedId(event.target.value); setAudioError(false); setAnalyzeError('') }}>
            {catalog.examples.map(example => <option key={example.id} value={example.id} disabled={!example.available}>
              {example.filename} · known {example.label}{example.available ? '' : ' · unavailable'}
            </option>)}
          </select>
          {selected && <div className="pilot-examples-selection">
            <span className="pilot-examples-reference">Reference label: <strong>{selected.label}</strong></span>
            <audio key={selected.id} controls preload="none" src={audioPath(selected.id)} aria-label={`Preview ${selected.filename}`} onError={() => setAudioError(true)} />
            {audioError && <p role="alert" className="pilot-examples-status">Preview is unavailable for this recording.</p>}
          </div>}
          <button type="button" className="pilot-examples-action" disabled={!selected || busy || fetchingAudio} onClick={analyzeSample}>
            {fetchingAudio ? 'Loading sample…' : 'Analyze this sample'}
          </button>
          {analyzeError && <p role="alert" className="pilot-examples-status">{analyzeError}</p>}
        </>}
      </>}
    </div>
  </details>
}
