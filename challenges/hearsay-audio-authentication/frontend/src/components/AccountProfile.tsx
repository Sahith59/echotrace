import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, KeyRound, LoaderCircle, LogOut, MonitorSmartphone, RefreshCw, Save } from 'lucide-react'
import { GlassEffect } from '@/components/ui/liquid-glass'
import { accountRequest, countOf, logOut, sendJson, type AccountSummary, type AccountUser } from '@/lib/account'
import { AccountAvatar } from './AccountAvatar'

export const MIN_PASSWORD_LENGTH = 10

type Props = {
  user: AccountUser
  summary: AccountSummary | null
  summaryError: string
  onRetrySummary: () => void
  onUserChange: (user: AccountUser) => void
}

function memberSince(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}

function NameForm({ user, onUserChange }: Pick<Props, 'user' | 'onUserChange'>) {
  const [name, setName] = useState(user.name)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  async function save(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) { setError('Enter a name to display.'); setSaved(false); return }
    setBusy(true); setError(''); setSaved(false)
    try {
      const response = await sendJson<{ user: AccountUser }>('/api/account/profile', 'PATCH', { name: trimmed })
      onUserChange(response.user); setName(response.user.name); setSaved(true)
    } catch (caught) { setError((caught as Error).message) }
    finally { setBusy(false) }
  }

  return <form className="account-form" onSubmit={save} noValidate>
    <label className="case-field">Display name
      <input value={name} maxLength={120} autoComplete="name" disabled={busy} aria-invalid={!!error} aria-describedby="account-name-status"
        onChange={event => { setName(event.target.value); setSaved(false) }} />
    </label>
    <div className="account-form-footer">
      <p id="account-name-status" className={error ? 'account-error' : 'account-status'} role={error ? 'alert' : 'status'}>{error || (saved ? 'Name saved.' : '')}</p>
      <button type="submit" className="outline-button" disabled={busy || name.trim() === user.name}>{busy ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />}{busy ? 'Saving…' : 'Save name'}</button>
    </div>
  </form>
}

function PasswordForm({ user, onUserChange }: Pick<Props, 'user' | 'onUserChange'>) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const settingFirst = !user.has_password

  async function submit(event: FormEvent) {
    event.preventDefault()
    setDone('')
    if (!settingFirst && !current) { setError('Enter your current password.'); return }
    if (next.length < MIN_PASSWORD_LENGTH) { setError(`Use at least ${MIN_PASSWORD_LENGTH} characters for the new password.`); return }
    setBusy(true); setError('')
    try {
      await sendJson('/api/account/password', 'POST', settingFirst ? { new: next } : { current, new: next })
      setCurrent(''); setNext('')
      setDone(settingFirst ? 'Password set. You can now sign in with your email and password.' : 'Password changed.')
      if (settingFirst) onUserChange({ ...user, has_password: true })
    } catch (caught) { setError((caught as Error).message) }
    finally { setBusy(false) }
  }

  const inputType = visible ? 'text' : 'password'
  return <form className="account-form" onSubmit={submit} noValidate aria-labelledby="account-password-heading">
    <h3 id="account-password-heading">{settingFirst ? 'Set a password' : 'Change password'}</h3>
    <p className="case-help">{settingFirst ? 'You sign in with Google. Add a password to also sign in with your email address.' : 'Enter your current password, then choose a new one.'} Minimum {MIN_PASSWORD_LENGTH} characters.</p>
    {!settingFirst && <label className="case-field">Current password
      <input type={inputType} value={current} autoComplete="current-password" disabled={busy} onChange={event => setCurrent(event.target.value)} />
    </label>}
    <label className="case-field">New password
      <input type={inputType} value={next} minLength={MIN_PASSWORD_LENGTH} autoComplete="new-password" disabled={busy} aria-describedby="account-password-status" onChange={event => setNext(event.target.value)} />
    </label>
    <div className="account-form-footer">
      <button type="button" className="text-button" aria-pressed={visible} onClick={() => setVisible(value => !value)}>{visible ? <EyeOff size={15} /> : <Eye size={15} />}{visible ? 'Hide passwords' : 'Show passwords'}</button>
      <button type="submit" className="outline-button" disabled={busy}>{busy ? <LoaderCircle size={15} className="spin" /> : <KeyRound size={15} />}{busy ? 'Saving…' : settingFirst ? 'Set password' : 'Change password'}</button>
    </div>
    <p id="account-password-status" className={error ? 'account-error' : 'account-status'} role={error ? 'alert' : 'status'}>{error || done}</p>
  </form>
}

function SessionControls() {
  const [busy, setBusy] = useState<'revoke' | 'logout' | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function revokeOthers() {
    setBusy('revoke'); setError(''); setMessage('')
    try {
      const { revoked } = await accountRequest<{ revoked: number }>('/api/account/sessions/revoke-others', { method: 'POST' })
      setMessage(revoked ? `Signed out of ${revoked} other ${revoked === 1 ? 'session' : 'sessions'}.` : 'No other devices were signed in.')
    } catch (caught) { setError((caught as Error).message) }
    finally { setBusy(null) }
  }
  async function handleLogOut() {
    setBusy('logout'); setError(''); setMessage('')
    try { await logOut() }
    catch (caught) { setError(`Could not log out: ${(caught as Error).message}`); setBusy(null) }
  }

  return <div className="account-session-actions">
    <div className="account-button-row">
      <button type="button" className="outline-button" onClick={revokeOthers} disabled={!!busy}>{busy === 'revoke' ? <LoaderCircle size={15} className="spin" /> : <MonitorSmartphone size={15} />}{busy === 'revoke' ? 'Signing out…' : 'Sign out of other devices'}</button>
      <button type="button" className="outline-button" onClick={handleLogOut} disabled={!!busy}>{busy === 'logout' ? <LoaderCircle size={15} className="spin" /> : <LogOut size={15} />}{busy === 'logout' ? 'Logging out…' : 'Log out'}</button>
    </div>
    <p className={error ? 'account-error' : 'account-status'} role={error ? 'alert' : 'status'}>{error || message}</p>
  </div>
}

export default function AccountProfile({ user, summary, summaryError, onRetrySummary, onUserChange }: Props) {
  const facts: [string, string][] = [
    ['Email', `${user.email}${user.email_verified ? '' : ' (not verified)'}`],
    ['Google sign-in', user.google_linked ? 'Linked' : 'Not linked'],
    ['Password', user.has_password ? 'Set' : 'Not set'],
    ['Member since', memberSince(user.created_at)],
    ['Recordings', summary ? String(countOf(summary.recordings)) : '…'],
    ['Active sessions', summary ? String(countOf(summary.active_sessions)) : '…'],
  ]
  return <div className="account-grid">
    <GlassEffect as="section" className="detail-section account-card" aria-labelledby="account-identity-heading">
      <div className="section-heading"><div><span className="eyebrow">IDENTITY</span><h2 id="account-identity-heading">Profile</h2></div></div>
      <div className="account-identity"><AccountAvatar user={user} size="large" /><div><strong>{user.name || 'Unnamed account'}</strong><small>{user.email}</small></div></div>
      <NameForm user={user} onUserChange={onUserChange} />
      <dl className="account-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {summaryError && <p className="account-error" role="alert">Recording and session counts are unavailable: {summaryError} <button type="button" className="text-button" onClick={onRetrySummary}><RefreshCw size={14} /> Try again</button></p>}
    </GlassEffect>
    <GlassEffect as="section" className="detail-section account-card" aria-labelledby="account-security-heading">
      <div className="section-heading"><div><span className="eyebrow">SECURITY</span><h2 id="account-security-heading">Sign-in and sessions</h2></div></div>
      <PasswordForm user={user} onUserChange={onUserChange} />
      <div className="account-divider" />
      <h3>Devices</h3>
      <p className="case-help">Signing out other devices ends every session except this one.</p>
      <SessionControls />
    </GlassEffect>
  </div>
}
