import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUpRight, AudioLines } from 'lucide-react'
import { motion, useMotionValueEvent, useReducedMotion, useScroll } from 'motion/react'
import './scroll-morph-hero.css'

type Formation = 'scatter' | 'align' | 'circle'

type SignalMorphHeroProps = {
  onAnalyze?: () => void
}

const specimenCount = 9
const specimens = Array.from({ length: specimenCount }, (_, index) => ({
  id: `0${index + 1}`,
  bars: Array.from({ length: 13 }, (_, bar) => {
    const wave = Math.abs(Math.sin((bar + 1) * (index + 2) * 0.58))
    const envelope = 0.45 + 0.55 * Math.sin((bar / 12) * Math.PI)
    return 5 + Math.round(wave * envelope * 22)
  }),
}))

const positions = [
  [-0.34, -0.28, -18], [-0.21, 0.24, 12], [-0.09, -0.35, 8],
  [0.09, 0.29, -12], [0.31, -0.21, 16], [0.36, 0.23, -7],
  [-0.37, 0.17, 9], [0.20, -0.36, -13], [0.02, -0.06, 7],
] as const

function Specimen({ bars, id }: { bars: number[]; id: string }) {
  return (
    <div className="smh-specimen-inner" aria-hidden="true">
      <div className="smh-specimen-top"><span>ET / {id}</span><span className="smh-specimen-dot" /></div>
      <svg viewBox="0 0 48 32" preserveAspectRatio="none" className="smh-specimen-wave">
        <line x1="0" y1="16" x2="48" y2="16" stroke="currentColor" strokeOpacity=".24" strokeWidth=".6" />
        {bars.map((height, index) => (
          <line key={index} x1={3 + index * 3.5} x2={3 + index * 3.5} y1={16 - height / 2} y2={16 + height / 2} stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" />
        ))}
      </svg>
      <div className="smh-specimen-bottom"><span>VOICE</span><span>{String(143 + Number(id) * 19).padStart(3, '0')}</span></div>
    </div>
  )
}

export default function SignalMorphHero({ onAnalyze }: SignalMorphHeroProps) {
  const panelRef = useRef<HTMLElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 540, height: 245 })
  const [formation, setFormation] = useState<Formation>('circle')
  const [manual, setManual] = useState(false)
  const reducedMotion = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: panelRef, offset: ['start end', 'end start'] })

  useMotionValueEvent(scrollYProgress, 'change', value => {
    if (manual || reducedMotion) return
    // The page's own scroll drives the study; the panel never captures wheel or touch input.
    setFormation(value < 0.31 ? 'scatter' : value < 0.64 ? 'align' : 'circle')
  })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      setSize({ width, height })
    })
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  const targets = useMemo(() => specimens.map((_, index) => {
    const compact = Math.min(1, size.width / 460)
    if (formation === 'align') {
      const stride = Math.min(57, (size.width - 44) / (specimenCount - 1))
      return { x: (index - 4) * stride, y: index % 2 === 0 ? -4 : 4, rotate: 0, scale: compact }
    }
    if (formation === 'scatter') {
      const [x, y, rotate] = positions[index]
      return { x: x * size.width, y: y * size.height, rotate, scale: compact * 0.93 }
    }
    const angle = (-90 + index * 40) * Math.PI / 180
    return {
      x: Math.cos(angle) * Math.min(size.width * 0.32, 178),
      y: Math.sin(angle) * Math.min(size.height * 0.34, 94),
      rotate: index % 2 === 0 ? -7 : 7,
      scale: compact,
    }
  }), [formation, size])

  const choose = (next: Formation) => {
    setManual(true)
    setFormation(next)
  }

  return (
    <section className="smh" ref={panelRef} aria-label="Illustrative voice signal study">
      <div className="smh-grid" aria-hidden="true" />
      <div className="smh-halo" aria-hidden="true" />
      <div className="smh-header">
        <div className="smh-kicker"><AudioLines size={14} strokeWidth={1.8} /><span>ECHOTRACE <span className="smh-slash">/</span> SIGNAL STUDY</span></div>
        <span className="smh-index">PLATE 01 — 09</span>
      </div>

      <div className="smh-canvas" ref={canvasRef}>
        <div className="smh-orbit smh-orbit-one" aria-hidden="true" />
        <div className="smh-orbit smh-orbit-two" aria-hidden="true" />
        <div className="smh-center-copy">
          <span className="smh-overline">EXAMINE THE UNHEARD</span>
          <h2>Every voice<br /><em>leaves a trace.</em></h2>
          <p>Uncover the patterns within a recording.</p>
        </div>
        <div className="smh-specimens" aria-hidden="true">
          {specimens.map((specimen, index) => (
            <motion.div
              key={specimen.id}
              className={`smh-specimen smh-specimen-${index + 1}`}
              animate={targets[index]}
              initial={false}
              transition={reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 165, damping: 24, mass: 0.85 }}
            >
              <Specimen {...specimen} />
            </motion.div>
          ))}
        </div>
      </div>

      <div className="smh-footer">
        <div className="smh-footer-left">
          <span className="smh-caption">ILLUSTRATIVE SIGNAL STUDY</span>
          <div className="smh-controls" role="group" aria-label="Signal arrangement">
            {(['circle', 'align', 'scatter'] as const).map(item => (
              <button key={item} type="button" className={formation === item ? 'smh-active' : ''} aria-pressed={formation === item} onClick={() => choose(item)}>{item}</button>
            ))}
          </div>
        </div>
        {onAnalyze && <button className="smh-analyze" type="button" onClick={onAnalyze}>Analyze audio <ArrowUpRight size={14} /></button>}
      </div>
    </section>
  )
}
