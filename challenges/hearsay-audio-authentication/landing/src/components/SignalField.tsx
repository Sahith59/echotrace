import { useEffect, useRef } from 'react'
import { useReducedMotion } from 'motion/react'

// Illustrative voice-like envelope. It is artwork, never an analysis result.
const SAMPLES = 900
const ENVELOPE = Array.from({ length: SAMPLES }, (_, i) => {
  const syllable = Math.max(0, Math.sin(i * 0.043)) ** 0.55
  const phrase = 0.35 + 0.65 * Math.max(0, Math.sin(i * 0.0105 + 0.6))
  const texture = Math.abs(0.55 * Math.sin(i * 0.31) + 0.3 * Math.sin(i * 0.87 + 1.3) + 0.15 * Math.sin(i * 2.1))
  return 0.06 + 0.94 * syllable * phrase * (0.45 + 0.55 * texture)
})
const CLIP_SECONDS = 8.72
const LENS_RADIUS = 110
const BAR_STEP = 6

type Props = {
  variant?: 'hero' | 'ambient'
  label: string
  onScan?: (reading: { seconds: number; level: number; active: boolean }) => void
}

export default function SignalField({ variant = 'hero', label, onScan }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pointer = useRef<{ x: number; active: boolean }>({ x: 0, active: false })
  const scanRef = useRef(onScan)
  scanRef.current = onScan
  const reduced = useReducedMotion()

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context) return
    let frame = 0
    let width = 0
    let height = 0
    let lensX = -1
    let lastReport = 0
    const started = performance.now()
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(canvas)

    const draw = (now: number) => {
      const elapsed = (now - started) / 1000
      const intro = reduced ? 1 : Math.min(1, elapsed / 1.4)
      const eased = 1 - (1 - intro) ** 3
      const drift = reduced ? 0 : elapsed * (variant === 'hero' ? 9 : 16)
      const autoX = width * (0.5 + 0.38 * Math.sin(elapsed * 0.35))
      const targetX = pointer.current.active ? pointer.current.x : variant === 'hero' ? autoX : -LENS_RADIUS * 2
      lensX = lensX < 0 || reduced ? targetX : lensX + (targetX - lensX) * 0.14
      const mid = height * (variant === 'hero' ? 0.52 : 0.58)
      const span = height * (variant === 'hero' ? 0.36 : 0.4)

      context.clearRect(0, 0, width, height)
      const bars = Math.ceil(width / BAR_STEP)
      for (let b = 0; b < bars; b += 1) {
        const x = b * BAR_STEP + BAR_STEP / 2
        const sample = ENVELOPE[Math.floor(b * 1.6 + drift) % SAMPLES]
        const distance = Math.abs(x - lensX)
        const lens = Math.max(0, 1 - distance / LENS_RADIUS) ** 2
        const reveal = Math.min(1, Math.max(0, eased * 1.6 - (b / bars) * 0.6))
        const amplitude = sample * span * reveal * (1 + 0.5 * lens)
        const alpha = 0.3 + 0.4 * sample + 0.3 * lens
        context.fillStyle = lens > 0.02
          ? `rgba(${Math.round(255 - 112 * lens)}, ${Math.round(255 - 44 * lens)}, ${Math.round(255 - 28 * lens)}, ${alpha})`
          : `rgba(255, 255, 255, ${alpha * 0.8})`
        context.beginPath()
        context.roundRect(x - 1.5, mid - amplitude, 3, amplitude * 2, 1.5)
        context.fill()
      }

      if (variant === 'hero' && intro >= 1) {
        context.strokeStyle = 'rgba(255, 217, 191, 0.9)'
        context.lineWidth = 1.5
        context.beginPath()
        context.moveTo(lensX, height * 0.16)
        context.lineTo(lensX, height * 0.84)
        context.stroke()
        const ring = context.createRadialGradient(lensX, mid, 0, lensX, mid, LENS_RADIUS)
        ring.addColorStop(0, 'rgba(143, 211, 227, 0.16)')
        ring.addColorStop(1, 'rgba(143, 211, 227, 0)')
        context.fillStyle = ring
        context.fillRect(lensX - LENS_RADIUS, 0, LENS_RADIUS * 2, height)
        if (scanRef.current && now - lastReport > 80) {
          lastReport = now
          const position = Math.min(1, Math.max(0, lensX / Math.max(width, 1)))
          const level = ENVELOPE[Math.floor((lensX / BAR_STEP) * 1.6 + drift) % SAMPLES]
          scanRef.current({ seconds: position * CLIP_SECONDS, level, active: pointer.current.active })
        }
      }
      if (!reduced || intro < 1) frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)

    const redrawStatic = () => { if (reduced) frame = requestAnimationFrame(draw) }
    const move = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect()
      pointer.current = { x: event.clientX - rect.left, active: true }
      redrawStatic()
    }
    const leave = () => { pointer.current = { ...pointer.current, active: false }; redrawStatic() }
    canvas.addEventListener('pointermove', move)
    canvas.addEventListener('pointerleave', leave)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      canvas.removeEventListener('pointermove', move)
      canvas.removeEventListener('pointerleave', leave)
    }
  }, [variant, reduced])

  return <canvas ref={canvasRef} role="img" aria-label={label} />
}
