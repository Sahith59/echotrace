import { useMemo, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { AudioWaveform, Ban, FileAudio2, FileText, Fingerprint, Gauge, Plus, ScanLine, ShieldQuestion, Sparkles, Split, Waves } from 'lucide-react'
import { Link } from '../lib/router'
import { useSession } from '../lib/session'
import { tabKeys } from './Story'
import { WORKSPACE_URL } from '../config'

// Measured results from the project's frozen evaluations (docs/model-serving-decision.md, docs/cluster-run-2026-09-25.md).
const RESULTS = {
  serving: {
    button: 'Serving model',
    name: 'NII wav2vec-small anti-deepfake',
    caught: 937, flagged: 24, recall: '93.7%', fpr: '2.4%', auroc: '0.9925',
    status: 'Serves new analyses in the workspace',
    note: 'Frozen In-the-Wild public benchmark, 1,000 genuine and 1,000 synthetic recordings, threshold 0.5 fixed in advance. The model authors had evaluated this dataset before, so this is a replication, not a test on the sponsor’s data.',
  },
  run03: {
    button: 'Adapted experiment',
    name: 'Adapted wav2vec2, GPU run 03',
    caught: 874, flagged: 244, recall: '87.4%', fpr: '24.4%', auroc: '0.906',
    status: 'Not promoted',
    note: 'Balanced 2,000-file ASVspoof 5 holdout. It cleared the recall goal but missed the 5% false-alarm goal, mostly on compressed genuine audio, so it stays out of the workspace.',
  },
} as const
type ResultKey = keyof typeof RESULTS

// A fixed pseudo-random order so errors scatter naturally and the same dots change between models.
function seededOrder(count: number, seed: number) {
  const order = Array.from({ length: count }, (_, i) => i)
  let state = seed >>> 0
  const random = () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  for (let i = count - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  const rank = new Array<number>(count)
  order.forEach((position, index) => { rank[position] = index })
  return rank
}
const GENUINE_RANK = seededOrder(1000, 11)
const SYNTHETIC_RANK = seededOrder(1000, 29)

export function Benchmark() {
  const [key, setKey] = useState<ResultKey>('serving')
  const result = RESULTS[key]
  const genuine = useMemo(() => GENUINE_RANK.map(rank => rank < result.flagged ? 'dot flagged' : 'dot correct-genuine'), [result.flagged])
  const synthetic = useMemo(() => SYNTHETIC_RANK.map(rank => rank < 1000 - result.caught ? 'dot missed' : 'dot caught'), [result.caught])

  return (
    <section className="section shell" id="benchmark" aria-labelledby="benchmark-title">
      <div className="section-head">
        <h2 id="benchmark-title">Measured, including where it fails.</h2>
        <p>Each dot is one real recording from a frozen public test. Switch models to see why a detector that looked promising was kept out of the product.</p>
      </div>
      <div className="bench glass">
        <div className="bench-field" role="img" aria-label={`${result.name}: ${result.caught} of 1,000 synthetic recordings caught and ${result.flagged} of 1,000 genuine recordings wrongly flagged.`}>
          <div className="bench-groups">
            <div className="bench-group">
              <h3>1,000 genuine recordings</h3>
              <div className="dots">{genuine.map((className, index) => <span key={index} className={className} />)}</div>
            </div>
            <div className="bench-group">
              <h3>1,000 synthetic recordings</h3>
              <div className="dots">{synthetic.map((className, index) => <span key={index} className={className} />)}</div>
            </div>
          </div>
          <div className="legend">
            <span><i className="swatch" style={{ background: '#ffffff8c' }} />Genuine, correctly passed</span>
            <span><i className="swatch square" style={{ background: 'var(--high)' }} />Genuine, wrongly flagged</span>
            <span><i className="swatch" style={{ background: 'var(--low)' }} />Synthetic, caught</span>
            <span><i className="swatch square" style={{ background: 'var(--mid)' }} />Synthetic, missed</span>
          </div>
        </div>
        <div className="bench-side">
          <div className="toggle-row" role="group" aria-label="Choose a model">
            {(Object.keys(RESULTS) as ResultKey[]).map(option => (
              <button key={option} type="button" className="chip" aria-pressed={option === key} onClick={() => setKey(option)}>
                {RESULTS[option].button}
              </button>
            ))}
          </div>
          <div aria-live="polite">
            <p className="bench-note"><strong style={{ color: '#fff' }}>{result.name}</strong> · {result.status}</p>
          </div>
          <div className="stat"><strong>{result.recall}</strong><span>of synthetic recordings caught ({result.caught.toLocaleString()} of 1,000)</span></div>
          <div className="stat"><strong>{result.fpr}</strong><span>of genuine recordings wrongly flagged ({result.flagged} of 1,000)</span></div>
          <div className="stat"><strong>{result.auroc}</strong><span>AUROC, how well scores rank synthetic above genuine</span></div>
          <p className="bench-note">{result.note}</p>
        </div>
      </div>
    </section>
  )
}

const STAGES = [
  { icon: FileAudio2, title: 'Add', sub: 'Your recording', heading: 'Add a recording', body: 'WAV, MP3, M4A, FLAC, OGG, Opus or AAC up to 50 MiB. The original file is kept exactly as uploaded and hashed.', points: ['Single files or a batch', 'Originals are never modified', 'Uploads never train the model'] },
  { icon: Waves, title: 'Decode', sub: 'FFmpeg', heading: 'Decode to one format', body: 'FFmpeg converts the audio to 16 kHz mono so the model always hears the same kind of input.', points: ['Corrupt or unsupported files fail with a clear reason', 'Nothing is silently trimmed'] },
  { icon: Gauge, title: 'Measure', sub: 'Signal checks', heading: 'Measure the signal', body: 'Six measurements describe the recording: average level, peak, clipping, quiet frames, spectral centroid and high-band energy.', points: ['Very quiet audio gets no score', 'Measurements describe; they do not decide'] },
  { icon: ScanLine, title: 'Detect', sub: 'NII model', heading: 'Score the whole file', body: 'The pinned NII wav2vec-small model scores the complete recording once, up to 30 seconds, and returns an uncalibrated 0–100 score.', points: ['Checksum-verified weights, verified against the official implementation', 'Longer recordings are rejected, not cut'] },
  { icon: Sparkles, title: 'Explain', sub: 'Optional AI', heading: 'Explain the evidence', body: 'An optional Groq-written brief summarises the measurements. Each finding cites the measurement it relies on.', points: ['Receives numbers only, never audio or transcripts', 'Cannot change the score'] },
  { icon: FileText, title: 'Report', sub: 'Case export', heading: 'Hand off the case', body: 'Export a case as JSON or a printable page, or selected results as an analyst CSV, with hashes and model versions attached.', points: ['Synthesis, voice and claims stay separate', 'No combined authenticity number'] },
] as const

export function HowItWorks() {
  const [active, setActive] = useState(3)
  const stage = STAGES[active]
  const reduced = useReducedMotion()
  return (
    <section className="section shell" id="how-it-works" aria-labelledby="how-title">
      <div className="section-head">
        <h2 id="how-title">What happens to a recording.</h2>
        <p>Every analysis runs on the ECHOTRACE server, in this order. Select a stage to see what it does and what it refuses to do.</p>
      </div>
      <div className="pipeline glass">
        <div className="rail" role="tablist" aria-label="Analysis stages"
          onKeyDown={tabKeys(STAGES.length, active, setActive, index => `stage-tab-${index}`)}>
          <div className="rail-track" aria-hidden="true">
            <motion.div className="rail-progress" animate={{ scaleX: active / (STAGES.length - 1) }} transition={{ type: 'spring', stiffness: 200, damping: 30 }} />
          </div>
          {STAGES.map((item, index) => (
            <button key={item.title} id={`stage-tab-${index}`} type="button" role="tab" className="node" aria-selected={index === active}
              aria-controls="stage-detail" tabIndex={index === active ? 0 : -1} onClick={() => setActive(index)}>
              <span className="node-icon"><item.icon size={24} aria-hidden="true" /></span>
              <span><strong>{item.title}</strong><br /><small>{item.sub}</small></span>
            </button>
          ))}
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={stage.title} id="stage-detail" role="tabpanel" aria-labelledby={`stage-tab-${active}`} className="node-detail"
            initial={{ opacity: 0, y: reduced ? 0 : 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <div><h3>{stage.heading}</h3><p>{stage.body}</p></div>
            <ul>{stage.points.map(point => <li key={point}>{point}</li>)}</ul>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  )
}

function embedFor(url: string) {
  const youtube = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/))([\w-]{11})/)
  if (youtube) return `https://www.youtube-nocookie.com/embed/${youtube[1]}`
  const vimeo = url.match(/vimeo\.com\/(?:video\/)?(\d+)/)
  if (vimeo) return `https://player.vimeo.com/video/${vimeo[1]}`
  return null
}

export function Demo({ videoUrl }: { videoUrl: string }) {
  const reduced = useReducedMotion()
  const embed = videoUrl ? embedFor(videoUrl) : null
  return (
    <section className="section shell" id="demo" aria-labelledby="demo-title">
      <div className="section-head">
        <h2 id="demo-title">Watch a full investigation.</h2>
        <p>A recorded walkthrough of the workspace: a genuine recording, a synthetic one, a known miss, a stress test and a case export.</p>
      </div>
      <div className="demo-frame glass">
        {videoUrl && embed && <iframe src={embed} title="ECHOTRACE demo video" allow="fullscreen; picture-in-picture" loading="lazy" />}
        {videoUrl && !embed && <video src={videoUrl} controls preload="metadata" playsInline aria-label="ECHOTRACE demo video" />}
        {!videoUrl && <>
          <svg className="demo-rings" viewBox="0 0 800 450" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            {[80, 140, 200, 260].map((radius, index) => (
              <motion.circle key={radius} cx="400" cy="225" r={radius} fill="none" stroke="#ffffff" strokeOpacity={0.22 - index * 0.04}
                animate={reduced ? undefined : { scale: [1, 1.06, 1] }} transition={{ duration: 4, repeat: Infinity, delay: index * 0.5, ease: 'easeInOut' }}
                style={{ transformOrigin: '400px 225px' }} />
            ))}
          </svg>
          <div className="demo-placeholder">
            <div className="demo-play"><AudioWaveform size={34} aria-hidden="true" /></div>
            <h3>The demo video is on its way.</h3>
            <p>We are recording a complete walkthrough of the workspace. It will play right here once it is published.</p>
          </div>
        </>}
      </div>
    </section>
  )
}

const LIMITS = [
  [Fingerprint, 'Who is speaking', 'Voice similarity needs a trusted reference, and a clone or replay can match it.'],
  [ShieldQuestion, 'Whether someone meant to deceive', 'Intent is outside what audio analysis can measure.'],
  [Ban, 'Whether a statement is true', 'Claim review records sources you checked. It is not lie detection.'],
  [Split, 'Where an edit happened', 'The model scores the whole recording. It does not locate splices.'],
  [Gauge, 'An exact probability', 'Scores are uncalibrated. A low score does not prove a recording is genuine.'],
  [Waves, 'Performance on every kind of audio', 'Public benchmark results are not a guarantee on new data. Compressed genuine speech is a known weak spot.'],
] as const

export function Limits() {
  return (
    <section className="section shell" id="limits" aria-labelledby="limits-title">
      <div className="section-head">
        <h2 id="limits-title">What ECHOTRACE will not tell you.</h2>
        <p>Knowing the boundaries is part of using a detector well. The workspace repeats these next to every result.</p>
      </div>
      <div className="limits">
        {LIMITS.map(([Icon, title, body]) => (
          <div key={title} className="limit">
            <Icon size={20} aria-hidden="true" />
            <div><h3>{title}</h3><p>{body}</p></div>
          </div>
        ))}
      </div>
    </section>
  )
}

const FAQS = [
  ['Does uploading a recording train the model?', 'No. The workspace runs fixed, checksum-verified model weights. Training happens separately, offline, on frozen labelled datasets.'],
  ['Where does my audio go?', 'Recordings you add are analysed on the ECHOTRACE server and stored in your account, where only you can open them. You can delete any recording, or your whole account, from Settings. The optional AI brief receives measured numbers only, never audio, filenames or transcripts.'],
  ['What files can I analyse?', 'WAV, MP3, M4A, FLAC, OGG, Opus and AAC up to 50 MiB. The detector scores recordings up to 30 seconds; longer files are rejected instead of being cut short.'],
  ['What does a score of 86 mean?', 'That the model found strong synthetic-speech indicators. It is an uncalibrated score, not an 86% probability, and it says nothing about who is speaking.'],
  ['Why show a model that failed?', 'Because an analyst should see how a detector behaves before trusting it. Every experiment that missed its goals stays visible and out of the product.'],
  ['What was ECHOTRACE built for?', 'The NSA HEARSAY audio authentication challenge at HackGT 13: audio in, several forensic techniques, a 0–100 synthesis score and a batch export.'],
] as const

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)
  const reduced = useReducedMotion()
  return (
    <section className="section shell" id="faq" aria-labelledby="faq-title">
      <div className="section-head">
        <h2 id="faq-title">Questions people ask first.</h2>
        <p>Something else on your mind? The guide in the corner answers from the same verified product facts.</p>
      </div>
      <div className="faq">
        {FAQS.map(([question, answer], index) => (
          <div key={question} className="faq-item glass">
            <h3>
              <button type="button" aria-expanded={open === index} aria-controls={`faq-${index}`} onClick={() => setOpen(open === index ? null : index)}>
                {question}<Plus size={20} aria-hidden="true" />
              </button>
            </h3>
            <AnimatePresence initial={false}>
              {open === index && (
                <motion.div id={`faq-${index}`} className="faq-answer" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }} transition={{ duration: reduced ? 0 : 0.22 }} style={{ overflow: 'hidden' }}>
                  <p>{answer}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Closing() {
  const { user } = useSession()
  return (
    <section className="shell" id="signup" aria-labelledby="closing-title">
      <div className="closing glass">
        <div>
          <h2 id="closing-title">{user ? `Your workspace is ready, ${user.name.split(' ')[0]}.` : 'Start your first review.'}</h2>
          <p>{user ? 'Open the workspace to add a recording. The guide in the corner stays available if you get stuck.' : 'Create an account with Google or email, open the workspace and add a recording you are allowed to analyse. It takes about a minute.'}</p>
        </div>
        <div className="closing-actions">
          {user
            ? <a className="btn btn-light" href={WORKSPACE_URL}>Open workspace</a>
            : <>
              <Link className="btn btn-light" to="/signup">Create an account</Link>
              <Link className="btn btn-quiet" to="/login">Log in</Link>
            </>}
        </div>
      </div>
    </section>
  )
}
