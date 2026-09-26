import { useId } from 'react'

/**
 * ECHOTRACE monogram: an E and a T share one top bar, and two fading bars
 * after the T's stem trace the echo of a voice.
 */
export function LogoMark({ size = 32, title }: { size?: number; title?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role={title ? 'img' : undefined} aria-hidden={title ? undefined : true}
      aria-label={title} className="logo-mark" focusable="false">
      <defs>
        <linearGradient id={`${id}-tile`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5b626d" />
          <stop offset="1" stopColor="#262b32" />
        </linearGradient>
        <linearGradient id={`${id}-sheen`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity=".38" />
          <stop offset=".5" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`${id}-ink`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#dfe6ec" />
        </linearGradient>
        <linearGradient id={`${id}-echo`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#9fe0ee" />
          <stop offset="1" stopColor="#9fe0ee" stopOpacity=".35" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="46" height="46" rx="13" fill={`url(#${id}-tile)`} />
      <rect x="1" y="1" width="46" height="46" rx="13" fill={`url(#${id}-sheen)`} />
      <rect x="1.5" y="1.5" width="45" height="45" rx="12.5" fill="none" stroke="#ffffff" strokeOpacity=".32" />
      <g fill={`url(#${id}-ink)`}>
        {/* Shared top bar: the E's top arm and the T's crossbar. */}
        <rect x="9" y="10.5" width="25" height="5" rx="2.5" />
        {/* E stem, middle and bottom arms. */}
        <rect x="9" y="10.5" width="5" height="27" rx="2.5" />
        <rect x="9" y="21.5" width="12" height="5" rx="2.5" />
        <rect x="9" y="32.5" width="14" height="5" rx="2.5" />
        {/* T stem. */}
        <rect x="26.5" y="10.5" width="5" height="27" rx="2.5" />
      </g>
      {/* The echo: a decaying trace of the voice. */}
      <g fill={`url(#${id}-echo)`}>
        <rect x="34.5" y="18.5" width="3" height="15" rx="1.5" />
        <rect x="39.5" y="22" width="3" height="8" rx="1.5" opacity=".7" />
      </g>
    </svg>
  )
}
