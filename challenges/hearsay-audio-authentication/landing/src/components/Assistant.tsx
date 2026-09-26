import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { AlertCircle, ArrowRight, ArrowUp, BookOpen, RotateCcw, Sparkles, X } from 'lucide-react'
import { postJson } from '../lib/session'
import { scrollToSection } from '../lib/router'
import { LogoMark } from './Logo'

type Message = { role: 'user' | 'assistant'; content: string; source?: 'groq' | 'guide'; section?: string | null; error?: boolean }

const STORAGE_KEY = 'echotrace-assistant'
const HISTORY_LIMIT = 12
const MAX_QUESTION = 1200
const STARTERS = [
  'What does ECHOTRACE do?',
  'How accurate is the detector?',
  'Does uploading audio train the model?',
  'Is my audio kept private?',
  'How do I get started?',
]
const SECTION_NAMES: Record<string, string> = {
  top: 'Overview', questions: 'Three questions', walkthrough: 'Workflow', benchmark: 'Results',
  'how-it-works': 'How it works', demo: 'Demo', limits: 'Limits', faq: 'FAQ', signup: 'Get started',
}
const FOCUSABLE = 'button:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex="-1"])'

function loadHistory(): Message[] {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(saved) ? saved.filter(item => typeof item?.content === 'string').slice(-40) : []
  } catch {
    return []
  }
}

function SourceTag({ source }: { source: 'groq' | 'guide' }) {
  return source === 'groq'
    ? <span className="source-tag"><Sparkles size={13} aria-hidden="true" />Groq, grounded in product facts</span>
    : <span className="source-tag"><BookOpen size={13} aria-hidden="true" />Built-in product guide</span>
}

function BotRow({ children, alert }: { children: React.ReactNode; alert?: boolean }) {
  return (
    <div className="bot-row">
      <span className="bot-avatar"><LogoMark size={28} /></span>
      <div className={`msg msg-bot${alert ? ' msg-error' : ''}`} role={alert ? 'alert' : undefined}>{children}</div>
    </div>
  )
}

export default function Assistant() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>(loadHistory)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const launcher = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const log = useRef<HTMLDivElement>(null)
  const wasOpen = useRef(false)
  const generation = useRef(0)
  const reduced = useReducedMotion()

  useEffect(() => {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-40))) } catch { /* storage unavailable; chat still works */ }
    log.current?.scrollTo?.({ top: log.current.scrollHeight, behavior: reduced ? 'auto' : 'smooth' })
  }, [messages, busy, reduced])

  useEffect(() => {
    if (open) {
      input.current?.focus()
      const previous = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      wasOpen.current = true
      return () => { document.body.style.overflow = previous }
    }
    if (wasOpen.current) launcher.current?.focus()
    wasOpen.current = false
  }, [open])

  useEffect(() => {
    const textarea = input.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`
  }, [draft, open])

  async function ask(question: string) {
    const text = question.trim().slice(0, MAX_QUESTION)
    if (!text || busy) return
    const conversation = [...messages.filter(item => !item.error), { role: 'user' as const, content: text }]
    setMessages(current => [...current.filter(item => !item.error), { role: 'user', content: text }])
    setDraft('')
    setBusy(true)
    const request = ++generation.current
    try {
      const reply = await postJson<{ text: string; source: 'groq' | 'guide'; section: string | null }>('/api/assistant', {
        messages: conversation.slice(-HISTORY_LIMIT).map(({ role, content }) => ({ role, content })),
      })
      if (request !== generation.current) return
      setMessages(current => [...current, { role: 'assistant', content: reply.text, source: reply.source, section: reply.section }])
    } catch (error) {
      if (request !== generation.current) return
      setMessages(current => [...current, { role: 'assistant', content: (error as Error).message, error: true }])
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }

  function retry() {
    const lastQuestion = [...messages].reverse().find(item => item.role === 'user')
    if (!lastQuestion) return
    setMessages(current => {
      const withoutError = current.filter(item => !item.error)
      const index = withoutError.lastIndexOf(lastQuestion)
      return index >= 0 ? withoutError.slice(0, index) : withoutError
    })
    void ask(lastQuestion.content)
  }

  function goTo(section: string) {
    setOpen(false)
    window.setTimeout(() => scrollToSection(section), reduced ? 0 : 260)
  }

  function reset() {
    generation.current += 1
    setBusy(false)
    setMessages([])
    input.current?.focus()
  }

  const submit = (event: FormEvent) => { event.preventDefault(); void ask(draft) }
  const onComposerKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask(draft) }
  }
  const onPanelKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') { event.stopPropagation(); setOpen(false); return }
    if (event.key !== 'Tab' || !panel.current) return
    const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (!items.length) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }

  return <>
    <button ref={launcher} type="button" className={`assistant-launch${open ? ' is-hidden' : ''}`}
      aria-label="Ask ECHOTRACE" title="Ask ECHOTRACE" aria-expanded={open} aria-controls="assistant-panel" aria-haspopup="dialog"
      tabIndex={open ? -1 : 0} onClick={() => setOpen(true)}>
      <span className="launch-float">
        <LogoMark size={64} />
        <span className="pulse" aria-hidden="true" />
      </span>
    </button>
    <AnimatePresence>
      {open && <>
        <motion.div key="backdrop" className="assistant-backdrop" aria-hidden="true" onClick={() => setOpen(false)}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduced ? 0 : 0.22 }} />
        <motion.div key="panel" ref={panel} id="assistant-panel" className="assistant" role="dialog" aria-modal="true"
          aria-labelledby="assistant-title" aria-describedby="assistant-subtitle"
          initial={{ opacity: 0, scale: reduced ? 1 : 0.94, y: reduced ? 0 : 16 }} animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: reduced ? 1 : 0.96, y: reduced ? 0 : 10 }} transition={{ type: 'spring', stiffness: 420, damping: 36 }}
          onKeyDown={onPanelKey}>
          <header className="assistant-head">
            <span className="head-avatar"><LogoMark size={42} /><span className="online" aria-hidden="true" /></span>
            <div className="head-text">
              <h2 id="assistant-title">ECHOTRACE guide</h2>
              <p id="assistant-subtitle">Answers from verified product facts</p>
            </div>
            <div className="head-actions">
              {messages.length > 0 && (
                <button type="button" className="icon-btn btn-glass" aria-label="Start a new conversation" title="New conversation" onClick={reset}>
                  <RotateCcw size={17} aria-hidden="true" />
                </button>
              )}
              <button type="button" className="icon-btn btn-glass" aria-label="Close guide" title="Close" onClick={() => setOpen(false)}>
                <X size={18} aria-hidden="true" />
              </button>
            </div>
          </header>

          <div className="assistant-log" ref={log} aria-live="polite">
            <BotRow>
              Hi, I am the ECHOTRACE guide. I can explain what the workspace checks, how far to trust its score, and how to get started.
            </BotRow>
            {messages.length === 0 && (
              <div className="suggestions">
                <p className="suggestions-title">Popular questions</p>
                {STARTERS.map(starter => (
                  <button key={starter} type="button" className="suggestion" onClick={() => void ask(starter)}>
                    <span>{starter}</span><ArrowRight size={15} aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
            {messages.map((message, index) => {
              if (message.role === 'user') return <div key={index} className="msg msg-user">{message.content}</div>
              if (message.error) {
                return (
                  <BotRow key={index} alert>
                    <span className="error-line"><AlertCircle size={16} aria-hidden="true" />{message.content}</span>
                    <button type="button" className="link-btn" onClick={retry}>Try again</button>
                  </BotRow>
                )
              }
              return (
                <BotRow key={index}>
                  {message.content}
                  <div className="msg-meta">
                    {message.source && <SourceTag source={message.source} />}
                    {message.section && SECTION_NAMES[message.section] && (
                      <button type="button" className="link-btn" onClick={() => goTo(message.section!)}>
                        Go to {SECTION_NAMES[message.section]}<ArrowRight size={14} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </BotRow>
              )
            })}
            {busy && (
              <div className="bot-row" aria-label="The guide is answering">
                <span className="bot-avatar"><LogoMark size={28} /></span>
                <div className="msg msg-bot typing"><i /><i /><i /></div>
              </div>
            )}
          </div>

          <form className="assistant-form" onSubmit={submit}>
            <div className="composer">
              <label className="sr-only" htmlFor="assistant-input">Your question</label>
              <textarea id="assistant-input" ref={input} rows={1} value={draft} maxLength={MAX_QUESTION} placeholder="Ask about ECHOTRACE"
                onChange={event => setDraft(event.target.value)} onKeyDown={onComposerKey} />
              <button type="submit" className="send-btn btn-glass" aria-label="Send question" disabled={busy || !draft.trim()}>
                <ArrowUp size={19} aria-hidden="true" />
              </button>
            </div>
            <p className="composer-hint">Enter to send, Shift + Enter for a new line. The guide can be wrong; measured results are on this page.</p>
          </form>
        </motion.div>
      </>}
    </AnimatePresence>
  </>
}
