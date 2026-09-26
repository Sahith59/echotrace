import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { MotionConfig } from 'motion/react'
import '@fontsource-variable/ibm-plex-sans'
import '@fontsource/ibm-plex-mono/latin-400.css'
import './styles.css'
import './redesign.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user"><App /></MotionConfig>
  </React.StrictMode>,
)
