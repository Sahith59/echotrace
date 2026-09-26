import { useEffect, useState } from 'react'
import { accountRequest, loadAccountState, type AccountState, type AccountUser, type Preferences } from './account'

export function useAccountSession(onError: (message: string) => void) {
  const [account, setAccount] = useState<AccountState>({ status: 'checking' })
  const [preferences, setPreferences] = useState<Preferences | null>(null)

  useEffect(() => {
    let live = true
    loadAccountState().then(state => { if (live) setAccount(state) })
    return () => { live = false }
  }, [])

  const signedIn = account.status === 'signed-in'
  useEffect(() => {
    if (!signedIn) return
    let live = true
    accountRequest<{ preferences: Preferences }>('/api/account/preferences')
      .then(response => { if (live) setPreferences(response.preferences) })
      .catch(event => { if (live) onError(`Your saved preferences could not be loaded: ${(event as Error).message}`) })
    return () => { live = false }
  }, [signedIn, onError])

  const motionReduced = preferences?.motion === 'reduce'
  useEffect(() => {
    document.documentElement.classList.toggle('motion-reduced', motionReduced)
    return () => document.documentElement.classList.remove('motion-reduced')
  }, [motionReduced])

  const user = account.status === 'signed-in' ? account.user : null
  const setUser = (next: AccountUser) => setAccount({ status: 'signed-in', user: next })
  return { user, preferences, setPreferences, setUser, motionReduced }
}
