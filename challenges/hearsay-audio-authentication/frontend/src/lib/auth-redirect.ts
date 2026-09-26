const SESSION_PROBE = '/api/auth/me'

type RedirectWindow = Pick<Window, 'fetch' | 'location'>

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

export function needsSignIn(input: RequestInfo | URL, status: number, origin: string): boolean {
  if (status !== 401) return false
  let url: URL
  try { url = new URL(requestUrl(input), origin) }
  catch { return false }
  return url.origin === origin && url.pathname.startsWith('/api/') && url.pathname !== SESSION_PROBE
}

export function loginPath(location: Pick<Location, 'pathname' | 'search' | 'hash'>): string {
  return `/login?next=${encodeURIComponent(`${location.pathname}${location.search}${location.hash}`)}`
}

export function installAuthRedirect(target: RedirectWindow = window): () => void {
  const originalFetch = target.fetch
  const guardedFetch: typeof fetch = async (input, init) => {
    const response = await originalFetch.call(target, input, init)
    if (needsSignIn(input, response.status, target.location.origin)) target.location.assign(loginPath(target.location))
    return response
  }
  target.fetch = guardedFetch
  return () => { target.fetch = originalFetch }
}
