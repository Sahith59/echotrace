import { useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { AudioLines, Check, FileText, Headphones, Info, Mic, ScrollText } from 'lucide-react'
import SignalField from '../components/SignalField'
import { Link, scrollToSection } from '../lib/router'
import { useSession } from '../lib/session'
import { WORKSPACE_URL } from '../config'

const spring = { type: 'spring', stiffness: 380, damping: 34 } as const

// Arrow keys move between tabs and select them, following the ARIA tabs pattern.
export function tabKeys(count: number, active: number, select: (index: number) => void, idFor: (index: number) => string) {
  return (event: React.KeyboardEvent) => {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }
    let next = active
    if (event.key in keys) next = (active + keys[event.key] + count) % count
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = count - 1
    else return
    event.preventDefault()
    select(next)
    document.getElementById(idFor(next))?.focus()
  }
}

function formatClock(seconds: number) {
  const whole = Math.max(0, seconds)
  return `00:${String(Math.floor(whole)).padStart(2, '0')}.${String(Math.floor((whole % 1) * 100)).padStart(2, '0')}`
}

export function Hero() {
  const { user } = useSession()
  const reduced = useReducedMotion()
  const clock = useRef<HTMLElement>(null)
  const level = useRef<HTMLElement>(null)
  const mode = useRef<HTMLElement>(null)
  const rise = (delay: number) => ({
    initial: { opacity: 0, y: reduced ? 0 : 18 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.6, delay: reduced ? 0 : delay, ease: [0.2, 0.7, 0.2, 1] as const },
  })

  return (
    <section className="hero shell" id="top" aria-labelledby="hero-title">
      <div className="hero-copy">
        <motion.h1 id="hero-title" {...rise(0.05)}>Listen closer before you trust a voice.</motion.h1>
        <motion.p className="hero-lede" {...rise(0.18)}>
          ECHOTRACE helps analysts review a suspicious recording: a learned synthetic-speech score, the measured audio
          behind it, a check of how far to trust it, and a case report the next person can reproduce.
        </motion.p>
        <motion.div className="hero-actions" {...rise(0.3)}>
          {user
            ? <a className="btn btn-primary" href={WORKSPACE_URL}>Open workspace</a>
            : <Link className="btn btn-primary" to="/signup">Create an account</Link>}
          <button type="button" className="btn btn-quiet" onClick={() => scrollToSection('demo')}>
            <Headphones size={18} aria-hidden="true" /> Watch the demo
          </button>
        </motion.div>
      </div>
      <motion.div className="signal-stage glass" {...rise(0.42)}>
        <SignalField
          label="Illustrative voice signal. Move across it to scan the recording."
          onScan={({ seconds, level: value, active }) => {
            if (clock.current) clock.current.textContent = formatClock(seconds)
            if (level.current) level.current.textContent = `${Math.round(value * 100)}%`
            if (mode.current) mode.current.textContent = active ? 'Scanning where you point' : 'Move across the signal to scan it'
          }}
        />
        <div className="signal-top" aria-hidden="true">
          <span ref={mode}>Move across the signal to scan it</span>
          <span>Mono · 16 kHz · whole-file view</span>
        </div>
        <div className="signal-readout" aria-hidden="true">
          <span>Position <b ref={clock}>00:00.00</b></span>
          <span>Signal level <b ref={level}>0%</b></span>
        </div>
        <p className="signal-caption">Illustrative signal. Real scores come from the workspace.</p>
      </motion.div>
    </section>
  )
}

const QUESTIONS = [
  {
    id: 'synthesis',
    title: 'Does it sound synthesized?',
    short: 'Synthetic-speech score',
    body: 'A pinned NII wav2vec model listens to the whole recording once and returns a 0–100 score for synthetic-speech indicators. Six separate signal measurements describe level, clipping, quiet frames and spectral balance, so you can see the audio the score came from.',
    facts: [
      ['What you get', 'An uncalibrated model score with measured observations and limitations'],
      ['What it cannot prove', 'A low score does not show a recording is genuine'],
    ],
    figure: 'synthesis',
  },
  {
    id: 'voice',
    title: 'Does it match a known voice?',
    short: 'Speaker reference',
    body: 'With explicit consent, compare the recording to a trusted sample of the claimed speaker. A local Microsoft WavLM model returns cosine similarity between the two voices. The reference audio is deleted as soon as the comparison finishes.',
    facts: [
      ['What you get', 'An uncalibrated similarity from −1 to 1, stored apart from the synthesis score'],
      ['What it cannot prove', 'Identity: a clone or a replay can also sound similar'],
    ],
    figure: 'voice',
  },
  {
    id: 'words',
    title: 'Are the words true?',
    short: 'Transcript and claims',
    body: 'Transcribe the recording locally, correct what the model misheard, then link a spoken passage to the sources you checked. Corrections create new versions, and reviews of older wording are marked stale.',
    facts: [
      ['What you get', 'A versioned transcript and analyst-written claim reviews with source links'],
      ['What it cannot prove', 'Intent or honesty: this is source review, not lie detection'],
    ],
    figure: 'words',
  },
] as const

function QuestionFigure({ kind }: { kind: (typeof QUESTIONS)[number]['figure'] }) {
  const reduced = useReducedMotion()
  const draw = { initial: { pathLength: reduced ? 1 : 0 }, animate: { pathLength: 1 }, transition: { duration: 1.1, ease: 'easeOut' as const } }
  if (kind === 'synthesis') {
    return (
      <svg className="question-figure" viewBox="0 0 520 140" aria-hidden="true">
        {Array.from({ length: 64 }, (_, i) => {
          const h = 10 + Math.abs(Math.sin(i * 0.5) * Math.sin(i * 0.13)) * 90
          return <motion.rect key={i} x={i * 8 + 4} width="4" rx="2" fill={i > 38 && i < 50 ? '#8fd3e3' : '#ffffff8c'}
            initial={{ height: 4, y: 68 }} animate={{ height: h, y: 70 - h / 2 }}
            transition={{ duration: reduced ? 0 : 0.6, delay: reduced ? 0 : i * 0.008 }} />
        })}
        <motion.rect x="308" y="8" width="96" height="124" rx="10" fill="none" stroke="#ffd9bf" strokeWidth="1.5"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reduced ? 0 : 0.5 }} />
      </svg>
    )
  }
  if (kind === 'voice') {
    return (
      <svg className="question-figure" viewBox="0 0 520 140" aria-hidden="true">
        <motion.path d="M10 70 C 60 20, 110 120, 160 70 S 260 20, 310 70 S 410 120, 510 70" fill="none" stroke="#ffffffb3" strokeWidth="3" {...draw} />
        <motion.path d="M10 76 C 60 30, 110 126, 160 76 S 260 34, 310 78 S 410 110, 510 74" fill="none" stroke="#8fd3e3" strokeWidth="3" strokeDasharray="6 8" {...draw} />
        <text x="12" y="20" fill="#dce1e6" fontSize="13">Recording</text>
        <text x="12" y="132" fill="#8fd3e3" fontSize="13">Trusted reference</text>
      </svg>
    )
  }
  return (
    <svg className="question-figure" viewBox="0 0 520 140" aria-hidden="true">
      {[18, 48, 78, 108].map((y, row) => (
        <g key={y}>
          <rect x="10" y={y} width={row === 1 ? 330 : 420 - row * 40} height="12" rx="6" fill="#ffffff40" />
          {row === 1 && <motion.rect x="120" y={y - 3} width="150" height="18" rx="9" fill="none" stroke="#f1c98c" strokeWidth="2"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reduced ? 0 : 0.3 }} />}
        </g>
      ))}
      <motion.path d="M270 54 C 340 54, 360 30, 430 30" fill="none" stroke="#f1c98c" strokeWidth="2" {...draw} />
      <circle cx="440" cy="30" r="9" fill="#f1c98c" />
      <text x="456" y="35" fill="#dce1e6" fontSize="13">Source</text>
    </svg>
  )
}

export function Questions() {
  const [active, setActive] = useState(0)
  const question = QUESTIONS[active]
  const reduced = useReducedMotion()
  const onKey = tabKeys(QUESTIONS.length, active, setActive, index => `question-tab-${QUESTIONS[index].id}`)

  return (
    <section className="section shell" id="questions" aria-labelledby="questions-title">
      <div className="section-head">
        <h2 id="questions-title">Three questions. Kept apart on purpose.</h2>
        <p>A convincing voice can be synthetic, a genuine voice can be replayed, and a real recording can carry a false claim. ECHOTRACE answers each question with its own evidence and never folds them into one number.</p>
      </div>
      <div className="questions glass">
        <div className="question-list" role="tablist" aria-label="Questions ECHOTRACE helps answer" aria-orientation="vertical" onKeyDown={onKey}>
          {QUESTIONS.map((item, index) => (
            <button key={item.id} id={`question-tab-${item.id}`} role="tab" type="button" className="question-tab"
              aria-selected={index === active} aria-controls="question-panel" tabIndex={index === active ? 0 : -1}
              onClick={() => setActive(index)}>
              {index === active && <motion.span layoutId="question-pill" className="pill" transition={spring} />}
              <span><strong>{item.title}</strong><small>{item.short}</small></span>
            </button>
          ))}
        </div>
        <div className="question-panel" id="question-panel" role="tabpanel" aria-labelledby={`question-tab-${question.id}`}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={question.id} initial={{ opacity: 0, x: reduced ? 0 : 16 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: reduced ? 0 : -10 }} transition={{ duration: 0.22 }}>
              <QuestionFigure kind={question.figure} />
              <h3>{question.title}</h3>
              <p>{question.body}</p>
              <dl className="question-facts">
                {question.facts.map(([term, detail]) => <div key={term}><dt>{term}</dt><dd>{detail}</dd></div>)}
              </dl>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}

const STEPS = ['Review recording', 'Check reliability', 'Case evidence'] as const
const WAVE = Array.from({ length: 56 }, (_, i) => 16 + Math.abs(Math.sin(i * 0.42) * Math.cos(i * 0.11)) * 80)
const CONDITIONS = [
  { id: 'original', label: 'Original', score: 86 },
  { id: 'mp3', label: 'MP3 64 kbps', score: 83 },
  { id: 'noise', label: 'Noise 20 dB', score: 77 },
] as const

function Meter({ value, color }: { value: number; color: string }) {
  return (
    <div className="meter" aria-hidden="true">
      <motion.span style={{ background: color }} initial={{ scaleX: 0 }} animate={{ scaleX: value / 100 }} transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }} />
    </div>
  )
}

function ReviewStep() {
  const [head, setHead] = useState(0.3)
  return (
    <div className="walk-body">
      <div className="walk-card">
        <span className="illustration-note"><Info size={14} aria-hidden="true" /> Illustration with sample values, not a real analysis</span>
        <h3>Synthesis assessment</h3>
        <div className="score-read"><strong>86</strong><span>of 100 · elevated synthetic indicators</span></div>
        <Meter value={86} color="var(--high)" />
        <div className="mini-wave" role="slider" tabIndex={0} aria-label="Sample playhead" aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={Math.round(head * 100)}
          onClick={event => {
            const rect = event.currentTarget.getBoundingClientRect()
            setHead(Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)))
          }}
          onKeyDown={event => {
            if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
              event.preventDefault()
              setHead(value => Math.min(1, Math.max(0, value + (event.key === 'ArrowRight' ? 0.05 : -0.05))))
            }
          }}>
          {WAVE.map((height, index) => <i key={index} style={{ height: `${height}%`, opacity: index / WAVE.length <= head ? 1 : 0.45 }} />)}
          <motion.span className="head" animate={{ left: `${head * 100}%` }} transition={spring} />
        </div>
        <p style={{ marginTop: 12 }}>Click the waveform or use the arrow keys, just as you would to play a passage in the workspace.</p>
      </div>
      <div className="walk-card">
        <h3>Measured observations</h3>
        <p>Signal properties that describe the recording. They do not produce or explain the model score.</p>
        <ul className="checklist">
          {['Average level and peak', 'Near-clipped samples', 'Quiet frames', 'Spectral centroid and high-band energy'].map(item => (
            <li key={item}><AudioLines size={16} aria-hidden="true" />{item}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function ReliabilityStep() {
  const [shown, setShown] = useState<string[]>(['original'])
  const toggle = (id: string) => setShown(current => current.includes(id) ? current.filter(item => item !== id || id === 'original') : [...current, id])
  return (
    <div className="walk-body">
      <div className="walk-card">
        <span className="illustration-note"><Info size={14} aria-hidden="true" /> Illustration with sample values, not a real analysis</span>
        <h3>Stress comparison</h3>
        <p>Make a compressed or noisy copy. The same model scores it separately and the original stays untouched.</p>
        <div className="toggle-row" role="group" aria-label="Transformed copies">
          {CONDITIONS.slice(1).map(condition => (
            <button key={condition.id} type="button" className="chip" aria-pressed={shown.includes(condition.id)} onClick={() => toggle(condition.id)}>
              {shown.includes(condition.id) ? <Check size={16} aria-hidden="true" /> : null}{condition.label}
            </button>
          ))}
        </div>
        <div className="compare">
          <AnimatePresence initial={false}>
            {CONDITIONS.filter(condition => shown.includes(condition.id)).map(condition => (
              <motion.div key={condition.id} className="compare-row" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <span>{condition.label}</span>
                <Meter value={condition.score} color={condition.id === 'original' ? 'var(--high)' : 'var(--mid)'} />
                <output>{condition.score}</output>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
      <div className="walk-card">
        <h3>Read the limits first</h3>
        <ul className="checklist">
          {['Scores are uncalibrated; they are not probabilities.', 'A stable score under compression does not prove authenticity.', 'Measured detector performance sits beside every result.'].map(item => (
            <li key={item}><Info size={16} aria-hidden="true" />{item}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function EvidenceStep() {
  const items = [
    [Check, 'Save your review status and notes, versioned apart from the model result'],
    [Mic, 'Optionally compare a consented trusted voice reference'],
    [ScrollText, 'Transcribe locally, correct the words, link claims to sources'],
    [FileText, 'Export a case report as JSON or a printable page, or an analyst CSV'],
  ] as const
  return (
    <div className="walk-body">
      <div className="walk-card">
        <h3>Hand off a case someone else can check</h3>
        <ul className="checklist">
          {items.map(([Icon, text]) => <li key={text}><Icon size={16} aria-hidden="true" />{text}</li>)}
        </ul>
      </div>
      <div className="walk-card">
        <h3>What travels with the report</h3>
        <p>File hashes, model versions and weights hashes, every transformation, the analyst review and any AI-written brief, each labelled by source. There is no combined authenticity percentage.</p>
      </div>
    </div>
  )
}

export function Walkthrough() {
  const [step, setStep] = useState(0)
  const reduced = useReducedMotion()
  const panels = [<ReviewStep key="review" />, <ReliabilityStep key="reliability" />, <EvidenceStep key="evidence" />]
  return (
    <section className="section shell" id="walkthrough" aria-labelledby="walkthrough-title">
      <div className="section-head">
        <h2 id="walkthrough-title">One recording, three steps.</h2>
        <p>The workspace guides every case the same way, so an analyst can move from a first listen to a report without losing track of what was checked.</p>
      </div>
      <div className="walk glass">
        <div className="walk-steps" role="tablist" aria-label="Investigation steps"
          onKeyDown={tabKeys(STEPS.length, step, setStep, index => `walk-tab-${index}`)}>
          {STEPS.map((label, index) => (
            <button key={label} id={`walk-tab-${index}`} type="button" role="tab" className="walk-step" aria-selected={index === step}
              aria-controls="walk-panel" tabIndex={index === step ? 0 : -1} onClick={() => setStep(index)}>
              {index === step && <motion.span layoutId="walk-pill" className="pill" transition={spring} />}
              <span><b>{String(index + 1).padStart(2, '0')}</b><strong>{label}</strong></span>
            </button>
          ))}
        </div>
        <div id="walk-panel" role="tabpanel" aria-labelledby={`walk-tab-${step}`}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={step} initial={{ opacity: 0, y: reduced ? 0 : 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              {panels[step]}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  )
}
