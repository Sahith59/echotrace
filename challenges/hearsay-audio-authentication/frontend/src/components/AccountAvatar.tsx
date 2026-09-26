import { useState } from 'react'
import { initials, type AccountUser } from '@/lib/account'

export function AccountAvatar({ user, size = 'small' }: { user: Pick<AccountUser, 'name' | 'email' | 'avatar_url'>; size?: 'small' | 'large' }) {
  const [imageFailed, setImageFailed] = useState(false)
  const className = `account-avatar account-avatar-${size}`
  if (user.avatar_url && !imageFailed) {
    return <img className={className} src={user.avatar_url} alt="" referrerPolicy="no-referrer" onError={() => setImageFailed(true)} />
  }
  return <span className={className} aria-hidden="true">{initials(user)}</span>
}
