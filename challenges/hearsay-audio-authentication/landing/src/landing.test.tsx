import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import Assistant from './components/Assistant'
import { Benchmark, Demo } from './sections/Evidence'

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

function stubApi(handlers: Record<string, (init?: RequestInit) => Promise<Response>>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const handler = handlers[String(input)]
    return handler ? handler(init) : json({ user: null })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('assistant', () => {
  it('answers a question, labels its source and jumps to the related section', async () => {
    const fetchMock = stubApi({
      '/api/assistant': () => json({ text: 'On 2,000 public recordings it caught 937 of 1,000 synthetic clips.', source: 'guide', section: 'benchmark' }),
    })
    const target = document.createElement('section')
    target.id = 'benchmark'
    document.body.append(target)
    const user = userEvent.setup()
    render(<Assistant />)

    await user.click(screen.getByRole('button', { name: /ask echotrace/i }))
    const dialog = screen.getByRole('dialog', { name: /echotrace guide/i })
    await user.type(within(dialog).getByLabelText(/your question/i), 'How accurate is it?{Enter}')

    expect(await within(dialog).findByText(/937 of 1,000/)).toBeInTheDocument()
    expect(within(dialog).getByText(/built-in product guide/i)).toBeInTheDocument()
    const [, init] = fetchMock.mock.calls.find(([url]) => url === '/api/assistant')!
    expect(JSON.parse(String(init?.body)).messages.at(-1)).toEqual({ role: 'user', content: 'How accurate is it?' })

    await user.click(within(dialog).getByRole('button', { name: /go to results/i }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(target.scrollIntoView).toHaveBeenCalled())
    target.remove()
  })

  it('offers starter questions and explains a failed request without inventing an answer', async () => {
    stubApi({ '/api/assistant': () => json({ detail: 'Too many attempts. Wait a minute and try again.' }, 429) })
    const user = userEvent.setup()
    render(<Assistant />)
    await user.click(screen.getByRole('button', { name: /ask echotrace/i }))
    await user.click(screen.getByRole('button', { name: /does uploading audio train the model/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/wait a minute/i)
  })

  it('drops a late reply that belongs to a conversation the visitor already cleared', async () => {
    let resolveReply!: (response: Response) => void
    stubApi({ '/api/assistant': () => new Promise<Response>(resolve => { resolveReply = resolve }) })
    const user = userEvent.setup()
    render(<Assistant />)
    await user.click(screen.getByRole('button', { name: /ask echotrace/i }))
    await user.click(screen.getByRole('button', { name: /what does echotrace do/i }))
    await user.click(screen.getByRole('button', { name: /start a new conversation/i }))
    resolveReply(new Response(JSON.stringify({ text: 'Stale answer from the old chat.', source: 'guide', section: null }),
      { headers: { 'Content-Type': 'application/json' } }))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(screen.queryByText('Stale answer from the old chat.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /how accurate is the detector/i })).toBeInTheDocument()
  })

  it('moves between workflow steps with the arrow keys', async () => {
    const user = userEvent.setup()
    const { Walkthrough } = await import('./sections/Story')
    render(<Walkthrough />)
    const first = screen.getByRole('tab', { name: /review recording/i })
    first.focus()
    await user.keyboard('{ArrowRight}')
    const second = screen.getByRole('tab', { name: /check reliability/i })
    expect(second).toHaveFocus()
    expect(second).toHaveAttribute('aria-selected', 'true')
  })

  it('opens as a modal over a blurred backdrop, keeps focus inside, and closes from the backdrop', async () => {
    stubApi({})
    const user = userEvent.setup()
    const { container } = render(<Assistant />)
    await user.click(screen.getByRole('button', { name: /ask echotrace/i }))
    const dialog = screen.getByRole('dialog', { name: /echotrace guide/i })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    const backdrop = container.querySelector('.assistant-backdrop')
    expect(backdrop).toBeInTheDocument()
    for (let i = 0; i < 12; i += 1) {
      await user.tab()
      expect(dialog.contains(document.activeElement)).toBe(true)
    }
    await user.click(backdrop!)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(container.querySelector('.assistant-backdrop')).not.toBeInTheDocument()
  })

  it('closes with Escape and returns focus to the launcher', async () => {
    stubApi({})
    const user = userEvent.setup()
    render(<Assistant />)
    const launcher = screen.getByRole('button', { name: /ask echotrace/i })
    await user.click(launcher)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(launcher).toHaveFocus()
  })
})

const ADA = {
  id: '1', name: 'Ada Analyst', email: 'ada@example.org', avatar_url: null, created_at: '',
  has_password: true, google_linked: false, email_verified: false,
}

function mockAssign() {
  const original = window.location
  const assign = vi.fn()
  const live = Object.fromEntries(['href', 'origin', 'protocol', 'host', 'hostname', 'port', 'pathname', 'search', 'hash']
    .map(key => [key, { get: () => original[key as keyof Location], enumerable: true }]))
  const stand = Object.defineProperties({ assign, replace: vi.fn(), reload: vi.fn() }, live)
  Object.defineProperty(window, 'location', { configurable: true, value: stand })
  onTestFinished(() => { Object.defineProperty(window, 'location', { configurable: true, value: original }) })
  return assign
}

const providers = (google: boolean) => () => json({ password: true, google })

describe('accounts', () => {
  it('validates signup fields next to each input before calling the server', async () => {
    const fetchMock = stubApi({})
    window.history.replaceState(null, '', '/signup')
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /create account/i }))
    expect(screen.getByText(/enter your name/i)).toBeInTheDocument()
    expect(screen.getByText(/valid email/i)).toBeInTheDocument()
    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith('/api/auth/signup', expect.anything())
  })

  it('shows a server conflict and, after signup succeeds, opens the workspace', async () => {
    const assign = mockAssign()
    let attempt = 0
    stubApi({
      '/api/auth/providers': providers(false),
      '/api/auth/signup': () => (attempt++ === 0
        ? json({ detail: 'An account with this email already exists. Log in instead.' }, 409)
        : json({ user: ADA }, 201)),
    })
    window.history.replaceState(null, '', '/signup')
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/^name/i), 'Ada Analyst')
    await user.type(screen.getByLabelText(/^email/i), 'ada@example.org')
    await user.type(screen.getByLabelText(/^password/i), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument()
    expect(assign).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /create account/i }))
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/app/'))
  })

  it('logs in and goes to the requested product page', async () => {
    const assign = mockAssign()
    stubApi({ '/api/auth/providers': providers(false), '/api/auth/login': () => json({ user: ADA }) })
    window.history.replaceState(null, '', '/login?next=%2Fapp%2Fcases')
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText(/^email/i), 'ada@example.org')
    await user.type(screen.getByLabelText(/^password/i), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/app/cases'))
  })

  it('hides Google sign-in when the backend does not offer it', async () => {
    const fetchMock = stubApi({ '/api/auth/providers': providers(false) })
    window.history.replaceState(null, '', '/login')
    render(<App />)
    await screen.findByLabelText(/^email/i)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/auth/providers'))
    expect(screen.queryByRole('link', { name: /continue with google/i })).not.toBeInTheDocument()
  })

  it('offers Google sign-in that carries a safe next path', async () => {
    stubApi({ '/api/auth/providers': providers(true) })
    window.history.replaceState(null, '', '/signup?next=%2Fapp%2Fcases%2F7')
    render(<App />)
    const google = await screen.findByRole('link', { name: /continue with google/i })
    expect(google).toHaveAttribute('href', '/api/auth/google/start?next=%2Fapp%2Fcases%2F7')
    expect(screen.getByRole('separator')).toHaveTextContent('or')
  })

  it.each(['https://evil.example/', '//evil.example/', '/\\evil.example', 'app/'])('replaces unsafe next %s with /app/', async next => {
    stubApi({ '/api/auth/providers': providers(true) })
    window.history.replaceState(null, '', `/login?next=${encodeURIComponent(next)}`)
    render(<App />)
    const google = await screen.findByRole('link', { name: /continue with google/i })
    expect(google).toHaveAttribute('href', '/api/auth/google/start?next=%2Fapp%2F')
  })

  it('shows an error passed back from the Google sign-in redirect', async () => {
    stubApi({ '/api/auth/providers': providers(true) })
    window.history.replaceState(null, '', `/login?error=${encodeURIComponent('Google sign-in was cancelled.')}`)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Google sign-in was cancelled.')
  })

  it('offers the workspace to a visitor who is already signed in', async () => {
    stubApi({ '/api/auth/me': () => json({ user: ADA }), '/api/auth/providers': providers(true) })
    window.history.replaceState(null, '', '/login')
    render(<App />)
    const main = await screen.findByRole('main')
    expect(await within(main).findByRole('link', { name: /open workspace/i })).toHaveAttribute('href', '/app/')
    expect(within(main).queryByLabelText(/^password/i)).not.toBeInTheDocument()
  })

  it('shows signed-in visitors an Open workspace link on the landing page', async () => {
    stubApi({ '/api/auth/me': () => json({ user: ADA }) })
    render(<App />)
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(await within(nav).findByRole('link', { name: /open workspace/i })).toHaveAttribute('href', '/app/')
    expect(within(nav).getByText('Ada Analyst')).toBeInTheDocument()
  })

  it('lets a visitor reveal the password they typed', async () => {
    stubApi({})
    window.history.replaceState(null, '', '/login')
    const user = userEvent.setup()
    render(<App />)
    const password = await screen.findByLabelText(/^password/i)
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: /show password/i }))
    expect(password).toHaveAttribute('type', 'text')
  })
})

describe('evidence sections', () => {
  it('draws the measured benchmark and switches to the failed experiment', async () => {
    const user = userEvent.setup()
    const { container } = render(<Benchmark />)
    expect(screen.getByText('93.7%')).toBeInTheDocument()
    expect(screen.getByText('2.4%')).toBeInTheDocument()
    expect(container.querySelectorAll('.dot')).toHaveLength(2000)
    expect(container.querySelectorAll('.dot.missed')).toHaveLength(63)
    expect(container.querySelectorAll('.dot.flagged')).toHaveLength(24)

    await user.click(screen.getByRole('button', { name: /adapted experiment/i }))
    expect(screen.getByText('87.4%')).toBeInTheDocument()
    expect(screen.getByText('24.4%')).toBeInTheDocument()
    expect(screen.getByText(/not promoted/i)).toBeInTheDocument()
    expect(container.querySelectorAll('.dot.flagged')).toHaveLength(244)
  })

  it('shows a clear placeholder until a demo video is configured', () => {
    const { rerender, container } = render(<Demo videoUrl="" />)
    expect(screen.getByText(/demo video is on its way/i)).toBeInTheDocument()
    rerender(<Demo videoUrl="/demo/echotrace-demo.mp4" />)
    expect(container.querySelector('video')).toHaveAttribute('src', '/demo/echotrace-demo.mp4')
  })
})
