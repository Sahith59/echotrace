import { useEffect } from 'react'
import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import Nav from './components/Nav'
import Assistant from './components/Assistant'
import AuthPage from './pages/AuthPage'
import { Hero, Questions, Walkthrough } from './sections/Story'
import { Benchmark, Closing, Demo, Faq, HowItWorks, Limits } from './sections/Evidence'
import { SessionProvider, useSession } from './lib/session'
import { usePath } from './lib/router'
import { DEMO_VIDEO_URL } from './config'

function Notice() {
  const { notice, clearNotice } = useSession()
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(clearNotice, 4000)
    return () => window.clearTimeout(timer)
  }, [notice, clearNotice])
  return (
    <AnimatePresence>
      {notice && (
        <motion.div className="toast glass" role="status" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {notice}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Home() {
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <Nav />
    <main id="main">
      <Hero />
      <Questions />
      <Walkthrough />
      <Benchmark />
      <HowItWorks />
      <Demo videoUrl={DEMO_VIDEO_URL} />
      <Limits />
      <Faq />
      <Closing />
    </main>
    <footer className="footer shell">
      <p>ECHOTRACE is a hackathon prototype for the NSA HEARSAY challenge at HackGT 13. It is not an official NSA product or endorsement.</p>
      <p>Built with pinned open models: NII wav2vec anti-deepfake, Microsoft WavLM and faster-whisper.</p>
    </footer>
  </>
}

function Routes() {
  const path = usePath()
  if (path === '/login') return <AuthPage key="login" mode="login" />
  if (path === '/signup') return <AuthPage key="signup" mode="signup" />
  return <Home />
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <SessionProvider>
        <Routes />
        <Notice />
        <Assistant />
      </SessionProvider>
    </MotionConfig>
  )
}
