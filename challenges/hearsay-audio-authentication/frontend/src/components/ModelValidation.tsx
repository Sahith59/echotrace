import { useEffect, useState } from 'react'

type Metrics = {
  recall: number | null
  false_positive_rate: number | null
  roc_auc: number | null
  genuine_count?: number
  synthetic_count?: number
}
type Slice = { value: string; sample_count: number; baseline: Metrics; candidate: Metrics }
type Experiment = {
  name: string; promoted: boolean; reason: string; sample_count: number
  baseline: Metrics; candidate: Metrics; codec_slices?: Slice[]
  baseline_model?: string; candidate_model?: string
}
type Evaluation = { scope: string; serving_model: string; experiments: Experiment[] }
const percentage = (value: number | null) => value == null ? 'Not available' : `${(value * 100).toFixed(1)}%`
const auc = (value: number | null) => value == null ? 'Not available' : value.toFixed(3)

function ExperimentReview({ experiment }: { experiment: Experiment }) {
  const [condition, setCondition] = useState('__all__')
  const slice = experiment.codec_slices?.find(item => item.value === condition)
  const { baseline, candidate } = slice ?? experiment
  return <section>
    <h3>{experiment.name}</h3>
    {experiment.baseline_model && <p className="case-help">Baseline: {experiment.baseline_model} · Candidate: {experiment.candidate_model ?? "Not specified"}</p>}
    <p className="case-help">{experiment.promoted ? 'Promoted after evaluation' : 'Experimental · not serving'} · {experiment.sample_count.toLocaleString()} evaluated recordings</p>
    {!!experiment.codec_slices?.length && <div className="validation-condition">
      <label>Recording condition
        <select aria-label={`Recording condition — ${experiment.name}`} value={condition} onChange={event => setCondition(event.target.value)}>
          <option value="__all__">All recording conditions</option>
          {experiment.codec_slices.map(item => <option key={item.value} value={item.value}>Dataset codec {item.value} · {item.sample_count.toLocaleString()} recordings</option>)}
        </select>
      </label>
      <p className="case-help">These are benchmark metadata codes, not an automatic label for this recording. All rows use the same previously selected threshold.</p>
    </div>}
    {candidate.genuine_count != null && candidate.synthetic_count != null && <p className="case-help" aria-live="polite">{candidate.genuine_count.toLocaleString()} genuine · {candidate.synthetic_count.toLocaleString()} synthetic</p>}
    <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>
      <tr><td>Synthetic recordings caught</td><td>{percentage(baseline.recall)}</td><td>{percentage(candidate.recall)}</td></tr>
      <tr><td>Genuine recordings falsely flagged</td><td>{percentage(baseline.false_positive_rate)}</td><td>{percentage(candidate.false_positive_rate)}</td></tr>
      <tr><td>AUROC</td><td>{auc(baseline.roc_auc)}</td><td>{auc(candidate.roc_auc)}</td></tr>
    </tbody></table></div>
    <p className="case-help">{experiment.reason}</p>
  </section>
}

export default function ModelValidation() {
  const [data, setData] = useState<Evaluation | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/model/evaluation', { signal: controller.signal })
      .then(response => { if (!response.ok) throw Error(); return response.json() })
      .then(setData).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [])
  return <details className="model-validation detail-section case-panel">
    <summary>Detector validation · measured performance</summary>
    {error ? <p className="case-help">Validation summary could not be loaded. Refresh to retry.</p>
      : !data ? <p className="case-help">Loading validation…</p>
        : <><p className="case-help">Serving: {data.serving_model}. {data.scope}</p>
          {data.experiments.map(experiment => <ExperimentReview key={experiment.name} experiment={experiment} />)}</>}
  </details>
}
