import { useEffect, useState, type AnchorHTMLAttributes, type MouseEvent } from 'react'

const CHANGE = 'echotrace:navigate'

export function navigate(to: string) {
  const url = new URL(to, window.location.origin)
  window.history.pushState(null, '', url.pathname + url.search + url.hash)
  window.dispatchEvent(new Event(CHANGE))
  if (url.hash) {
    requestAnimationFrame(() => document.getElementById(url.hash.slice(1))?.scrollIntoView({ block: 'start' }))
  } else {
    window.scrollTo({ top: 0 })
  }
}

export function usePath() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const update = () => setPath(window.location.pathname)
    window.addEventListener('popstate', update)
    window.addEventListener(CHANGE, update)
    return () => {
      window.removeEventListener('popstate', update)
      window.removeEventListener(CHANGE, update)
    }
  }, [])
  return path
}

export const DEFAULT_NEXT = '/app/'

export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return DEFAULT_NEXT
  return value
}

export function scrollToSection(id: string) {
  const target = document.getElementById(id)
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  else navigate(`/#${id}`)
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }

export function Link({ to, onClick, ...props }: LinkProps) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
    event.preventDefault()
    navigate(to)
  }
  return <a href={to} onClick={handle} {...props} />
}
