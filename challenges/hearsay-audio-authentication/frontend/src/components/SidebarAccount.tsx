import { useState } from 'react'
import { LoaderCircle, LogOut, Settings, UserRound } from 'lucide-react'
import { logOut, type AccountUser } from '@/lib/account'
import { AccountAvatar } from './AccountAvatar'
import type { AccountTab } from './AccountCenter'

export default function SidebarAccount({ user, activeTab, onOpen }: { user: AccountUser; activeTab: AccountTab | null; onOpen: (tab: AccountTab) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleLogOut() {
    setBusy(true); setError('')
    try { await logOut() }
    catch (event) { setError(`Could not log out: ${(event as Error).message}`); setBusy(false) }
  }

  return <section className="sidebar-account" aria-label="Your account">
    <div className="sidebar-account-identity">
      <AccountAvatar user={user} />
      <div><strong title={user.name}>{user.name || 'Unnamed account'}</strong><small title={user.email}>{user.email}</small></div>
    </div>
    <div className="sidebar-account-actions">
      <button type="button" className={`sidebar-account-button ${activeTab === 'profile' ? 'active' : ''}`} aria-current={activeTab === 'profile' ? 'page' : undefined} onClick={() => onOpen('profile')}><UserRound size={15} /> Profile</button>
      <button type="button" className={`sidebar-account-button ${activeTab === 'settings' ? 'active' : ''}`} aria-current={activeTab === 'settings' ? 'page' : undefined} onClick={() => onOpen('settings')}><Settings size={15} /> Settings</button>
      <button type="button" className="sidebar-account-button" onClick={handleLogOut} disabled={busy}>{busy ? <LoaderCircle size={15} className="spin" /> : <LogOut size={15} />} {busy ? 'Logging out…' : 'Log out'}</button>
    </div>
    {error && <p className="sidebar-account-error" role="alert">{error}</p>}
  </section>
}
