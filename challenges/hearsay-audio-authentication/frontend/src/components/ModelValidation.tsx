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
type ServingBenchmark = Metrics & {
  name: string; model: string; sample_count: number; genuine_count: number; synthetic_count: number
  threshold: number; reason: string; status?: string; model_scored_count?: number
}
type Evaluation = { scope: string; serving_model: string; experiments: Experiment[]; serving_benchmarks?: ServingBenchmark[] }
const percentage = (value: number | null) => value == null ? 'Not available' : `${(value * 100).toFixed(1)}%`
const auc = (value: number | null) => value == null ? 'Not available' : value.toFixed(3)

function ExperimentReview({ experiment }: { experiment: Experiment }) {
  const [condition, setCondition] = useState('__all__')
  const slice = experiment.codec_slices?.find(item => item.value === condition)
  const { baseline, candidate } = slice ?? experiment
  return <details className="validation-study">
    <summary>{experiment.name} <span>{experiment.promoted ? 'Adopted' : 'Not used in the app'}</span></summary>
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
  </details>
}

function ServingBenchmarkReview({ benchmark }: { benchmark: ServingBenchmark }) {
  const missed = benchmark.recall == null ? null : benchmark.synthetic_count - Math.round(benchmark.recall * benchmark.synthetic_count)
  const falseAlarms = benchmark.false_positive_rate == null ? null : Math.round(benchmark.false_positive_rate * benchmark.genuine_count)
  return <section className="validation-study-card">
    <span className="validation-study-label">{benchmark.status === 'failed_quality_goal' ? 'HARDER STRESS SAMPLE' : 'PUBLIC REPLICATION'}</span>
    <h3>{benchmark.name}</h3>
    {benchmark.status === 'failed_quality_goal' && <p className="validation-warning"><strong>Goal missed here.</strong> A detector that misses generated voices or alarms on human voices needs a human reviewer.</p>}
    {missed != null && falseAlarms != null && <p className="validation-takeaway">Of <strong>{benchmark.synthetic_count} generated clips</strong>, it missed <strong>{missed}</strong>. Of <strong>{benchmark.genuine_count} human clips</strong>, it incorrectly flagged <strong>{falseAlarms}</strong>.</p>}
    <details className="validation-study"><summary>See test numbers and method</summary>
    <p className="case-help">Serving model: {benchmark.model} · {benchmark.sample_count.toLocaleString()} selected recordings</p>
    {benchmark.model_scored_count != null && benchmark.model_scored_count !== benchmark.sample_count && <p className="case-help">{benchmark.model_scored_count.toLocaleString()} scored · {(benchmark.sample_count - benchmark.model_scored_count).toLocaleString()} outside the product's analysis scope</p>}
    <p className="case-help">{benchmark.genuine_count.toLocaleString()} genuine · {benchmark.synthetic_count.toLocaleString()} synthetic · fixed threshold {benchmark.threshold}</p>
    <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Observed result</th></tr></thead><tbody>
      <tr><td>Synthetic recordings caught</td><td>{percentage(benchmark.recall)}</td></tr>
      <tr><td>Genuine recordings falsely flagged</td><td>{percentage(benchmark.false_positive_rate)}</td></tr>
      <tr><td>AUROC</td><td>{auc(benchmark.roc_auc)}</td></tr>
    </tbody></table></div>
    <p className="case-help">{benchmark.reason}</p>
    </details>
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
    <summary>How well has the detector worked on other recordings?</summary>
    {error ? <p className="case-help">Validation summary could not be loaded. Refresh to retry.</p>
      : !data ? <p className="case-help">Loading validation…</p>
        : <><p className="validation-explainer"><strong>This tests the model, not your current recording.</strong> We gave it other audio files whose human or generated origin was already labeled, then counted its misses and false alarms. These are public tests, not the NSA sponsor test.</p>
          {data.serving_benchmarks?.map(benchmark => <ServingBenchmarkReview key={benchmark.name} benchmark={benchmark} />)}
          {!!data.experiments.length && <details className="validation-study validation-history"><summary>Earlier model experiments ({data.experiments.length})</summary>{data.experiments.map(experiment => <ExperimentReview key={experiment.name} experiment={experiment} />)}</details>}
          <details className="validation-study validation-history"><summary>Dataset and model provenance</summary><p className="case-help">Current model: {data.serving_model}. {data.scope}</p></details></>}
  </details>
}
