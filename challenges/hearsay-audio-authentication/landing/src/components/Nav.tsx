import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'
import { LogoMark } from './Logo'
import { Link } from '../lib/router'
import { useSession } from '../lib/session'
import { WORKSPACE_URL } from '../config'

const LINKS = [
  ['#questions', 'Questions'],
  ['#walkthrough', 'Workflow'],
  ['#benchmark', 'Results'],
  ['#how-it-works', 'How it works'],
  ['#demo', 'Demo'],
  ['#faq', 'FAQ'],
] as const

export default function Nav() {
  const { user, logout } = useSession()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!error) return
    const timer = window.setTimeout(() => setError(''), 5000)
    return () => window.clearTimeout(timer)
  }, [error])

  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [open])

  return (
    <nav className={`nav glass${open ? ' open' : ''}`} aria-label="Main">
      <Link to="/" className="brand" aria-label="ECHOTRACE home">
        <LogoMark size={36} />ECHOTRACE
      </Link>
      <div className="nav-links" id="nav-links">
        {LINKS.map(([href, label]) => <a key={href} href={href} onClick={() => setOpen(false)}>{label}</a>)}
      </div>
      <div className="nav-actions">
        {user ? <>
          <span className="nav-user">{user.name}</span>
          <button type="button" className="btn btn-quiet" onClick={() => logout().catch(reason => setError((reason as Error).message))}>Log out</button>
          <a className="btn btn-light" href={WORKSPACE_URL}>Open workspace</a>
        </> : <>
          <Link to="/login" className="btn btn-quiet">Log in</Link>
          <Link to="/signup" className="btn btn-light">Sign up</Link>
        </>}
        <button type="button" className="icon-btn btn-glass nav-menu" aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open} aria-controls="nav-links" onClick={() => setOpen(value => !value)}>
          {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
        </button>
      </div>
      {error && <p role="alert" className="sr-only">{error}</p>}
    </nav>
  )
}
