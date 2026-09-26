import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { accountRequest, type AccountSummary, type AccountUser, type Preferences } from '@/lib/account'
import AccountProfile from './AccountProfile'
import AccountSettings from './AccountSettings'
import './AccountCenter.css'

export type AccountTab = 'profile' | 'settings'

type Props = {
  user: AccountUser
  tab: AccountTab
  preferences: Preferences | null
  onTabChange: (tab: AccountTab) => void
  onBack: () => void
  onUserChange: (user: AccountUser) => void
  onPreferencesChange: (preferences: Preferences) => void
  onRecordingsDeleted: () => void
}

const TABS: { id: AccountTab; label: string }[] = [{ id: 'profile', label: 'Profile' }, { id: 'settings', label: 'Settings' }]

export default function AccountCenter({ user, tab, preferences, onTabChange, onBack, onUserChange, onPreferencesChange, onRecordingsDeleted }: Props) {
  const [summary, setSummary] = useState<AccountSummary | null>(null)
  const [summaryError, setSummaryError] = useState('')
  const tabRefs = useRef<Record<AccountTab, HTMLButtonElement | null>>({ profile: null, settings: null })

  const loadSummary = useCallback(() => {
    setSummaryError('')
    return accountRequest<AccountSummary>('/api/account')
      .then(setSummary)
      .catch(event => setSummaryError((event as Error).message))
  }, [])
  useEffect(() => { loadSummary() }, [loadSummary])

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    event.preventDefault()
    const next: AccountTab = tab === 'profile' ? 'settings' : 'profile'
    onTabChange(next)
    tabRefs.current[next]?.focus()
  }

  return <div className="account-center">
    <div className="breadcrumb"><button type="button" onClick={onBack}>Workspace</button><span>/</span><span>Account</span></div>
    <div className="page-intro"><div><span className="eyebrow">ACCOUNT</span><h1>{tab === 'profile' ? 'Your profile' : 'Settings'}</h1><p>{tab === 'profile' ? 'Your identity, sign-in methods and security.' : 'How ECHOTRACE behaves for you, and control over your data.'}</p></div></div>
    <div className="case-tabs account-tabs" role="tablist" aria-label="Account sections">
      {TABS.map(item => <button key={item.id} ref={node => { tabRefs.current[item.id] = node }} type="button" role="tab" id={`account-tab-${item.id}`}
        aria-selected={tab === item.id} aria-controls={`account-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1}
        onClick={() => onTabChange(item.id)} onKeyDown={handleTabKey}>{item.label}</button>)}
    </div>
    <div role="tabpanel" id={`account-panel-${tab}`} aria-labelledby={`account-tab-${tab}`}>
      {tab === 'profile'
        ? <AccountProfile user={user} summary={summary} summaryError={summaryError} onRetrySummary={loadSummary} onUserChange={onUserChange} />
        : <AccountSettings preferences={preferences} onPreferencesChange={onPreferencesChange} onRecordingsDeleted={() => { onRecordingsDeleted(); loadSummary() }} />}
    </div>
  </div>
}
