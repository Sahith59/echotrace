import { useEffect, useRef, useState, type FormEvent } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowLeft, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import SignalField from '../components/SignalField'
import { LogoMark } from '../components/Logo'
import { Link, safeNext } from '../lib/router'
import { useSession } from '../lib/session'

type Mode = 'login' | 'signup'
type Errors = Partial<Record<'name' | 'email' | 'password', string>>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const COPY = {
  signup: {
    art: 'Every recording deserves a closer listen.',
    artBody: 'Create an account with Google or email to open the ECHOTRACE workspace and start your first review.',
    title: 'Create your account',
    lede: 'It takes about a minute. You will go straight to the workspace, signed in.',
    googleLede: 'Use your Google account or sign up with email. You will go straight to the workspace.',
    submit: 'Create account',
    busy: 'Creating account…',
  },
  login: {
    art: 'Welcome back to the workspace.',
    artBody: 'Log in to continue reviewing recordings and pick up your saved cases.',
    title: 'Log in',
    lede: 'Use the email and password you signed up with.',
    googleLede: 'Continue with Google, or use the email and password you signed up with.',
    submit: 'Log in',
    busy: 'Logging in…',
  },
} as const

function validate(mode: Mode, values: { name: string; email: string; password: string }): Errors {
  const errors: Errors = {}
  if (mode === 'signup' && !values.name.trim()) errors.name = 'Enter your name.'
  if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = 'Enter a valid email address, like name@example.org.'
  if (mode === 'signup' && values.password.length < 10) errors.password = 'Use at least 10 characters.'
  if (mode === 'login' && !values.password) errors.password = 'Enter your password.'
  return errors
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

function useGoogleAvailable() {
  const [available, setAvailable] = useState(false)
  useEffect(() => {
    let live = true
    fetch('/api/auth/providers')
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (live) setAvailable(data?.google === true) })
      .catch(() => { if (live) setAvailable(false) })
    return () => { live = false }
  }, [])
  return available
}

export default function AuthPage({ mode }: { mode: Mode }) {
  const { user, signup, login, logout } = useSession()
  const [params] = useState(() => new URLSearchParams(window.location.search))
  const next = safeNext(params.get('next'))
  const carry = params.get('next') ? `?next=${encodeURIComponent(next)}` : ''
  const google = useGoogleAvailable()
  const copy = COPY[mode]
  const reduced = useReducedMotion()
  const [values, setValues] = useState({ name: '', email: '', password: '' })
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState(() => params.get('error') ?? '')
  const [busy, setBusy] = useState(false)
  const [reveal, setReveal] = useState(false)
  const refs = { name: useRef<HTMLInputElement>(null), email: useRef<HTMLInputElement>(null), password: useRef<HTMLInputElement>(null) }

  const update = (field: keyof typeof values) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setValues(current => ({ ...current, [field]: event.target.value }))
    if (errors[field]) setErrors(current => ({ ...current, [field]: undefined }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setFormError('')
    const found = validate(mode, values)
    setErrors(found)
    const first = (['name', 'email', 'password'] as const).find(field => found[field])
    if (first) { refs[first].current?.focus(); return }
    setBusy(true)
    try {
      if (mode === 'signup') await signup({ name: values.name.trim(), email: values.email.trim(), password: values.password })
      else await login({ email: values.email.trim(), password: values.password })
      window.location.assign(next)
    } catch (error) {
      setFormError((error as Error).message)
      setBusy(false)
    }
  }

  const field = (name: 'name' | 'email' | 'password', label: string, input: JSX.Element, hint?: string) => (
    <div className="field">
      <label htmlFor={`auth-${name}`}>{label}</label>
      {input}
      {errors[name]
        ? <span className="field-error" id={`auth-${name}-error`}>{errors[name]}</span>
        : hint && <span className="field-hint" id={`auth-${name}-hint`}>{hint}</span>}
    </div>
  )
  const described = (name: 'name' | 'email' | 'password') => errors[name] ? `auth-${name}-error` : name === 'password' && mode === 'signup' ? 'auth-password-hint' : undefined

  return (
    <main className="auth" id="main">
      <motion.aside className="auth-art glass" initial={{ opacity: 0, x: reduced ? 0 : -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
        <Link to="/" className="auth-back"><ArrowLeft size={16} aria-hidden="true" /> Back to ECHOTRACE</Link>
        <span className="auth-logo"><LogoMark size={52} title="ECHOTRACE" /></span>
        <h1>{copy.art}</h1>
        <p>{copy.artBody}</p>
        <SignalField variant="ambient" label="Illustrative moving voice signal" />
      </motion.aside>
      <div className="auth-panel">
        {user && !busy ? (
          <div className="auth-form">
            <h2>You are signed in</h2>
            <p>Signed in as {user.name} ({user.email}).</p>
            <a className="btn btn-primary" href={next}>Open workspace</a>
            <p className="auth-switch">
              Not you? <button type="button" className="link-button" onClick={() => logout().catch(reason => setFormError((reason as Error).message))}>Log out</button>
            </p>
            {formError && <p className="form-error" role="alert">{formError}</p>}
          </div>
        ) : (
        <form className="auth-form" onSubmit={submit} noValidate>
          <h2>{copy.title}</h2>
          <p>{google ? copy.googleLede : copy.lede}</p>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          {google && <>
            <a className="btn btn-google" href={`/api/auth/google/start?next=${encodeURIComponent(next)}`}>
              <GoogleMark />Continue with Google
            </a>
            <div className="auth-divider" role="separator"><span>or</span></div>
          </>}
          {mode === 'signup' && field('name', 'Name',
            <input ref={refs.name} id="auth-name" name="name" autoComplete="name" value={values.name} onChange={update('name')}
              maxLength={80} aria-invalid={!!errors.name} aria-describedby={described('name')} />)}
          {field('email', 'Email',
            <input ref={refs.email} id="auth-email" name="email" type="email" inputMode="email" autoComplete="email" value={values.email}
              onChange={update('email')} maxLength={254} aria-invalid={!!errors.email} aria-describedby={described('email')} />)}
          {field('password', 'Password',
            <div className="field-input">
              <input ref={refs.password} id="auth-password" name="password" className="has-reveal" type={reveal ? 'text' : 'password'}
                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} value={values.password} onChange={update('password')}
                maxLength={200} aria-invalid={!!errors.password} aria-describedby={described('password')} />
              <button type="button" className="reveal" aria-label={reveal ? 'Hide password' : 'Show password'} aria-pressed={reveal}
                onClick={() => setReveal(value => !value)}>
                {reveal ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              </button>
            </div>,
            mode === 'signup' ? 'At least 10 characters. A short phrase works well.' : undefined)}
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy && <LoaderCircle size={18} className="spin" aria-hidden="true" />}{busy ? copy.busy : copy.submit}
          </button>
          <p className="auth-switch">
            {mode === 'signup'
              ? <>Already have an account? <Link to={`/login${carry}`}>Log in</Link></>
              : <>New to ECHOTRACE? <Link to={`/signup${carry}`}>Create an account</Link></>}
          </p>
        </form>
        )}
      </div>
    </main>
  )
}
