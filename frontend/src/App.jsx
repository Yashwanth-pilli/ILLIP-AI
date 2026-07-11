import React, { useState, useEffect, useRef, useCallback } from 'react'
import { marked } from 'marked'
import { api, formatUptime, formatSecs, escapeHtml } from './api.js'
import Header from './components/Header.jsx'
import RamHelper from './components/RamHelper.jsx'
import NavRail from './components/NavRail.jsx'
import SlidePanel from './components/SlidePanel.jsx'
import ChatMain from './components/ChatMain.jsx'
import PluginDialog from './components/dialogs/PluginDialog.jsx'
import InstallSkillDialog from './components/dialogs/InstallSkillDialog.jsx'
import NewProjectDialog from './components/dialogs/NewProjectDialog.jsx'
import NewChatChoiceDialog from './components/dialogs/NewChatChoiceDialog.jsx'
import DiagnosticPanel from './components/DiagnosticPanel.jsx'
import CreateJobModal from './components/dialogs/CreateJobModal.jsx'
import MarketplaceModal from './components/dialogs/MarketplaceModal.jsx'
import Toasts from './components/Toasts.jsx'
import GamesModal from './components/dialogs/GamesModal.jsx'
import FirstRunWizard from './components/dialogs/FirstRunWizard.jsx'
import AgentsRunPanel from './components/AgentsRunPanel.jsx'
import { ILLIP_GUIDE } from './guide.js'

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
  const [chatModes, setChatModes] = useState({ caveman: false, ponytail: false })
  const [skills, setSkills] = useState([])
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
  const [hasSavedSession, setHasSavedSession] = useState(false)
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
  const [newChatChoiceOpen, setNewChatChoiceOpen] = useState(false)
  const [wizardDismissed, setWizardDismissed] = useState(
    () => localStorage.getItem('illip_wizard_done') === '1'
  )
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

  // ── Reply-style modes (caveman / ponytail) ──────────────────────────────────
  const loadChatModes = useCallback(async () => {
    try {
      const d = await api.getChatModes()
      const state = {}
      for (const m of d.modes || []) state[m.name] = m.enabled
      setChatModes(prev => ({ ...prev, ...state }))
    } catch {}
  }, [])

  const toggleChatMode = useCallback(async (name) => {
    const next = !chatModes[name]
    setChatModes(prev => ({ ...prev, [name]: next }))  // optimistic
    try {
      await api.setChatMode(name, next)
      pushToast(
        `${name === 'caveman' ? '🗿 Caveman' : '🐴 Ponytail'} mode ${next ? 'on' : 'off'}`,
        'ok', next ? '✅' : '⚪',
      )
    } catch {
      setChatModes(prev => ({ ...prev, [name]: !next }))  // revert on failure
    }
  }, [chatModes, pushToast])

  // ── Guardian auto-watch: surface risky new downloads as toasts ───────────────
  const pollGuardianAlerts = useCallback(async () => {
    try {
      const d = await api.guardianAlerts()
      for (const a of d.alerts || []) {
        pushToast(
          `${a.file}: ${a.message} — type "/scan ${a.path}" for the full check.`,
          a.level === 'danger' ? 'warn' : 'info',
          a.level === 'danger' ? '🔴' : '🟡',
        )
      }
    } catch {}
  }, [pushToast])

  // ── Games ─────────────────────────────────────────────────────────────────────
  const [gamesOpen, setGamesOpen] = useState(false)

  // ── Agent company (live orchestration) ────────────────────────────────────────
  const [agentTask, setAgentTask] = useState(null)

  // Diagnostics/repair (/doctor, /heal) render in an ephemeral overlay, never chat.
  const [diagnostic, setDiagnostic] = useState(null)  // { title, md, busy, kind } | null

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

  const deleteModel = useCallback(async (name) => {
    if (!confirm(`Delete model "${name}" from disk? You can re-download it any time.`)) return
    try {
      const d = await api.modelDelete(name)
      if (d.detail) { pushToast(`⚠️ ${d.detail}`); return }
      pushToast(`🗑️ Deleted ${name}`)
      await loadModels()
    } catch (e) {
      pushToast(`Delete failed: ${e.message || e}`)
    }
  }, [loadModels, pushToast])

  const loadSkills = useCallback(async () => {
    try {
      const d = await api.skills()
      setSkills(d.skills || [])
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

  // "Just chat" — instant, no naming step. Auto-titled so it still shows up
  // sensibly in the Chats sidebar later.
  const startBlankChat = useCallback(async () => {
    const stamp = new Date().toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    const p = await api.createProject(`Chat ${stamp}`)
    await loadProjects()
    setActiveProject(p.id)
    setMessages([])
  }, [loadProjects])

  const loadChatHistory = useCallback(async (projectId) => {
    try {
      const d = await api.chatHistory(projectId)
      const msgs = (d.messages || [])
        .filter(m => m.role === 'user' || m.role === 'assistant')
        .map((m, i) => ({ id: `h${i}`, role: m.role, content: m.content }))
      setMessages(msgs)
    } catch {}
  }, [])

  const deleteProject = useCallback(async (projectId) => {
    if (projectId === 'default') return
    if (!window.confirm('Delete this space? This removes its chat history and memory permanently.')) return
    try {
      await api.deleteProject(projectId)
      if (activeProject === projectId) {
        setActiveProject('default')
        loadChatHistory('default')
      }
      await loadProjects()
    } catch {}
  }, [activeProject, loadProjects, loadChatHistory])

  // Remember the active chat across refreshes
  useEffect(() => {
    localStorage.setItem('illip_active_project', activeProject)
  }, [activeProject])

  useEffect(() => {
    // Initial load
    checkHealth()
    loadSystemStatus()
    loadHardwareStatus()
    loadModels()
    loadSkills()
    loadPlugins()
    loadHealth()
    loadGov()
    loadScheduler()
    loadStats()
    loadProjects()
    loadHwLive()
    loadChatModes()
    initVoice()
    // Continue where you left off: restore the last active chat + its
    // messages on refresh. New chats are explicit (+ button) — a page
    // refresh must never look like the conversation vanished.
    ;(async () => {
      const saved = localStorage.getItem('illip_active_project') || 'default'
      setActiveProject(saved)
      await loadChatHistory(saved)
    })()

    // Polling
    const intervals = [
      setInterval(checkHealth, 10000),
      setInterval(loadSystemStatus, 10000),
      setInterval(loadHwLive, 5000),
      setInterval(loadModels, 60000),
      setInterval(loadHealth, 10000),
      setInterval(loadGov, 15000),
      setInterval(loadScheduler, 30000),
      setInterval(pollGuardianAlerts, 20000),
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

  // ── Diagnostics/repair — run in the ephemeral overlay, keep chat clean ───────
  const runDiagnostic = useCallback(async (kind) => {
    const meta = kind === 'heal'
      ? { title: '🔧 Repair', api: api.doctorHeal, rerunLabel: '↻ Repair again' }
      : { title: '🩺 Diagnostics', api: api.doctor, rerunLabel: '↻ Run again' }
    setDiagnostic({ title: meta.title, md: '', busy: true, kind, rerunLabel: meta.rerunLabel })
    try {
      const d = await meta.api()
      let md = d.report_md
      if (!md && kind === 'heal') {
        const acts = (d.recent_actions || []).map(a => `- ${a}`).join('\n')
        md = `**${d.message}**${acts ? `\n\n_Recent actions:_\n${acts}` : ''}`
      }
      setDiagnostic({ title: meta.title, md: md || 'No report returned.', busy: false, kind, rerunLabel: meta.rerunLabel })
    } catch (e) {
      setDiagnostic({ title: meta.title, md: `**Failed:** ${e.message}`, busy: false, kind, rerunLabel: meta.rerunLabel })
    }
  }, [])

  // ── Chat ────────────────────────────────────────────────────────────────────
  const handleChat = useCallback(async (message, imageFile = null, docFile = null) => {
    // Slash command: /game /games — open the arcade. No LLM call.
    if (typeof message === 'string' && ['/game', '/games'].includes(message.trim().toLowerCase())) {
      setGamesOpen(true)
      return
    }

    // Slash command: /video — open the video generator. No LLM call.
    if (typeof message === 'string' && ['/video', '/vid'].includes(message.trim().toLowerCase())) {
      setVideoPanelOpen(true)
      return
    }

    // Cloud mode: /cloud on|off — route through OmniRoute (free big models, no strain).
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/cloud')) {
      const arg = message.trim().slice('/cloud'.length).trim().toLowerCase()
      const on = arg !== 'off'
      addMessage('user', `/cloud ${on ? 'on' : 'off'}`)
      try {
        const d = await api.cloudMode(on)
        if (on && !d.ok) { addMessage('assistant', `☁️ ${d.reason}`, { done: true }); return }
        addMessage('assistant', on
          ? '☁️ **Cloud mode ON.** Your messages now use OmniRoute\'s big cloud models — no strain on your laptop. Note: these prompts leave your PC. Turn off: `/cloud off`.'
          : '🔒 **Cloud mode OFF.** Back to the local private brain (ornith) — nothing leaves your PC.', { done: true })
      } catch (e) { addMessage('assistant', `Cloud toggle failed: ${e.message}`) }
      return
    }

    // Supervised gate: /approve <id>, /deny <id>, /pending
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/approve')) {
      const id = message.trim().slice('/approve'.length).trim()
      if (!id) { addMessage('assistant', 'Give the id: `/approve a1b2` (see `/pending`).'); return }
      addMessage('user', `/approve ${id}`)
      try {
        const d = await api.govApproveRun(id)
        addMessage('assistant', d.ok ? `✅ Approved & ran \`${id}\`.\n\n${d.result || ''}` : `Couldn't approve ${id}.`, { done: true })
      } catch (e) { addMessage('assistant', `Approve failed: ${e.message}`) }
      return
    }
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/deny')) {
      const id = message.trim().slice('/deny'.length).trim()
      if (!id) { addMessage('assistant', 'Give the id: `/deny a1b2`.'); return }
      addMessage('user', `/deny ${id}`)
      try { await api.govDeny(id); addMessage('assistant', `🚫 Denied \`${id}\`.`, { done: true }) }
      catch (e) { addMessage('assistant', `Deny failed: ${e.message}`) }
      return
    }
    if (typeof message === 'string' && message.trim().toLowerCase() === '/pending') {
      addMessage('user', '/pending')
      try {
        const d = await api.govPending()
        const list = d.pending || []
        if (!list.length) { addMessage('assistant', 'Nothing waiting for approval.', { done: true }); return }
        const md = list.map(p => `- \`${p.id}\` — **${p.action}**  (\`/approve ${p.id}\` · \`/deny ${p.id}\`)`).join('\n')
        addMessage('assistant', `**Waiting for your approval:**\n${md}`, { done: true })
      } catch (e) { addMessage('assistant', `Couldn't load pending: ${e.message}`) }
      return
    }

    // Slash command: /browser — open the web browser panel. No LLM call.
    if (typeof message === 'string' && ['/browser', '/web'].includes(message.trim().toLowerCase())) {
      setBrowserOpen(true)
      api.browserStatus().then(s => setHasSavedSession(!!s.has_saved_session)).catch(() => {})
      return
    }

    // Slash command: /research <query> — deep multi-source cited research.
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/research')) {
      const q = message.trim().slice('/research'.length).trim()
      if (q) { addMessage('user', `/research ${q}`); startResearch(q) }
      else addMessage('assistant', 'Give me a topic: `/research best local LLMs for a laptop with 8GB VRAM`')
      return
    }

    // Slash commands: /search on|off, /large on|off — toggle reply behaviour.
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/search')) {
      const arg = message.trim().slice('/search'.length).trim().toLowerCase()
      const on = arg !== 'off'
      setForceSearch(on)
      addMessage('assistant', on ? 'Web search **ON** — replies will search the web first. `/search off` to stop.' : 'Web search **OFF**.')
      return
    }
    if (typeof message === 'string' && (message.trim().toLowerCase().startsWith('/large') || message.trim().toLowerCase().startsWith('/forcelarge'))) {
      const arg = message.trim().replace(/^\/(forcelarge|large)/i, '').trim().toLowerCase()
      const on = arg !== 'off'
      setForceLarge(on)
      addMessage('assistant', on ? 'Force-large **ON** — uses the big model for every reply. `/large off` to stop.' : 'Force-large **OFF** — back to auto-routing.')
      return
    }


    // Slash command: /loop <goal> — agent company loops until QA passes.
    if (typeof message === 'string' && message.trim().toLowerCase().startsWith('/loop')) {
      const goal = message.trim().slice(5).trim()
      if (goal) { addMessage('user', `/loop ${goal}`); setAgentTask({ goal, loop: true }) }
      else addMessage('assistant', 'Give me a goal: `/loop build a snake game and make sure it runs`')
      return
    }

    // Slash command: /task <goal> · /team <goal> — run it through the agent company, live.
    if (typeof message === 'string' &&
        (message.trim().toLowerCase().startsWith('/task') || message.trim().toLowerCase().startsWith('/team'))) {
      const goal = message.trim().replace(/^\/(task|team)\s*/i, '').trim()
      if (goal) { addMessage('user', `/task ${goal}`); setAgentTask({ goal, loop: false }) }
      else addMessage('assistant', 'Give me a goal: `/team build a landing page for a coffee shop`')
      return
    }

    // Slash command: /illip [guide] · /guide · /help — the ILLIP tour, instant, no LLM.
    if (typeof message === 'string' &&
        ['/illip', '/illip guide', '/guide', '/help'].includes(message.trim().toLowerCase())) {
      addMessage('user', message.trim())
      addMessage('assistant', ILLIP_GUIDE, { done: true })
      return
    }

    // Slash commands that call a backend route and render its markdown report.
    const reportCommands = [
      { cmd: '/idea', run: (arg) => api.ideaJourney(arg), wait: '💡 Analyzing your idea, searching similar work, building your step plan…', needArg: 'Tell me the idea: `/idea an app that helps farmers detect crop disease from photos`' },
      { cmd: '/stuck', run: (arg) => api.ideaStuck(arg), wait: '🧭 Looking at your tasks and workspace to find your next step…' },
      { cmd: '/opps', run: (arg) => api.ideaOpportunities(arg), wait: '🌱 Searching live opportunities for your field…' },
      { cmd: '/opportunities', run: (arg) => api.ideaOpportunities(arg), wait: '🌱 Searching live opportunities for your field…' },
      { cmd: '/scan', run: (arg) => api.guardianScan(arg), wait: '🛡️ Scanning for malicious signs (heuristics + Windows Defender)…' },
      { cmd: '/getsafe', run: (arg) => api.guardianGetSafe(arg), wait: '🛡️ Checking reputation + building a safe-download guide…', needArg: 'What do you want to download? `/getsafe a free video editor` or `/getsafe repack of <game>`' },
      { cmd: '/gstack', run: (arg) => api.gstack(arg), wait: '🌿 Reading the repo (branch, status, staged changes)…' },
      {
        cmd: '/skills',
        wait: '🧩 Loading the agent-skills directory…',
        run: async (arg) => {
          const d = await api.skillsDirectory(arg.trim(), '')
          const byCat = {}
          for (const s of (d.skills || [])) (byCat[s.category] = byCat[s.category] || []).push(s)
          let md = `**Agent Skills Directory** — ${d.count} of ${d.total} shown${arg.trim() ? ` (category: ${arg.trim()})` : ''}  \n_categories: ${(d.categories || []).join(', ')}_  \n\n`
          for (const cat of Object.keys(byCat).sort()) {
            md += `**${cat}**\n`
            for (const s of byCat[cat]) md += `- [${s.id}](${s.url}) — ${s.description}\n`
            md += '\n'
          }
          md += `\n_${d.note}_  \nSource: ${d.source}\n\nFilter by category: \`/skills web\`, \`/skills security\`, \`/skills data\`…`
          return { report_md: md }
        },
      },
      {
        cmd: '/read',
        wait: '📖 Reading that link (transcript / thread / readme / article)…',
        needArg: 'Paste a URL: `/read https://youtube.com/watch?v=…` (YouTube, GitHub, or any page)',
        run: async (arg) => {
          const d = await api.readUrl(arg)
          if (d.error && !d.text) return { report_md: `**Couldn't read that:** ${d.error}` }
          return { report_md: `**${d.title || d.url}**  \n_source: ${d.source}_\n\n${(d.text || '').slice(0, 6000)}${(d.text || '').length > 6000 ? '\n\n…(truncated)' : ''}` }
        },
      },
      {
        cmd: '/ask',
        wait: '🔎 Searching the live web, reading the top pages, writing a cited answer…',
        needArg: 'Ask anything current: `/ask latest AI model releases this month`',
        run: async (arg) => {
          const d = await api.ask(arg)
          if (d.error || !d.answer) return { report_md: `**Couldn't answer:** ${d.error || 'no sources found. Is Ollama running? Type `illip` to start it.'}` }
          const src = (d.sources || []).map((s, i) => `${i + 1}. [${(s.title || s.url).slice(0, 80)}](${s.url})`).join('\n')
          return { report_md: `${d.answer}\n\n---\n**Sources**\n${src || '_none_'}` }
        },
      },
      {
        cmd: '/sharpen',
        wait: '🪒 Drafting, then critiquing and refining the answer…',
        needArg: 'Ask something: `/sharpen explain how HTTPS keeps data private`',
        run: async (arg) => {
          const d = await api.sharpen(arg)
          const tag = d.improved
            ? `✅ _Sharpened — the critique caught something and the answer was improved (${d.rounds_run} round${d.rounds_run === 1 ? '' : 's'}, brain: ${d.provider || 'local'})._`
            : `ℹ️ _Draft already held up — no changes needed (brain: ${d.provider || 'local'})._`
          return { report_md: `${d.answer}\n\n---\n${tag}` }
        },
      },
      {
        cmd: '/caveman',
        wait: '⚙️ Updating reply style…',
        run: async (arg) => {
          const on = arg.trim().toLowerCase() !== 'off'
          await api.setChatMode('caveman', on)
          return { report_md: on
            ? '🗿 **Caveman mode ON.** ILLIP now replies terse — faster on your hardware. Turn off: `/caveman off`.'
            : '🗿 **Caveman mode OFF.** ILLIP back to normal replies.' }
        },
      },
      {
        cmd: '/ponytail',
        wait: '⚙️ Updating solution style…',
        run: async (arg) => {
          const on = arg.trim().toLowerCase() !== 'off'
          await api.setChatMode('ponytail', on)
          return { report_md: on
            ? '🐴 **Ponytail mode ON.** ILLIP now favours the simplest solution and flags over-engineering. Turn off: `/ponytail off`.'
            : '🐴 **Ponytail mode OFF.**' }
        },
      },
      {
        cmd: '/remind',
        wait: '⏰ Setting reminder…',
        needArg: 'Format: `/remind HH:MM your instruction` — e.g. `/remind 09:00 give me one LeetCode problem and solve it`',
        run: async (arg) => {
          const m = arg.match(/^(\d{1,2}:\d{2})\s+(.+)$/)
          if (!m) return { report_md: "Format: `/remind HH:MM your instruction` — e.g. `/remind 09:00 daily leetcode problem`" }
          return api.createReminder({ instruction: m[2], time_of_day: m[1], project_id: activeProject })
        },
      },
      {
        cmd: '/reminders',
        wait: '⏰ Loading reminders…',
        run: async () => {
          const d = await api.reminders()
          const list = d.reminders || []
          if (!list.length) return { report_md: 'No reminders set. `/remind HH:MM your instruction` to add one.' }
          const lines = list.map(r =>
            `- **${r.time_of_day}** — ${r.instruction} ${r.enabled ? '' : '_(disabled)_'} — \`${r.id}\` (\`/unremind ${r.id}\`)`
          )
          return { report_md: `⏰ **Reminders**\n\n${lines.join('\n')}` }
        },
      },
      {
        cmd: '/unremind',
        wait: '🗑️ Removing reminder…',
        needArg: 'Give the reminder id — see `/reminders` for the list.',
        run: async (arg) => {
          await api.deleteReminder(arg.trim())
          return { report_md: `Deleted reminder \`${arg.trim()}\`.` }
        },
      },
    ]
    if (typeof message === 'string' && message.trim().startsWith('/')) {
      const trimmed = message.trim()
      const rc = reportCommands.find(c => trimmed.toLowerCase() === c.cmd || trimmed.toLowerCase().startsWith(c.cmd + ' '))
      if (rc) {
        const arg = trimmed.slice(rc.cmd.length).trim()
        if (!arg && rc.needArg) { addMessage('assistant', rc.needArg); return }
        addMessage('user', trimmed)
        addMessage('assistant', rc.wait)
        try {
          const d = await rc.run(arg)
          setMessages(prev => prev.slice(0, -1))
          addMessage('assistant', d.report_md || d.detail || 'No report returned.', { done: true })
        } catch (e) {
          setMessages(prev => prev.slice(0, -1))
          addMessage('assistant', `**${rc.cmd} failed:** ${e.message}`)
        }
        return
      }
    }

    // Slash commands: /doctor, /heal — run in the diagnostics overlay, NOT chat.
    const dtrim = typeof message === 'string' ? message.trim().toLowerCase() : ''
    if (dtrim === '/doctor') { runDiagnostic('doctor'); return }
    if (dtrim === '/heal' || dtrim === '/repair') { runDiagnostic('heal'); return }

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
  }, [pinnedModel, forceLarge, forceSearch, activeProject, autoSpeak, addMessage, activeDocument, runDiagnostic])

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

  // ── Delete / edit a sent message ─────────────────────────────────────────────
  const deleteMessage = useCallback((msg) => {
    setMessages(prev => prev.filter(m => m.id !== msg.id))
    // Best-effort disk removal; slash-command outputs aren't on disk — fine.
    api.chatDeleteMessage(msg.role, msg.content).catch(() => {})
  }, [])

  const editMessage = useCallback(async (msg, newText) => {
    if (!newText.trim() || isLoading) return
    // Forget the old message and every reply after it, then resend the new text.
    setMessages(prev => {
      const idx = prev.findIndex(m => m.id === msg.id)
      return idx === -1 ? prev : prev.slice(0, idx)
    })
    try { await api.chatRewind(msg.content) } catch { /* not on disk — fine */ }
    handleChat(newText.trim())
  }, [isLoading]) // eslint-disable-line

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
        api.browserStatus().then(s => setHasSavedSession(!!s.has_saved_session)).catch(() => {})
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

  const clearBrowserSession = useCallback(async () => {
    if (!window.confirm('Clear saved browser login? Next task will run logged out.')) return
    try {
      await api.browserClearSession()
      setHasSavedSession(false)
    } catch {}
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
        isLoading={isLoading}
        onDeleteProject={deleteProject}
        onSwitchModel={switchModel}
        onSwitchProject={(id) => {
          setActiveProject(id)
          loadChatHistory(id)
        }}
        onDismissSuggestion={() => setDismissedSuggestion(true)}
        onNewProject={() => setNewChatChoiceOpen(true)}
        onRefresh={refreshSystem}
        onAutoSpeak={() => setAutoSpeak(p => !p)}
        autoSpeak={autoSpeak}
        chatModes={chatModes}
        onToggleChatMode={toggleChatMode}
      />

      <RamHelper hwLive={hwLive} />

      <div className="app-body">
        <NavRail
          activePanel={activePanel}
          onTogglePanel={togglePanel}
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
          plugins={plugins}
          healthData={healthData}
          govPending={govPending}
          schedulerJobs={schedulerJobs}
          stats={stats}
          onSwitchModel={switchModel}
          onDeleteModel={deleteModel}
          onModelsChanged={loadModels}
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
          activeProject={activeProject}
          projects={projects}
          onSwitchProject={(id) => { setActiveProject(id); loadChatHistory(id) }}
          onDeleteProject={deleteProject}
          onNewChat={() => setNewChatChoiceOpen(true)}
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
          hasSavedSession={hasSavedSession}
          onClearBrowserSession={clearBrowserSession}
          imagePanelOpen={imagePanelOpen}
          videoPanelOpen={videoPanelOpen}
          activeModel={activeModelRef.current}
          onChat={handleChat}
          onStop={stopGeneration}
          onRegenerate={regenerate}
          onDeleteMessage={deleteMessage}
          onEditMessage={editMessage}
          onOpenArtifact={setArtifactHtml}
          artifactHtml={artifactHtml}
          onCloseArtifact={() => setArtifactHtml(null)}
          onOpenGames={() => setGamesOpen(true)}
          onToggleForceLarge={() => setForceLarge(p => !p)}
          onToggleForceSearch={() => setForceSearch(p => !p)}
          chatModes={chatModes}
          onToggleChatMode={toggleChatMode}
          onMic={toggleMic}
          onSetPendingImage={setPendingImage}
          onSetPendingDocument={setPendingDocument}
          onUploadFile={async (file) => {
            const mb = (file.size / 1048576).toFixed(1)
            addMessage('user', `📎 Uploading **${file.name}** (${mb} MB)…`)
            try {
              const d = await api.uploadFile(file, (pct) => {
                setMessages(prev => {
                  const c = [...prev]
                  c[c.length - 1] = { ...c[c.length - 1], content: `📎 Uploading **${file.name}** (${mb} MB)… ${pct}%` }
                  return c
                })
              })
              const ext = d.extracted_count > 0 ? ` — zip extracted: ${d.extracted_count} files` : ''
              setMessages(prev => {
                const c = [...prev]
                c[c.length - 1] = { ...c[c.length - 1], content: `📎 Uploaded **${d.filename}** (${mb} MB)${ext}` }
                return c
              })
              addMessage('assistant', `Got it — **${d.filename}** is in my workspace${ext}. Ask me anything about it.`, { done: true })
            } catch (e) {
              addMessage('assistant', `**Upload failed:** ${e.message}`, { done: true })
            }
          }}
          onStartResearch={startResearch}
          onCloseResearch={() => { setResearchOpen(false); if (researchSSERef.current) researchSSERef.current.close() }}
          onSetResearchDepth={setResearchDepth}
          onOpenBrowser={() => { setBrowserOpen(true); api.browserStatus().then(s => setHasSavedSession(!!s.has_saved_session)).catch(() => {}) }}
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
      {modelsData && !modelsData.models?.length && !wizardDismissed && (
        <FirstRunWizard
          onDone={(installed) => {
            localStorage.setItem('illip_wizard_done', '1')
            setWizardDismissed(true)
            if (installed) loadModels()
          }}
        />
      )}
      {newChatChoiceOpen && (
        <NewChatChoiceDialog
          onClose={() => setNewChatChoiceOpen(false)}
          onPickChat={async () => { setNewChatChoiceOpen(false); await startBlankChat() }}
          onPickProject={() => { setNewChatChoiceOpen(false); setNewProjectOpen(true) }}
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
            setMessages([])
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
      {agentTask && <AgentsRunPanel task={agentTask.goal || agentTask} loop={!!agentTask.loop} onClose={() => setAgentTask(null)} />}

      {diagnostic && (
        <DiagnosticPanel
          title={diagnostic.title}
          md={diagnostic.md}
          busy={diagnostic.busy}
          rerunLabel={diagnostic.rerunLabel}
          onRerun={() => runDiagnostic(diagnostic.kind)}
          onClose={() => setDiagnostic(null)}
        />
      )}

      <Toasts toasts={toasts} onDismiss={(id) => setToasts(prev => prev.filter(t => t.id !== id))} />
    </div>
  )
}
