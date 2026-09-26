import PilotExamples from './components/PilotExamples'
import AIInterpretation from './components/AIInterpretation'
import CaseReview from './components/CaseReview'
import ModelValidation from './components/ModelValidation'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { GlassEffect, GlassFilter, GlassButton } from '@/components/ui/liquid-glass'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, ArrowDownToLine, ArrowRight, AudioLines, ChevronDown,
  CircleAlert, Clock3, FileAudio2, FileJson2, FileUp, Headphones,
  Layers3, LoaderCircle, Menu, Pause, Play, Plus,
  RefreshCw, ScanLine, ShieldAlert, SlidersHorizontal, X,
} from 'lucide-react'

type Evidence = { id: string; label: string; value: string | number | null; unit?: string; detail?: string; kind?: string }
type Interval = { start_s: number; end_s: number; score: number }
type Analysis = {
  schema_version: string
  input: { filename: string; sha256?: string; duration_s?: number; sample_rate?: number; channels?: number; codec?: string }
  synthetic_score: number | null
  score_kind: string
  model?: { name?: string; version?: string }
  manipulation_type?: string
  waveform?: number[]
  intervals?: Interval[]
  evidence?: Evidence[]
  limitations?: string[]
  runtime_s?: number
}
type Job = {
  id: string
  filename: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string
  created_at: string
  result: Analysis | null
  error: string | null
  parent_id?: string | null
  transform?: { kind?: string; [key: string]: unknown } | string | null
}
type Health = { status: string; model?: Record<string, unknown> }

const MAX_SIZE = 50 * 1024 * 1024
const audioExtensions = /\.(wav|mp3|m4a|flac|ogg|opus|aac)$/i

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(path, init) }
  catch { throw new Error('Cannot reach the local analysis server. Start the backend on 127.0.0.1:8000.') }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

function shortTime(seconds: number | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return '—'
  const value = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
}
export function intervalTime(seconds: number | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return '—'
  const hundredths = Math.max(0, Math.round(seconds * 100))
  const minutes = Math.floor(hundredths / 6000)
  const remainder = hundredths % 6000
  return `${String(minutes).padStart(2, '0')}:${String(Math.floor(remainder / 100)).padStart(2, '0')}.${String(remainder % 100).padStart(2, '0')}`
}
function displayDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}
function scoreLabel(score: number | null | undefined) {
  return score == null || !Number.isFinite(score) ? '—' : `${Math.round(score * 100)}%`
}
function scoreTone(score: number | null | undefined) {
  return score == null ? 'neutral' : score >= 0.7 ? 'coral' : score >= 0.35 ? 'amber' : 'cyan'
}
function stageLabel(stage: string) {
  return stage.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase())
}
function transformLabel(job: Job) {
  if (!job.transform) return null
  const kind = typeof job.transform === 'string' ? job.transform : job.transform.kind
  return kind === 'mp3' ? 'MP3 compression' : kind === 'noise' ? 'Added noise' : kind || 'Derived clip'
}

function Waveform({ values, intervals, duration, onSeek, currentTime }: {
  values: number[]; intervals: Interval[]; duration: number; onSeek: (time: number) => void; currentTime: number
}) {
  const waveform = values.length ? values : []
  const position = duration > 0 ? Math.min(100, Math.max(0, currentTime / duration * 100)) : 0
  return <div className="waveform-shell">
    <div className="waveform-label"><span>AMPLITUDE / TIME</span><span>{shortTime(duration)}</span></div>
    <div
      className="waveform" role="slider" tabIndex={0} aria-label="Seek audio" aria-valuemin={0}
      aria-valuemax={Math.max(0, Math.round(duration))} aria-valuenow={Math.round(currentTime)}
      aria-valuetext={`${shortTime(currentTime)} of ${shortTime(duration)}`}
      onClick={event => {
        if (!duration) return
        const rect = event.currentTarget.getBoundingClientRect()
        onSeek(Math.min(duration, Math.max(0, (event.clientX - rect.left) / rect.width * duration)))
      }}
      onKeyDown={event => {
        if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
          event.preventDefault(); onSeek(Math.max(0, Math.min(duration, currentTime + (event.key === 'ArrowRight' ? 5 : -5))))
        } else if (event.key === 'Home') { event.preventDefault(); onSeek(0) }
        else if (event.key === 'End') { event.preventDefault(); onSeek(duration) }
      }}
    >
      <div className="waveform-grid" aria-hidden="true" />
      {intervals.map((interval, index) => duration > 0 && <div key={index} className="interval-zone" style={{ left: `${interval.start_s / duration * 100}%`, width: `${Math.max(0, (interval.end_s - interval.start_s) / duration * 100)}%` }} />)}
      <div className="waveform-bars" aria-hidden="true">
        {waveform.map((value, index) => <div key={index} className="waveform-bar" style={{ height: `${Math.max(4, Math.min(100, value * 100))}%` }} />)}
      </div>
      <div className="waveform-playhead" style={{ left: `${position}%` }} aria-hidden="true" />
      {!waveform.length && <span className="waveform-empty">Waveform unavailable for this analysis</span>}
    </div>
    <div className="waveform-ticks" aria-hidden="true"><span>00:00</span><span>{shortTime(duration / 4)}</span><span>{shortTime(duration / 2)}</span><span>{shortTime(duration * 3 / 4)}</span><span>{shortTime(duration)}</span></div>
  </div>
}

export default function App() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checkedIds, setCheckedIds] = useState<string[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [healthChecked, setHealthChecked] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [deriving, setDeriving] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [batchOpen, setBatchOpen] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const audio = useRef<HTMLAudioElement>(null)
  const mobileMenu = useRef<HTMLButtonElement>(null)
  const mobileClose = useRef<HTMLButtonElement>(null)
  const mobileDrawer = useRef<HTMLElement>(null)
  const mainColumn = useRef<HTMLDivElement>(null)
  const skipLink = useRef<HTMLAnchorElement>(null)
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    if (!mobileNav) return
    const drawer = mobileDrawer.current
    const background: HTMLElement[] = []
    if (skipLink.current) background.push(skipLink.current)
    if (mainColumn.current) background.push(mainColumn.current)
    background.forEach(node => {
      node.setAttribute('inert', '')
      node.setAttribute('aria-hidden', 'true')
    })
    mobileClose.current?.focus()

    const containFocus = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setMobileNav(false)
        return
      }
      if (event.key !== 'Tab' || !drawer) return
      const controls = Array.from(drawer.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      ))
      if (!controls.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !drawer.contains(document.activeElement))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !drawer.contains(document.activeElement))) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', containFocus)
    return () => {
      window.removeEventListener('keydown', containFocus)
      background.forEach(node => {
        node.removeAttribute('inert')
        node.removeAttribute('aria-hidden')
      })
      if (mobileMenu.current?.isConnected) mobileMenu.current.focus()
    }
  }, [mobileNav])

  useEffect(() => {
    if (!window.matchMedia) return
    const mobileViewport = window.matchMedia('(max-width: 800px)')
    const closeAtDesktop = (event: MediaQueryListEvent) => {
      if (!event.matches) setMobileNav(false)
    }
    mobileViewport.addEventListener('change', closeAtDesktop)
    return () => mobileViewport.removeEventListener('change', closeAtDesktop)
  }, [])

  const loadJobs = useCallback(async () => {
    const list = await api<Job[]>('/api/analyses')
    const sorted = [...list].sort((a, b) => b.created_at.localeCompare(a.created_at))
    setJobs(sorted)
  }, [])

  useEffect(() => {
    loadJobs().catch(event => setError(event.message))
    api<Health>('/api/health').then(setHealth).catch(() => setHealth(null)).finally(() => setHealthChecked(true))
  }, [loadJobs])

  const activeCount = jobs.filter(job => job.status === 'queued' || job.status === 'running').length
  useEffect(() => {
    if (!activeCount) return
    const timer = window.setInterval(() => loadJobs().catch(event => setError(event.message)), 1500)
    return () => window.clearInterval(timer)
  }, [activeCount, loadJobs])

  const selected = jobs.find(job => job.id === selectedId) || null
  const result = selected?.result
  const children = useMemo(() => jobs.filter(job => job.parent_id === selectedId).sort((a, b) => b.created_at.localeCompare(a.created_at)), [jobs, selectedId])
  const completedCount = jobs.filter(job => job.status === 'completed').length
  const failedCount = jobs.filter(job => job.status === 'failed').length

  useEffect(() => { setCurrentTime(0); setPlaying(false) }, [selectedId])

  async function uploadFiles(files: FileList | File[]) {
    const selectedFiles = Array.from(files)
    if (!selectedFiles.length) return
    const invalid = selectedFiles.find(file => !audioExtensions.test(file.name) || file.size > MAX_SIZE || file.size === 0)
    if (invalid) {
      setError(`${invalid.name}: choose a non-empty WAV, MP3, M4A, FLAC, OGG, OPUS or AAC file under 50 MiB.`)
      return
    }
    setError(null); setUploading(true)
    try {
      for (const file of selectedFiles) {
        const form = new FormData(); form.append('file', file)
        const job = await api<Job>('/api/analyses', { method: 'POST', body: form })
        if (selectedFiles.length === 1) setSelectedId(job.id)
      }
      await loadJobs()
      if (selectedFiles.length > 1) setBatchOpen(true)
    } catch (event) { setError((event as Error).message) }
    finally { setUploading(false); if (fileInput.current) fileInput.current.value = '' }
  }

  async function createDerivative(kind: 'mp3' | 'noise') {
    if (!selected) return
    setError(null); setDeriving(kind)
    try {
      await api<Job>(`/api/analyses/${selected.id}/stress-tests`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }) })
      await loadJobs()
    } catch (event) { setError((event as Error).message) }
    finally { setDeriving(null) }
  }

  async function retryAnalysis() {
    if (!selected) return
    setError(null)
    try {
      await api<Job>(`/api/analyses/${selected.id}/retry`, { method: 'POST' })
      await loadJobs()
    } catch (event) { setError((event as Error).message) }
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function downloadReport() {
    if (!selected) return
    setError(null)
    try {
      const report = await api<Analysis>(`/api/analyses/${selected.id}/report`)
      downloadBlob(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }), `echotrace-${selected.id}.json`)
    } catch (event) { setError((event as Error).message) }
  }

  async function exportCsv() {
    if (!checkedIds.length) return
    setError(null); setExporting(true)
    try {
      const response = await fetch('/api/exports', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: checkedIds }) })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(typeof body?.detail === 'string' ? body.detail : `Export failed (${response.status}).`)
      }
      downloadBlob(await response.blob(), 'echotrace-analyst-export.csv')
    } catch (event) { setError((event as Error).message) }
    finally { setExporting(false) }
  }

  function seek(time: number) {
    if (!audio.current) return
    audio.current.currentTime = time
    setCurrentTime(time)
  }
  async function togglePlay() {
    if (!audio.current) return
    try { if (audio.current.paused) await audio.current.play(); else audio.current.pause() }
    catch { setError('Audio playback is unavailable for this file in your browser.') }
  }

  return <div className="app-shell">
    <a ref={skipLink} className="skip-link" href="#main-content">Skip to workspace</a>
    <GlassFilter />
    <div className="ambient-scene" aria-hidden="true"><div className="ambient-orb orb-one" /><div className="ambient-orb orb-two" /><div className="ambient-grid" /></div>
    <aside ref={mobileDrawer} className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`} aria-label="Analysis history" id="workspace-navigation" role={mobileNav ? 'dialog' : undefined} aria-modal={mobileNav || undefined}>
      <div className="brand"><div className="brand-mark"><AudioLines size={20} strokeWidth={2.2} /></div><div><strong>ECHOTRACE</strong><small>Audio review workspace</small></div><button ref={mobileClose} className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="sidebar-main">
        <div className="sidebar-section-label">WORKSPACE</div>
        <button className={`nav-item ${!batchOpen ? 'nav-active' : ''}`} onClick={() => { setSelectedId(null); setBatchOpen(false); setMobileNav(false) }}><ScanLine size={17} /> Investigation <span>{jobs.length}</span></button>
        <button className={`nav-item ${batchOpen ? 'nav-active' : ''}`} onClick={() => { setBatchOpen(true); setMobileNav(false) }}><Layers3 size={17} /> Batch & export <span>{completedCount}</span></button>
        <div className="sidebar-divider" />
        <div className="sidebar-list-heading"><span>RECENT ANALYSES</span><button className="icon-button" onClick={() => fileInput.current?.click()} aria-label="Add recording"><Plus size={16} /></button></div>
        <div className="job-list">
          {jobs.length ? jobs.filter(job => !job.parent_id).map(job => <button key={job.id} className={`job-row ${selectedId === job.id && !batchOpen ? 'selected' : ''}`} onClick={() => { setSelectedId(job.id); setBatchOpen(false); setMobileNav(false) }}>
            <span className={`job-icon ${job.status}`}><FileAudio2 size={17} /></span><span className="job-row-text"><strong title={job.filename}>{job.filename}</strong><small>{displayDate(job.created_at)}</small></span><span className={`job-indicator ${job.status}`} title={job.status} />
          </button>) : <p className="sidebar-empty">Your recordings will appear here.</p>}
        </div>
      </div>
      <div className="sidebar-footer"><span className={`connection-dot ${health?.status === 'ok' ? 'online' : ''}`} /><div><strong>{!healthChecked ? 'Connecting to local server' : health?.status === 'ok' ? 'Local processing available' : 'Server unavailable'}</strong><small>Files stay on this device</small></div></div>
    </aside>

    {mobileNav && <button className="mobile-scrim" aria-hidden="true" tabIndex={-1} onClick={() => setMobileNav(false)} />}
    <div ref={mainColumn} className="main-column">
      <header className="topbar"><div className="topbar-left"><button ref={mobileMenu} className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileNav} aria-controls="workspace-navigation" onClick={() => setMobileNav(true)}><Menu size={20} /></button><span className="topbar-eyebrow">Audio review / {batchOpen ? 'Batch export' : selected ? 'Recording' : 'Workspace'}</span></div><div className="topbar-right"><button className="topbar-add" onClick={() => fileInput.current?.click()} disabled={uploading}><Plus size={16} /> Add recording</button></div></header>
      <input aria-label="Choose audio recordings" ref={fileInput} className="sr-only" type="file" multiple accept=".wav,.mp3,.m4a,.flac,.ogg,.opus,.aac,audio/*" onChange={event => event.target.files && uploadFiles(event.target.files)} />
      {error && <div className="error-banner" role="alert"><CircleAlert size={18} /><span>{error}</span><button className="icon-button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={17} /></button></div>}

      <main className="content" id="main-content" tabIndex={-1}>
        <AnimatePresence mode="wait" initial={false}>
        <motion.div key={batchOpen ? 'batch' : selectedId || 'intake'} className="view-transition"
          initial={{ opacity: 0, y: reducedMotion ? 0 : 10 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: reducedMotion ? 0 : -6 }} transition={{ duration: reducedMotion ? 0 : 0.18 }}>
        {batchOpen ? <>
          <div className="page-intro"><div><span className="eyebrow">01 / COLLECTION</span><h1>Batch & export</h1><p>Review analyses together and export selected results.</p></div><button className="outline-button" onClick={() => fileInput.current?.click()}><FileUp size={16} /> Add files</button></div>
          <div className="batch-stats"><div><span>ALL FILES</span><strong>{jobs.length}</strong></div><div><span>COMPLETED</span><strong>{completedCount}</strong></div><div><span>IN PROGRESS</span><strong>{activeCount}</strong></div><div><span>FAILED</span><strong>{failedCount}</strong></div></div>
          <GlassEffect as="section" className="batch-panel"><div className="section-heading"><div><span className="eyebrow">ANALYSIS REGISTER</span><h2>Recorded files</h2></div><button className="text-button" onClick={() => loadJobs().catch(event => setError(event.message))}><RefreshCw size={15} /> Refresh</button></div>
            {jobs.length ? <div className="table-scroll"><table><thead><tr><th><input type="checkbox" aria-label="Select all completed results" checked={jobs.filter(job => job.status === 'completed' && job.result?.synthetic_score != null).length > 0 && jobs.filter(job => job.status === 'completed' && job.result?.synthetic_score != null).every(job => checkedIds.includes(job.id))} onChange={event => setCheckedIds(event.target.checked ? jobs.filter(job => job.status === 'completed' && job.result?.synthetic_score != null).map(job => job.id) : [])} /></th><th>RECORDING</th><th>STATUS</th><th>SCORE</th><th>ADDED</th><th aria-label="Open result" /></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td><input type="checkbox" aria-label={`Select ${job.filename}`} checked={checkedIds.includes(job.id)} disabled={job.status !== 'completed' || job.result?.synthetic_score == null} onChange={event => setCheckedIds(current => event.target.checked ? [...current, job.id] : current.filter(id => id !== job.id))} /></td><td><div className="table-name"><FileAudio2 size={16} /><span>{job.filename}{job.parent_id && <small>{transformLabel(job) || 'Derived analysis'}</small>}</span></div></td><td><span className={`status-pill ${job.status}`}>{job.status === 'running' && <LoaderCircle size={12} className="spin" />}{stageLabel(job.status)}</span>{job.error && <small className="table-error" title={job.error}>{job.error}</small>}</td><td><span className={`table-score ${scoreTone(job.result?.synthetic_score)}`}>{scoreLabel(job.result?.synthetic_score)}</span></td><td className="muted">{displayDate(job.created_at)}</td><td><button className="icon-button" aria-label={`Open ${job.filename}`} onClick={() => { setSelectedId(job.id); setBatchOpen(false) }}><ArrowRight size={17} /></button></td></tr>)}</tbody></table></div> : <div className="batch-empty"><FileAudio2 size={28} /><p>No recordings yet. Add one or more audio files to begin.</p></div>}
          </GlassEffect>
          <div className="export-bar"><div><strong>{checkedIds.length} selected for export</strong><span>Analyst CSV: file_id, filename, synthetic_score (0–1). Sponsor submission schema may differ.</span></div><GlassButton className="primary-button" disabled={!checkedIds.length || exporting} onClick={exportCsv}>{exporting ? <LoaderCircle size={16} className="spin" /> : <ArrowDownToLine size={16} />} Export selected CSV</GlassButton></div>
        </> : selected ? <>
          <div className="breadcrumb"><button onClick={() => setSelectedId(null)}>Investigations</button><span>/</span><span>{selected.filename}</span></div>
          <div className="page-intro result-intro"><div><span className="eyebrow">RECORDING / {selected.id.slice(0, 8).toUpperCase()}</span><h1 title={selected.filename}>{selected.filename}</h1><p>{displayDate(selected.created_at)} <span className="dot-separator">·</span> {result?.input.duration_s != null ? shortTime(result.input.duration_s) : 'Duration pending'} <span className="dot-separator">·</span> {result?.input.codec || 'Audio file'}</p></div><button className="outline-button" onClick={downloadReport} disabled={!result}><FileJson2 size={16} /> JSON report</button></div>
          {selected.status === 'failed' ? <GlassEffect as="section" className="state-panel failed-state"><CircleAlert size={24} /><span className="eyebrow">ANALYSIS FAILED</span><h2>This recording could not be analyzed.</h2><p>{selected.error || 'The server did not return a reason.'}</p><div className="failure-actions"><GlassButton className="primary-button" onClick={retryAnalysis}><RefreshCw size={15} /> Retry analysis</GlassButton><button className="outline-button" onClick={() => fileInput.current?.click()}><Plus size={15} /> Add another file</button></div></GlassEffect>
          : selected.status !== 'completed' ? <GlassEffect as="section" className="state-panel processing-state"><div className="processing-orbit"><AudioLines size={32} /></div><span className="eyebrow">{selected.status === 'queued' ? 'WAITING FOR WORKER' : 'ANALYSIS IN PROGRESS'}</span><h2>{selected.status === 'queued' ? 'Queued for analysis' : stageLabel(selected.stage)}</h2><p>Processing stages update as the local pipeline runs. One file is analyzed at a time.</p><div className="processing-stage" role="status" aria-live="polite">CURRENT STAGE / {stageLabel(selected.stage)}</div></GlassEffect>
          : result && <>
            <div className="assessment-layout"><GlassEffect as="section" className="score-panel"><div className="panel-header"><span className="eyebrow">SYNTHESIS ASSESSMENT</span></div><div className={`score-number ${scoreTone(result.synthetic_score)}`}>{scoreLabel(result.synthetic_score)}</div><div className="score-rule"><span className={scoreTone(result.synthetic_score)} style={{ width: `${result.synthetic_score == null ? 0 : Math.max(0, Math.min(100, result.synthetic_score * 100))}%` }} /></div><div className="score-scale"><span>0 / LOW</span><span>100 / HIGH</span></div><div className="score-caption"><ShieldAlert size={16} /><span>{result.synthetic_score == null ? 'No defensible model assessment is available for this file.' : result.score_kind === 'calibrated' ? 'Calibrated synthesis-likelihood estimate' : 'Uncalibrated model score. This is not a verified probability.'}</span></div></GlassEffect>
              <GlassEffect as="section" className="assessment-context"><div className="panel-header"><span className="eyebrow">REVIEW CONTEXT</span><SlidersHorizontal size={17} /></div><div className="context-line"><span>ANALYSIS STATUS</span><strong><span className="status-dot" /> Completed</strong></div><div className="context-line"><span>MODEL</span><strong>{result.model?.name || 'Unavailable'}</strong></div><div className="context-line"><span>PROCESSING TIME</span><strong>{result.runtime_s != null ? `${result.runtime_s.toFixed(1)}s` : '—'}</strong></div><div className="context-line"><span>INPUT</span><strong>{result.input.sample_rate ? `${(result.input.sample_rate / 1000).toFixed(1)} kHz` : '—'} / {result.input.channels ?? '—'} ch</strong></div><p className="context-note">For investigative triage only. The score does not verify speaker identity or recording origin.</p></GlassEffect></div>
            <GlassEffect as="section" className="player-section"><div className="section-heading"><div><span className="eyebrow">02 / LISTEN & INSPECT</span><h2>Audio timeline</h2></div><span className="section-aside">Original recording</span></div><div className="player-content"><button className="play-button" onClick={togglePlay} aria-label={playing ? 'Pause audio' : 'Play audio'}>{playing ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}</button><div className="player-main"><Waveform values={result.waveform || []} intervals={result.intervals || []} duration={result.input.duration_s || 0} currentTime={currentTime} onSeek={seek} /><div className="player-meta"><span><Headphones size={13} /> {shortTime(currentTime)} / {shortTime(result.input.duration_s)}</span><span>{result.intervals?.length ? 'SHADED REGIONS: SCORED WINDOWS' : 'FILE-LEVEL ASSESSMENT'}</span></div></div><audio ref={audio} src={`/api/analyses/${selected.id}/audio`} preload="metadata" onTimeUpdate={event => setCurrentTime(event.currentTarget.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} /></div></GlassEffect>
            <div className="detail-grid"><GlassEffect as="section" className="detail-section"><div className="section-heading"><div><span className="eyebrow">03 / METHOD OUTPUT</span><h2>Forensic observations</h2></div><Activity size={18} className="subtle-icon" /></div>{result.evidence?.length ? <div className="evidence-list">{result.evidence.map((item, index) => <div className="evidence-row" key={`${item.id}-${index}`}><div className="evidence-symbol"><Activity size={16} /></div><div className="evidence-copy"><strong>{item.label}</strong><small>{item.detail || item.kind || 'Measured result'}</small></div><div className="evidence-value">{item.value == null ? '—' : String(item.value)} <span>{item.unit || ''}</span></div></div>)}</div> : <p className="no-data">No technique measurements were returned.</p>}</GlassEffect>
              <GlassEffect as="section" className="detail-section"><div className="section-heading"><div><span className="eyebrow">04 / TIME WINDOWS</span><h2>Intervals for review</h2></div><Clock3 size={18} className="subtle-icon" /></div>{result.intervals?.length ? <><p className="detail-note">Window-level scores point to passages for review; they are not verified edit boundaries.</p><div className="interval-list">{result.intervals.map((interval, index) => <button key={index} onClick={() => seek(interval.start_s)} className="interval-row"><span className="interval-index">{String(index + 1).padStart(2, '0')}</span><span>{intervalTime(interval.start_s)} – {intervalTime(interval.end_s)}</span><span className={`interval-score ${scoreTone(interval.score)}`}>{scoreLabel(interval.score)}</span><Play size={13} /></button>)}</div></> : <p className="no-data">No time-window assessment is available for this file.</p>}</GlassEffect></div>
            <div className="detail-grid bottom-grid"><GlassEffect as="section" className="detail-section"><div className="section-heading"><div><span className="eyebrow">05 / RELIABILITY</span><h2>Measurement limitations</h2></div><CircleAlert size={18} className="subtle-icon" /></div><div className="limitations">{result.limitations?.length ? result.limitations.map((limitation, index) => <p key={index}><span>0{index + 1}</span>{limitation}</p>) : <p><span>01</span>No additional limitations were returned. A low score does not establish authenticity.</p>}</div><details className="technical-details"><summary>Technical provenance <ChevronDown size={16} /></summary><dl><dt>SHA-256</dt><dd>{result.input.sha256 || 'Unavailable'}</dd><dt>Model version</dt><dd>{result.model?.version || 'Unavailable'}</dd><dt>Schema</dt><dd>{result.schema_version}</dd><dt>Manipulation type</dt><dd>{result.manipulation_type || 'Undetermined'}</dd></dl></details></GlassEffect>
              <GlassEffect as="section" className="detail-section"><div className="section-heading"><div><span className="eyebrow">06 / COMPARISON</span><h2>Stress comparison</h2></div><SlidersHorizontal size={18} className="subtle-icon" /></div><p className="detail-note">Analyze a derived copy to see how this assessment changes under a named transformation.</p><div className="compare-actions"><button className="outline-button" disabled={!!deriving || !!selected.parent_id} onClick={() => createDerivative('mp3')}>{deriving === 'mp3' ? <LoaderCircle className="spin" size={15} /> : <AudioLines size={15} />} MP3 compression</button><button className="outline-button" disabled={!!deriving || !!selected.parent_id} onClick={() => createDerivative('noise')}>{deriving === 'noise' ? <LoaderCircle className="spin" size={15} /> : <Activity size={15} />} Add noise</button></div>{selected.parent_id && <button className="text-button" onClick={() => setSelectedId(selected.parent_id!)}><ArrowRight size={14} /> Open original analysis</button>}{children.length > 0 && <div className="comparison-list">{children.map(child => <div className="comparison-row" key={child.id}><div className="comparison-source"><strong>{transformLabel(child)}</strong><small>{child.status === 'completed' ? `Original ${scoreLabel(result.synthetic_score)} → derived ${scoreLabel(child.result?.synthetic_score)}` : stageLabel(child.stage)}</small>{child.status === 'completed' && <audio controls preload="none" aria-label={`Play ${transformLabel(child)} recording`} src={`/api/analyses/${child.id}/audio`} />}</div><div className="comparison-numbers"><strong className={scoreTone(child.result?.synthetic_score)}>{child.status === 'completed' ? scoreLabel(child.result?.synthetic_score) : '—'}</strong>{child.status === 'completed' && result.synthetic_score != null && child.result?.synthetic_score != null && <small>{`${(child.result.synthetic_score - result.synthetic_score) >= 0 ? '+' : ''}${Math.round((child.result.synthetic_score - result.synthetic_score) * 100)} pts`}</small>}</div><button className="icon-button" aria-label={`Open ${transformLabel(child)} result`} onClick={() => setSelectedId(child.id)}><ArrowRight size={16} /></button></div>)}</div>}<p className="compare-caveat">A stable score does not prove a recording is genuine.</p></GlassEffect></div>
            <AIInterpretation jobId={selected.id} />
            <CaseReview jobId={selected.id} onSeek={seek} />
            <ModelValidation />
          </>}
        </> : <div className="empty-layout">
          <div className="page-intro"><div><span className="eyebrow">HEARSAY · Audio authentication</span><h1>Review a recording.</h1><p>Examine synthetic speech indicators and the evidence behind them.</p></div></div>
          <GlassEffect className="empty-workspace">
            <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={event => { event.preventDefault(); setDragging(false) }} onDrop={event => { event.preventDefault(); setDragging(false); uploadFiles(event.dataTransfer.files) }}>
              <div className="drop-icon"><FileAudio2 size={32} strokeWidth={1.25} /></div>
              <h2>Add audio for review</h2><p>Drop one recording or a collection of files.</p>
              <GlassButton className="primary-button" onClick={() => fileInput.current?.click()} disabled={uploading}>{uploading ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}{uploading ? 'Adding recordings…' : 'Choose audio files'}</GlassButton>
              <small>WAV, MP3, M4A and other common formats<br />50 MiB · 2 minutes per recording</small>
            </div>
            <div className="intake-guide"><span className="eyebrow">What the review includes</span>
              <div><span>01</span><section><h3>Synthetic speech assessment</h3><p>A model score with its calibration status and limitations.</p></section></div>
              <div><span>02</span><section><h3>Recording evidence</h3><p>Playback, scored intervals and measured signal characteristics.</p></section></div>
              <div><span>03</span><section><h3>Comparison & reporting</h3><p>Compare a trusted voice, transcribe speech, review claims, and export evidence.</p></section></div>
              <p className="intake-boundary">Speaker identity and factual claims require separate evidence. They are not determined by the synthesis score.</p>
            </div>
          </GlassEffect>
          <PilotExamples busy={uploading} onAnalyze={file => uploadFiles([file])} />
          <div className="recent-heading"><h2>Recent recordings</h2><button className="text-button" onClick={() => setBatchOpen(true)}>View all <ArrowRight size={16} /></button></div>
          <GlassEffect className="recent-recordings">{jobs.filter(job => !job.parent_id).slice(0,4).map(job => <button key={job.id} className="recent-recording" onClick={() => setSelectedId(job.id)}><FileAudio2 size={22} strokeWidth={1.5}/><span><strong>{job.filename}</strong><small>{displayDate(job.created_at)}</small></span><span className="recent-status">{stageLabel(job.status)}</span><ArrowRight size={17}/></button>)}{!jobs.some(job => !job.parent_id) && <p>Your recordings will appear here after you add audio.</p>}</GlassEffect>
          <p className="workspace-footnote">Original files are preserved. Analysis runs on this device.</p>
        </div>}

        </motion.div>
        </AnimatePresence>
      </main>
    </div>
  </div>
}
