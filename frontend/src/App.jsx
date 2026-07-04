import React, { useState, useEffect, useRef, useCallback } from 'react'
import { marked } from 'marked'
import { api, formatUptime, formatSecs, escapeHtml } from './api.js'
import Header from './components/Header.jsx'
import NavRail from './components/NavRail.jsx'
import SlidePanel from './components/SlidePanel.jsx'
import ChatMain from './components/ChatMain.jsx'
import PluginDialog from './components/dialogs/PluginDialog.jsx'
import InstallSkillDialog from './components/dialogs/InstallSkillDialog.jsx'
import NewProjectDialog from './components/dialogs/NewProjectDialog.jsx'
import CreateJobModal from './components/dialogs/CreateJobModal.jsx'
import MarketplaceModal from './components/dialogs/MarketplaceModal.jsx'
import Toasts from './components/Toasts.jsx'
import GamesModal from './components/dialogs/GamesModal.jsx'
import AgentsRunPanel from './components/AgentsRunPanel.jsx'
import TerminalPanel from './components/TerminalPanel.jsx'

marked.setOptions({ breaks: true, gfm: true })

// Wrap every code block with a header + copy button. ponytail: no highlight.js
// dep — copy covers the common need; syntax colors are marginal polish.
const _renderer = new marked.Renderer()
const _PREVIEWABLE = new Set(['html', 'svg', 'xml', 'htm'])
// marked v12 passes positional args (code, infostring), not an object.
_renderer.code = (code, infostring) => {
  const lang = (infostring || '').trim().split(/\s+/)[0]
  const escaped = String(code).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const label = lang || 'code'
  const preview = _PREVIEWABLE.has(lang.toLowerCase())
    ? `<button class="preview-btn" type="button">▶ Preview</button>` : ''
  return `<div class="code-block"><div class="code-head"><span class="code-lang">${label}</span>` +
    `<span>${preview}<button class="copy-btn" type="button">Copy</button></span></div>` +
    `<pre><code>${escaped}</code></pre></div>`
}
marked.setOptions({ renderer: _renderer })

export default function App() {
  // ── Connection ──────────────────────────────────────────────────────────────
  const [connected, setConnected] = useState(false)
  const [statusText, setStatusText] = useState('Connecting...')

  // ── Model ───────────────────────────────────────────────────────────────────
  const [modelsData, setModelsData] = useState(null)
  const [pinnedModel, setPinnedModel] = useState(null)
  const [ghostBadge, setGhostBadge] = useState({ cls: 'warming', text: '⏳ Warming...' })
  const [dismissedSuggestion, setDismissedSuggestion] = useState(false)
  const [pressureBanner, setPressureBanner] = useState(null)

  // ── Chat ────────────────────────────────────────────────────────────────────
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [forceLarge, setForceLarge] = useState(false)
  const [forceSearch, setForceSearch] = useState(false)
  const [pendingImage, setPendingImage] = useState(null)
  const [pendingDocument, setPendingDocument] = useState(null)
  const [activeDocument, setActiveDocument] = useState(null)  // pinned doc — stays in context across follow-up turns until cleared

  // ── Projects ────────────────────────────────────────────────────────────────
  const [projects, setProjects] = useState([])
  const [activeProject, setActiveProject] = useState('default')

  // ── Voice ───────────────────────────────────────────────────────────────────
  const [voiceAvailable, setVoiceAvailable] = useState(false)
  const [autoSpeak, setAutoSpeak] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState(null)
  const [isRecording, setIsRecording] = useState(false)
  const [ttsMode, setTtsMode] = useState('browser')
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  // ── Nav panel ───────────────────────────────────────────────────────────────
  const [activePanel, setActivePanel] = useState(null)

  // ── Panel data ──────────────────────────────────────────────────────────────
  const [systemStatus, setSystemStatus] = useState(null)
  const [hardwareStatus, setHardwareStatus] = useState(null)
  const [hwLive, setHwLive] = useState(null)
  const [skills, setSkills] = useState([])
  const [agents, setAgents] = useState([])
  const [plugins, setPlugins] = useState([])
  const [healthData, setHealthData] = useState(null)
  const [govPending, setGovPending] = useState([])
  const [schedulerJobs, setSchedulerJobs] = useState([])
  const [stats, setStats] = useState(null)

  // ── Research ────────────────────────────────────────────────────────────────
  const [researchOpen, setResearchOpen] = useState(false)
  const [researchDepth, setResearchDepth] = useState('standard')
  const [researchSteps, setResearchSteps] = useState([])
  const [researchAnswer, setResearchAnswer] = useState(null)
  const [researchSources, setResearchSources] = useState([])
  const [isResearching, setIsResearching] = useState(false)
  const researchSSERef = useRef(null)

  // ── Browser ─────────────────────────────────────────────────────────────────
  const [browserOpen, setBrowserOpen] = useState(false)
  const [browserSteps, setBrowserSteps] = useState([])
  const [browserScreen, setBrowserScreen] = useState(null)
  const [browserResult, setBrowserResult] = useState(null)
  const [isBrowsing, setIsBrowsing] = useState(false)
  const browserSSERef = useRef(null)

  // ── Image / Video ───────────────────────────────────────────────────────────
  const [imagePanelOpen, setImagePanelOpen] = useState(false)
  const [videoPanelOpen, setVideoPanelOpen] = useState(false)

  // ── Artifact (live HTML/SVG preview) ──────────────────────────────────────────
  const [artifactHtml, setArtifactHtml] = useState(null)

  // ── Dialogs ─────────────────────────────────────────────────────────────────
  const [pluginDialogOpen, setPluginDialogOpen] = useState(false)
  const [installSkillOpen, setInstallSkillOpen] = useState(false)
  const [newProjectOpen, setNewProjectOpen] = useState(false)
  const [createJobOpen, setCreateJobOpen] = useState(false)
  const [marketplaceOpen, setMarketplaceOpen] = useState(false)

  // ── Toasts ────────────────────────────────────────────────────────────────────
  const [toasts, setToasts] = useState([])
  const seenHealRef = useRef(0)  // latest heal-action timestamp already shown

  const pushToast = useCallback((msg, kind = 'info', icon = '🔧') => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, msg, kind, icon }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 6000)
  }, [])

  // ── Games ─────────────────────────────────────────────────────────────────────
  const [gamesOpen, setGamesOpen] = useState(false)

  // ── Agent company (live orchestration) ────────────────────────────────────────
  const [agentTask, setAgentTask] = useState(null)

  // ── Terminal ──────────────────────────────────────────────────────────────────
  const [terminalOpen, setTerminalOpen] = useState(false)

  // ── Helpers ─────────────────────────────────────────────────────────────────
  const activeModelRef = useRef('')
  const abortRef = useRef(null)

  const stopGeneration = useCallback(() => {
    if (abortRef.current) abortRef.current.abort()
  }, [])

  const addMessage = useCallback((role, content, extra = {}) => {
    setMessages(prev => [...prev, { id: Date.now() + Math.random(), role, content, ...extra }])
  }, [])

  const showGhostBadge = useCallback((strategy) => {
    const map = {
      full_gpu:   { cls: 'full-gpu',   text: '⚡ Full GPU' },
      kv_offload: { cls: 'kv-offload', text: '🔀 KV Offload' },
      hybrid:     { cls: 'hybrid',     text: '🔀 Hybrid' },
      cpu_only:   { cls: 'cpu-only',   text: '💻 CPU Only' },
    }
    const info = map[strategy] || { cls: 'hybrid', text: strategy }
    setGhostBadge(info)
  }, [])

  // ── Init polling ────────────────────────────────────────────────────────────
  const checkHealth = useCallback(async () => {
    try {
      const d = await api.health()
      setConnected(d.status !== 'error')
      setStatusText(d.message || 'Online')
    } catch {
      setConnected(false)
      setStatusText('Connection failed')
    }
  }, [])

  const loadSystemStatus = useCallback(async () => {
    try { setSystemStatus(await api.systemStatus()) } catch {}
  }, [])

  const loadHardwareStatus = useCallback(async () => {
    try { setHardwareStatus(await api.systemHardware()) } catch {}
  }, [])

  const loadHwLive = useCallback(async () => {
    try {
      const d = await api.systemHardwareLive()
      setHwLive(d)
      // Surface any NEW self-heal actions as a toast (auto-fixed heads-up)
      const heals = d.heal_actions || []
      const labels = {
        ollama_started: 'Ollama was down — auto-restarted it ✓',
        ollama_recovered: 'Ollama back online ✓',
        model_switched: 'Switched to a model that fits your hardware ✓',
        ollama_start_failed: 'Tried to restart Ollama (needs attention)',
      }
      for (const h of heals) {
        if (h.ts > seenHealRef.current) {
          seenHealRef.current = h.ts
          const msg = labels[h.action] || `Auto-fixed: ${h.action}`
          pushToast(msg, h.action.includes('fail') ? 'warn' : 'ok', '🔧')
        }
      }
    } catch {}
  }, [pushToast])

  const loadModels = useCallback(async () => {
    try {
      const d = await api.systemModels()
      setModelsData(d)
      if (!pinnedModel && d.models?.length) {
        const active = d.models.find(m => m.name === d.active)
        if (active?.strategy) showGhostBadge(active.strategy)
      }
    } catch {}
  }, [pinnedModel, showGhostBadge])

  const loadSkills = useCallback(async () => {
    try {
      const d = await api.skills()
      setSkills(d.skills || [])
    } catch {}
  }, [])

  const loadAgents = useCallback(async () => {
    try {
      const d = await api.agents()
      setAgents(d.agents || [])
    } catch {}
  }, [])

  const loadPlugins = useCallback(async () => {
    try {
      const d = await api.plugins()
      setPlugins(d.plugins || [])
    } catch {}
  }, [])

  const loadHealth = useCallback(async () => {
    try {
      const [curr, sched] = await Promise.all([
        api.monitoringCurrent(),
        api.schedulerJobs(),
      ])
      setHealthData({ system: curr.system, jobs: sched.jobs || [] })
    } catch {}
  }, [])

  const loadGov = useCallback(async () => {
    try {
      const d = await api.govPending()
      setGovPending(d.pending || [])
    } catch {}
  }, [])

  const loadScheduler = useCallback(async () => {
    try {
      const d = await api.schedulerJobs()
      setSchedulerJobs(d.jobs || [])
    } catch {}
  }, [])

  const loadStats = useCallback(async () => {
    try {
      const [td, md] = await Promise.all([api.taskStats(), api.memoryStats()])
      setStats({ tasks: td, memory: md })
    } catch {}
  }, [])

  const loadProjects = useCallback(async () => {
    try {
      const d = await api.projects()
      setProjects(d.projects || [])
    } catch {}
  }, [])

  const loadChatHistory = useCallback(async (projectId) => {
    try {
      const d = await api.chatHistory(projectId)
      const msgs = (d.messages || [])
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .map((m, i) => ({ id: `h${i}`, role: m.role, content: m.content }))
      setMessages(msgs)
    } catch {}
  }, [])

  useEffect(() => {
    // Initial load
    checkHealth()
    loadSystemStatus()
    loadHardwareStatus()
    loadModels()
    loadSkills()
    loadAgents()
    loadPlugins()
    loadHealth()
    loadGov()
    loadScheduler()
    loadStats()
    loadProjects()
    loadHwLive()
    initVoice()
    loadChatHistory('default')

    // Polling
    const intervals = [
      setInterval(checkHealth, 10000),
      setInterval(loadSystemStatus, 10000),
      setInterval(loadAgents, 30000),
      setInterval(loadHwLive, 5000),
      setInterval(loadModels, 60000),
      setInterval(loadHealth, 10000),
      setInterval(loadGov, 15000),
      setInterval(loadScheduler, 30000),
    ]
    return () => intervals.forEach(clearInterval)
  }, []) // eslint-disable-line

  // ── Voice init ──────────────────────────────────────────────────────────────
  const initVoice = async () => {
    try {
      const d = await api.voiceStatus()
      setVoiceAvailable(d.stt)
      setTtsMode(d.tts_backend)
    } catch {}
  }

  // ── Model switching ─────────────────────────────────────────────────────────
  const switchModel = useCallback(async (model) => {
    if (!model) {
      setPinnedModel(null)
      setGhostBadge({ cls: 'warming', text: '...' })
      addMessage('assistant', '🤖 Auto-routing active — model selected per task complexity.')
      return
    }
    setPinnedModel(model)
    setGhostBadge({ cls: 'warming', text: '⏳ Switching...' })
    try {
      await api.switchModel(model)
      activeModelRef.current = model
      try {
        const gd = await api.ghostEngine(model)
        if (gd.strategy) showGhostBadge(gd.strategy)
      } catch {}
      await loadModels()
      addMessage('assistant', `🤖 Switched to **${model}**. Pre-warming in background…`)
    } catch (e) {
      addMessage('assistant', `**Switch failed:** ${e.message}`)
    }
  }, [addMessage, loadModels, showGhostBadge])

  // ── Chat ────────────────────────────────────────────────────────────────────
  const handleChat = useCallback(async (message, imageFile = null, docFile = null) => {
    // Slash command: /game — open the arcade. No LLM call.
    if (typeof message === 'string' && message.trim().toLowerCase() === '/game') {
      setGamesOpen(true)
      return
    }

    // Slash command: /terminal — open the terminal. No LLM call.
    if (typeof message === 'string' && message.trim().toLowerCase() === '/terminal') {
      setTerminalOpen(true)
      return
    }

    // Slash command: /task <goal> — run it through the agent company, live.
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/task')) {
      const goal = message.trim().slice(5).trim()
      if (goal) { addMessage('user', `/task ${goal}`); setAgentTask(goal) }
      else addMessage('assistant', 'Give me a goal: `/task build a landing page for a coffee shop`')
      return
    }

    // Slash command: /doctor — run diagnostics, render inline. No LLM call.
    if (typeof message === 'string' && message.trim().toLowerCase() === '/doctor') {
      addMessage('user', '/doctor')
      addMessage('assistant', '🩺 Running diagnostics…')
      try {
        const d = await api.doctor()
        setMessages(prev => prev.slice(0, -1))
        addMessage('assistant', d.report_md || 'No report returned.', { done: true })
      } catch (e) {
        setMessages(prev => prev.slice(0, -1))
        addMessage('assistant', `**Doctor failed:** ${e.message}`)
      }
      return
    }

    // Show user message immediately
    if (docFile) {
      addMessage('user', `📄 ${docFile.name}${message ? ' — ' + message : ''}`)
    } else {
      addMessage('user', imageFile ? `[Image] ${message || 'Describe this image'}` : message)
    }

    setIsLoading(true)
    const thinkingId = Date.now()
    setMessages(prev => [...prev, { id: thinkingId, role: 'thinking', content: '⏳ ILLIP is thinking...' }])

    if (imageFile) {
      const form = new FormData()
      form.append('file', imageFile)
      form.append('prompt', message || 'Describe this image in detail.')
      try {
        const d = await api.visionAnalyze(form)
        setMessages(prev => prev.filter(m => m.id !== thinkingId))
        addMessage('assistant', d.description || '(no description)')
      } catch (e) {
        setMessages(prev => prev.filter(m => m.id !== thinkingId))
        addMessage('assistant', `Vision error: ${e.message}`)
      }
      setIsLoading(false)
      return
    }

    let chatMessage = message
    let docContext = docFile ? null : activeDocument
    if (docFile) {
      const form = new FormData()
      form.append('file', docFile)
      try {
        const d = await api.documentAnalyze(form)
        if (d.error || !d.text) {
          setMessages(prev => prev.filter(m => m.id !== thinkingId))
          addMessage('assistant', `**Couldn't read PDF:** ${d.error || 'no text extracted'}`)
          setIsLoading(false)
          return
        }
        docContext = { filename: d.filename, text: d.text, truncated: d.truncated }
        setActiveDocument(docContext)
      } catch (e) {
        setMessages(prev => prev.filter(m => m.id !== thinkingId))
        addMessage('assistant', `**PDF upload failed:** ${e.message}`)
        setIsLoading(false)
        return
      }
    }
    if (docContext) {
      // Question first — protects it from tail-truncation in context_manager
      // if the whole message exceeds the model's budget. Document dump last,
      // so IT gets cut before the actual question ever would.
      chatMessage = `${message || 'Explain this document fully.'}\n\n---\nDocument "${docContext.filename}" contents:\n\n${docContext.text}${docContext.truncated ? '\n\n[... truncated]' : ''}`
    }

    try {
      const payload = {
        message: chatMessage,
        include_memory: true,
        model: pinnedModel || (forceLarge ? activeModelRef.current : null) || null,
        force_search: forceSearch,
        project_id: activeProject,
      }
      const controller = new AbortController()
      abortRef.current = controller
      const res = await api.chatStream(payload, controller.signal)
      setMessages(prev => prev.filter(m => m.id !== thinkingId))

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        addMessage('assistant', `**Error:** ${err.detail || res.statusText}`)
        return
      }

      const msgId = Date.now() + 1
      setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', routing: null }])

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let raw = ''
      let buffer = ''
      let routing = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const parsed = JSON.parse(payload)
            if (parsed.routing && !routing) {
              routing = parsed.routing
              activeModelRef.current = routing.model
              const searchTag = routing.needs_search ? ' · 🔍 searched' : ''
              const pinTag = pinnedModel ? ' · 📌 pinned' : ''
              routing._badge = `🤖 ${routing.model} · ${routing.complexity} · ${routing.pressure} pressure${searchTag}${pinTag}`
              if (routing.warning) {
                setPressureBanner({ text: routing.warning, cls: routing.pressure })
              } else {
                setPressureBanner(null)
              }
              setForceLarge(false)
              setForceSearch(false)
              // Show "retrieving memory..." placeholder until first token arrives
              setMessages(prev => prev.map(m => m.id === msgId
                ? { ...m, routing, content: '', _pending: '🧠 Retrieving memory…' }
                : m))
            } else if (parsed.token) {
              raw += parsed.token
              setMessages(prev => prev.map(m => m.id === msgId ? { ...m, content: raw, _pending: null } : m))
            } else if (parsed.tool_calls) {
              const names = parsed.tool_calls.join(', ')
              setMessages(prev => prev.map(m => m.id === msgId
                ? { ...m, _pending: `🔧 Using tools: ${names}…` }
                : m))
            } else if (parsed.tool_result) {
              setMessages(prev => prev.map(m => m.id === msgId
                ? { ...m, _pending: `✅ ${parsed.tool_result.name} done` }
                : m))
            }
          } catch {}
        }
      }

      // Mark done — triggers feedback buttons
      setMessages(prev => prev.map(m => m.id === msgId ? { ...m, done: true, question: message } : m))

      if (autoSpeak && raw) speakText(raw)

    } catch (e) {
      setMessages(prev => prev.filter(m => m.id !== thinkingId))
      if (e.name !== 'AbortError') {
        addMessage('assistant', `**Connection error:** ${e.message}`)
      }
    } finally {
      abortRef.current = null
      setIsLoading(false)
    }
  }, [pinnedModel, forceLarge, forceSearch, activeProject, autoSpeak, addMessage, activeDocument])

  // ── Regenerate ────────────────────────────────────────────────────────────────
  const regenerate = useCallback(() => {
    if (isLoading) return
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUser) return
    // Drop the trailing assistant reply so the new one takes its place
    setMessages(prev => {
      const idx = prev.map(m => m.role).lastIndexOf('assistant')
      return idx === -1 ? prev : prev.slice(0, idx)
    })
    handleChat(lastUser.content)
  }, [messages, isLoading]) // eslint-disable-line

  // ── TTS ─────────────────────────────────────────────────────────────────────
  const speakText = useCallback((text) => {
    const plain = text.replace(/```[\s\S]*?```/g, 'code block')
      .replace(/`[^`]+`/g, '').replace(/[#*_~[\]()]/g, '').trim()
    if (!plain) return
    if (ttsMode === 'piper') {
      api.speak(plain.slice(0, 500)).then(res => {
        if (res.status === 501) {
          browserSpeak(plain)
        } else if (res.ok) {
          res.blob().then(blob => {
            const url = URL.createObjectURL(blob)
            const a = new Audio(url)
            a.play()
            a.onended = () => URL.revokeObjectURL(url)
          })
        }
      }).catch(() => browserSpeak(plain))
    } else {
      browserSpeak(plain)
    }
  }, [ttsMode])

  const browserSpeak = (text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text.slice(0, 500))
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find(v => v.lang.startsWith('en') && v.localService) || voices[0]
    if (preferred) utt.voice = preferred
    window.speechSynthesis.speak(utt)
  }

  // ── Voice recording ─────────────────────────────────────────────────────────
  const toggleMic = useCallback(async () => {
    if (!voiceAvailable) {
      setVoiceStatus({ msg: 'STT not available', type: 'error' })
      return
    }
    if (isRecording) {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop()
        mediaRecorderRef.current.stream.getTracks().forEach(t => t.stop())
      }
      setIsRecording(false)
      setVoiceStatus({ msg: '⏳ Transcribing…', type: 'loading' })
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        audioChunksRef.current = []
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
        const mr = new MediaRecorder(stream, { mimeType })
        mr.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
        mr.onstop = async () => {
          if (!audioChunksRef.current.length) { setVoiceStatus(null); return }
          const mimeType = audioChunksRef.current[0].type || 'audio/webm'
          const ext = mimeType.includes('ogg') ? '.ogg' : '.webm'
          const blob = new Blob(audioChunksRef.current, { type: mimeType })
          audioChunksRef.current = []
          const form = new FormData()
          form.append('file', blob, `recording${ext}`)
          try {
            const d = await api.transcribe(form)
            if (d.text) {
              setVoiceStatus({ msg: `✓ "${d.text.slice(0, 60)}…"`, type: 'ok' })
              setTimeout(() => setVoiceStatus(null), 3000)
              // Insert text into input via custom event
              window.dispatchEvent(new CustomEvent('voice-transcribed', { detail: d.text }))
            } else {
              setVoiceStatus({ msg: 'No speech detected', type: 'error' })
              setTimeout(() => setVoiceStatus(null), 2000)
            }
          } catch (e) {
            setVoiceStatus({ msg: `Transcription failed: ${e.message}`, type: 'error' })
          }
        }
        mr.start(250)
        mediaRecorderRef.current = mr
        setIsRecording(true)
        setVoiceStatus({ msg: '🎙 Recording…', type: 'recording' })
      } catch (e) {
        setVoiceStatus({ msg: `Mic error: ${e.message}`, type: 'error' })
      }
    }
  }, [voiceAvailable, isRecording])

  // ── Research ────────────────────────────────────────────────────────────────
  const startResearch = useCallback((query) => {
    if (!query) return
    setResearchOpen(true)
    setResearchSteps([])
    setResearchAnswer(null)
    setResearchSources([])
    setIsResearching(true)
    if (researchSSERef.current) researchSSERef.current.close()
    const sse = new EventSource(api.researchStreamUrl(query, researchDepth))
    researchSSERef.current = sse
    sse.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'done') {
        sse.close()
        researchSSERef.current = null
        setResearchAnswer(data.data?.answer || '')
        setResearchSources(data.data?.sources || [])
        setIsResearching(false)
        setResearchSteps(prev => [...prev, { type: 'done', text: `✅ Done` }])
      } else if (data.type === 'error') {
        sse.close()
        researchSSERef.current = null
        setIsResearching(false)
        setResearchSteps(prev => [...prev, { type: 'error', text: `❌ ${data.message}` }])
      } else {
        setResearchSteps(prev => [...prev, { type: data.type, text: data.message }])
      }
    }
    sse.onerror = () => {
      sse.close()
      researchSSERef.current = null
      setIsResearching(false)
      setResearchSteps(prev => [...prev, { type: 'error', text: '❌ Connection lost' }])
    }
  }, [researchDepth])

  // ── Browser ─────────────────────────────────────────────────────────────────
  const runBrowser = useCallback((task, startUrl, headless) => {
    setBrowserSteps([])
    setBrowserScreen(null)
    setBrowserResult(null)
    setIsBrowsing(true)
    if (browserSSERef.current) browserSSERef.current.close()
    const sse = new EventSource(api.browserStreamUrl(task, startUrl, headless))
    browserSSERef.current = sse
    sse.onmessage = (e) => {
      const event = JSON.parse(e.data)
      const { type, data = {} } = event
      if (type === 'done' || type === 'failed') {
        sse.close()
        browserSSERef.current = null
        setIsBrowsing(false)
        if (type === 'done') {
          setBrowserResult(data.result || '')
          if (data.screenshot_b64) setBrowserScreen(data.screenshot_b64)
        }
        setBrowserSteps(prev => [...prev, {
          type: type === 'done' ? 'done' : 'error',
          text: type === 'done' ? `✅ Complete — ${data.steps_taken} steps` : `❌ Failed: ${data.reason}`
        }])
        return
      }
      if (type === 'step' && data.screenshot_b64) setBrowserScreen(data.screenshot_b64)
      const stepText = {
        start: `🤖 Starting: ${data.task}`,
        setup: `🔧 ${data.message}`,
        plan: data.subtasks ? `📋 Plan: ${data.subtasks.join(' → ')}` : `🧠 ${data.message}`,
        subtask_start: `▶ [${data.idx}/${data.total}] ${data.subtask}`,
        subtask_done: `✅ [${data.idx}] ${data.summary}`,
        step: `• ${data.action}${data.target ? ' "' + data.target + '"' : ''}${data.error ? ' ❌ ' + data.error : ''}`,
      }[type] || `• ${type}`
      setBrowserSteps(prev => [...prev, { type: data.error ? 'error' : type, text: stepText }])
    }
    sse.onerror = () => {
      sse.close()
      browserSSERef.current = null
      setIsBrowsing(false)
      setBrowserSteps(prev => [...prev, { type: 'error', text: '❌ Connection lost' }])
    }
  }, [])

  // ── Governance ──────────────────────────────────────────────────────────────
  const govApprove = useCallback(async (id) => {
    try { await api.govApprove(id); loadGov() } catch {}
  }, [loadGov])

  const govDeny = useCallback(async (id) => {
    try { await api.govDeny(id); loadGov() } catch {}
  }, [loadGov])

  // ── Scheduler ───────────────────────────────────────────────────────────────
  const schedRunNow = useCallback(async (id) => {
    try { await api.runJob(id); setTimeout(loadScheduler, 1000) } catch {}
  }, [loadScheduler])

  const schedToggle = useCallback(async (id, enable) => {
    try { await api.toggleJob(id, enable); loadScheduler() } catch {}
  }, [loadScheduler])

  // ── Refresh ─────────────────────────────────────────────────────────────────
  const refreshSystem = useCallback(async () => {
    try {
      const d = await api.refresh(activeProject)
      addMessage('assistant', `**↺ Context refreshed**\n${d.cleared?.join(' · ')}\nAll history preserved on disk.`)
    } catch (e) {
      addMessage('assistant', `**Refresh failed:** ${e.message}`)
    }
  }, [activeProject, addMessage])

  // ── Panel toggle ────────────────────────────────────────────────────────────
  const togglePanel = useCallback((name) => {
    setActivePanel(prev => prev === name ? null : name)
  }, [])

  return (
    <div className="app-container">
      <div className="grid-bg" />
      <div className="scanlines" />

      <Header
        connected={connected}
        statusText={statusText}
        modelsData={modelsData}
        pinnedModel={pinnedModel}
        ghostBadge={ghostBadge}
        dismissedSuggestion={dismissedSuggestion}
        projects={projects}
        activeProject={activeProject}
        hwLive={hwLive}
        onSwitchModel={switchModel}
        onSwitchProject={(id) => {
          setActiveProject(id)
          loadChatHistory(id)
        }}
        onDismissSuggestion={() => setDismissedSuggestion(true)}
        onNewProject={() => setNewProjectOpen(true)}
        onRefresh={refreshSystem}
        onAutoSpeak={() => setAutoSpeak(p => !p)}
        autoSpeak={autoSpeak}
      />

      <div className="app-body">
        <NavRail
          activePanel={activePanel}
          onTogglePanel={togglePanel}
          agentCount={agents.filter(a => a.is_available).length}
          govCount={govPending.length}
        />

        <SlidePanel
          activePanel={activePanel}
          onClose={() => setActivePanel(null)}
          systemStatus={systemStatus}
          hardwareStatus={hardwareStatus}
          hwLive={hwLive}
          modelsData={modelsData}
          pinnedModel={pinnedModel}
          skills={skills}
          agents={agents}
          plugins={plugins}
          healthData={healthData}
          govPending={govPending}
          schedulerJobs={schedulerJobs}
          stats={stats}
          onSwitchModel={switchModel}
          onGovApprove={govApprove}
          onGovDeny={govDeny}
          onSchedRun={schedRunNow}
          onSchedToggle={schedToggle}
          onAddPlugin={() => setPluginDialogOpen(true)}
          onDeletePlugin={async (name) => {
            if (!confirm(`Delete plugin "${name}"?`)) return
            await api.deletePlugin(name)
            loadPlugins()
          }}
          onInstallSkill={() => setInstallSkillOpen(true)}
          onShowMarketplace={() => setMarketplaceOpen(true)}
          onCreateJob={() => setCreateJobOpen(true)}
        />

        <ChatMain
          messages={messages}
          isLoading={isLoading}
          forceLarge={forceLarge}
          forceSearch={forceSearch}
          pressureBanner={pressureBanner}
          voiceAvailable={voiceAvailable}
          isRecording={isRecording}
          voiceStatus={voiceStatus}
          autoSpeak={autoSpeak}
          pendingImage={pendingImage}
          pendingDocument={pendingDocument}
          activeDocument={activeDocument}
          onClearActiveDocument={() => setActiveDocument(null)}
          researchOpen={researchOpen}
          researchDepth={researchDepth}
          researchSteps={researchSteps}
          researchAnswer={researchAnswer}
          researchSources={researchSources}
          isResearching={isResearching}
          browserOpen={browserOpen}
          browserSteps={browserSteps}
          browserScreen={browserScreen}
          browserResult={browserResult}
          isBrowsing={isBrowsing}
          imagePanelOpen={imagePanelOpen}
          videoPanelOpen={videoPanelOpen}
          activeModel={activeModelRef.current}
          onChat={handleChat}
          onStop={stopGeneration}
          onRegenerate={regenerate}
          onOpenArtifact={setArtifactHtml}
          artifactHtml={artifactHtml}
          onCloseArtifact={() => setArtifactHtml(null)}
          onOpenGames={() => setGamesOpen(true)}
          onOpenTerminal={() => setTerminalOpen(true)}
          onToggleForceLarge={() => setForceLarge(p => !p)}
          onToggleForceSearch={() => setForceSearch(p => !p)}
          onMic={toggleMic}
          onSetPendingImage={setPendingImage}
          onSetPendingDocument={setPendingDocument}
          onStartResearch={startResearch}
          onCloseResearch={() => { setResearchOpen(false); if (researchSSERef.current) researchSSERef.current.close() }}
          onSetResearchDepth={setResearchDepth}
          onOpenBrowser={() => setBrowserOpen(true)}
          onCloseBrowser={() => { setBrowserOpen(false); if (browserSSERef.current) browserSSERef.current.close() }}
          onRunBrowser={runBrowser}
          onOpenImage={() => setImagePanelOpen(true)}
          onCloseImage={() => setImagePanelOpen(false)}
          onOpenVideo={() => setVideoPanelOpen(true)}
          onCloseVideo={() => setVideoPanelOpen(false)}
          onFeedback={async (question, response, isGood) => {
            try {
              if (isGood) await api.learningApprove(question, response)
              else await api.learningCorrect(question, response)
            } catch {}
          }}
          onSpeak={speakText}
        />
      </div>

      {/* Dialogs */}
      {pluginDialogOpen && (
        <PluginDialog
          onClose={() => setPluginDialogOpen(false)}
          onSave={async (spec) => {
            await api.savePlugin(spec)
            setPluginDialogOpen(false)
            loadPlugins()
            loadSkills()
          }}
        />
      )}
      {installSkillOpen && (
        <InstallSkillDialog
          onClose={() => setInstallSkillOpen(false)}
          onInstalled={() => { setInstallSkillOpen(false); loadSkills() }}
        />
      )}
      {newProjectOpen && (
        <NewProjectDialog
          onClose={() => setNewProjectOpen(false)}
          onCreate={async (name) => {
            const p = await api.createProject(name)
            setNewProjectOpen(false)
            await loadProjects()
            setActiveProject(p.id)
          }}
        />
      )}
      {createJobOpen && (
        <CreateJobModal
          onClose={() => setCreateJobOpen(false)}
          onCreate={async (data) => {
            await api.createJob(data)
            setCreateJobOpen(false)
            loadScheduler()
          }}
        />
      )}
      {marketplaceOpen && (
        <MarketplaceModal
          onClose={() => setMarketplaceOpen(false)}
          onInstall={async (spec) => {
            await api.savePlugin(spec)
            setMarketplaceOpen(false)
            loadPlugins()
          }}
        />
      )}
      {gamesOpen && <GamesModal onClose={() => setGamesOpen(false)} />}
      {agentTask && <AgentsRunPanel task={agentTask} onClose={() => setAgentTask(null)} />}
      {terminalOpen && <TerminalPanel onClose={() => setTerminalOpen(false)} />}

      <Toasts toasts={toasts} onDismiss={(id) => setToasts(prev => prev.filter(t => t.id !== id))} />
    </div>
  )
}
