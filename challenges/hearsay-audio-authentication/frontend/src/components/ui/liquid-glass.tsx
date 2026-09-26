import type { ComponentPropsWithoutRef, CSSProperties, ReactNode } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { cn } from '@/lib/utils'

type GlassProps = ComponentPropsWithoutRef<'div'> & {
  as?: 'div' | 'section'
  children: ReactNode
  style?: CSSProperties
}

/** Adapted from the supplied layered-glass component. Only the decorative
 * layer is distorted: data, controls, and text retain their sharpness. */
export function GlassEffect({ as: Tag = 'div', className, children, ...props }: GlassProps) {
  return <Tag className={cn('liquid-glass', className)} {...props}>
    <span className="glass-refraction" aria-hidden="true" />
    <span className="glass-specular" aria-hidden="true" />
    {children}
  </Tag>
}

export function GlassFilter() {
  return <svg className="glass-filter-defs" aria-hidden="true" focusable="false">
    <defs>
      <filter id="glass-distortion" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.008 0.018" numOctaves="1" seed="17" result="texture" />
        <feGaussianBlur in="texture" stdDeviation="3" result="softMap" />
        <feDisplacementMap in="SourceGraphic" in2="softMap" scale="16" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </defs>
  </svg>
}

type GlassButtonProps = ComponentPropsWithoutRef<typeof motion.button>
export function GlassButton({ className, children, ...props }: GlassButtonProps) {
  const reduced = useReducedMotion()
  return <motion.button className={cn('glass-button', className)}
    whileTap={reduced ? undefined : { scale: 0.975 }}
    whileHover={reduced ? undefined : { y: -1 }}
    transition={{ type: 'spring', stiffness: 420, damping: 30 }} {...props}>
    {children}
  </motion.button>
}
