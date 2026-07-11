import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api.js'
import MessageList from './MessageList.jsx'
import ResearchPanel from './ResearchPanel.jsx'
import BrowserPanel from './BrowserPanel.jsx'
import ImagePanel from './ImagePanel.jsx'
import VideoPanel from './VideoPanel.jsx'
import ArtifactPane from './ArtifactPane.jsx'

// Known slash commands — drives the command palette above the input.
// `arg` shows expected input and decides whether accepting adds a trailing
// space (needs an argument) or not (runs on the next Enter).
const SLASH_COMMANDS = [
  { cmd: '/task',      arg: '<goal>',   desc: 'Run a goal through the agent crew (live)' },
  { cmd: '/loop',      arg: '<goal>',   desc: 'Agent crew loops until QA passes' },
  { cmd: '/idea',      arg: '<idea>',   desc: 'Analyze an idea + build a step plan' },
  { cmd: '/stuck',     arg: '',         desc: 'Get your next step from tasks + workspace' },
  { cmd: '/opps',      arg: '',         desc: 'Find live opportunities for your field' },
  { cmd: '/scan',      arg: '[path]',   desc: 'Scan a download for malware signs (safe / unsafe)' },
  { cmd: '/getsafe',   arg: '<name>',   desc: 'How to download + run something safely (before you get it)' },
  { cmd: '/gstack',    arg: '[path]',   desc: 'Git status + a suggested commit message (read-only)' },
  { cmd: '/ask',       arg: '<question>', desc: 'Live web answer with cited sources (Perplexity-style, no API key)' },
  { cmd: '/read',      arg: '<url>',      desc: 'Read any link keyless: YouTube transcript, GitHub, Reddit, article' },
  { cmd: '/skills',    arg: '[category]', desc: 'Browse the agent-skills directory (1,497+ skills, discovery)' },
  { cmd: '/sharpen',   arg: '<question>', desc: 'Answer, then self-critique + refine it (any brain, sharper)' },
  { cmd: '/caveman',   arg: '[off]',    desc: 'Toggle terse replies (faster on local hardware)' },
  { cmd: '/ponytail',  arg: '[off]',    desc: 'Toggle simplest-solution / anti-over-engineering style' },
  { cmd: '/remind',    arg: 'HH:MM …',  desc: 'Set a daily reminder' },
  { cmd: '/reminders', arg: '',         desc: 'List your reminders' },
  { cmd: '/unremind',  arg: '<id>',     desc: 'Delete a reminder by id' },
  { cmd: '/doctor',    arg: '',         desc: 'Run diagnostics (opens a panel, not chat)' },
  { cmd: '/heal',      arg: '',         desc: 'Auto-repair Ollama / model issues' },
  { cmd: '/game',      arg: '',         desc: 'Open the arcade' },
  { cmd: '/guide',     arg: '',         desc: 'Show the ILLIP tour' },
]

export default function ChatMain({
  messages, isLoading, forceLarge, forceSearch, pressureBanner,
  voiceAvailable, isRecording, voiceStatus, autoSpeak, pendingImage, pendingDocument,
  activeDocument, onClearActiveDocument,
  researchOpen, researchDepth, researchSteps, researchAnswer, researchSources, isResearching,
  browserOpen, browserSteps, browserScreen, browserResult, isBrowsing,
  hasSavedSession, onClearBrowserSession,
  imagePanelOpen, videoPanelOpen, activeModel,
  onChat, onStop, onRegenerate, onDeleteMessage, onEditMessage, onOpenArtifact, artifactHtml, onCloseArtifact, onOpenGames,
  onToggleForceLarge, onToggleForceSearch, onMic, onSetPendingImage, onSetPendingDocument, onUploadFile,
  onStartResearch, onCloseResearch, onSetResearchDepth,
  onOpenBrowser, onCloseBrowser, onRunBrowser,
  onOpenImage, onCloseImage, onOpenVideo, onCloseVideo,
  onFeedback, onSpeak,
}) {
  const [inputValue, setInputValue] = useState('')
  const [menuIndex, setMenuIndex] = useState(0)   // highlighted row in the palette
  const [slashDismissed, setSlashDismissed] = useState(false) // Esc / accept hides it
  const inputRef = useRef(null)

  // Slash-command matching for the command palette + input highlight
  const trimmedInput = inputValue.trim()
  const firstWord = trimmedInput.split(/\s+/)[0].toLowerCase()
  const isSlashCommand = trimmedInput.startsWith('/') &&
    SLASH_COMMANDS.some(c => c.cmd === firstWord)
  // While typing a "/word" (no space yet) show every command that prefix-matches.
  const slashMatches = trimmedInput.startsWith('/') && !trimmedInput.includes(' ')
    ? SLASH_COMMANDS.filter(c => c.cmd.startsWith(trimmedInput.toLowerCase()))
    : []
  // Input already IS a full command name → Enter should run it, not re-complete.
  const exactComplete = SLASH_COMMANDS.some(c => c.cmd === trimmedInput.toLowerCase())
  const menuVisible = slashMatches.length > 0 && !slashDismissed
  const selected = slashMatches[Math.min(menuIndex, slashMatches.length - 1)] || null

  // Accept a palette row: fill the command, add a space only if it takes an arg.
  const acceptSlash = (c) => {
    setInputValue(c.arg ? c.cmd + ' ' : c.cmd)
    setSlashDismissed(true)
    inputRef.current?.focus()
  }

  // Voice transcription inserts text
  useEffect(() => {
    const handler = (e) => setInputValue(prev => prev + e.detail)
    window.addEventListener('voice-transcribed', handler)
    return () => window.removeEventListener('voice-transcribed', handler)
  }, [])

  // Focus the chat box on load
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Reset the palette highlight whenever the typed command prefix changes.
  useEffect(() => { setMenuIndex(0) }, [firstWord])

  // Shrink the box back to one line whenever it's cleared (after send, /refresh, etc.)
  useEffect(() => {
    if (inputValue === '' && inputRef.current) {
      inputRef.current.style.height = 'auto'
    }
  }, [inputValue])

  // Type anywhere -> jumps focus into the chat box, like Slack/Discord.
  // Skipped when focus is already in an input/textarea/select (dialogs,
  // other fields) or a modifier key is held (shortcuts, browser hotkeys).
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key.length !== 1) return  // only printable characters
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (document.activeElement?.isContentEditable) return
      inputRef.current?.focus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    const msg = inputValue.trim()
    if (isLoading) return
    if (msg === '!refresh' || msg === '/refresh') { setInputValue(''); return }
    if (pendingDocument) {
      onChat(msg, null, pendingDocument.file)
      onSetPendingDocument(null)
      setInputValue('')
      return
    }
    if (pendingImage) {
      onChat(msg || 'Describe this image in detail.', pendingImage.file)
      onSetPendingImage(null)
      setInputValue('')
      return
    }
    if (!msg) return
    onChat(msg)
    setInputValue('')
  }

  const handleFileSelect = async (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      onSetPendingDocument({ file })
      return
    }
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = ev => onSetPendingImage({ file, dataUrl: ev.target.result })
      reader.readAsDataURL(file)
      return
    }
    // Audio files → transcribe with local Whisper, drop the text into the box.
    const audioExts = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm', '.aac', '.opus']
    if (file.type.startsWith('audio/') || audioExts.some(x => file.name.toLowerCase().endsWith(x))) {
      setInputValue(v => v + `⏳ transcribing ${file.name}…`)
      try {
        const form = new FormData()
        form.append('file', file)
        const d = await api.transcribe(form)
        setInputValue(v => v.replace(`⏳ transcribing ${file.name}…`, d.text || ''))
      } catch {
        setInputValue(v => v.replace(`⏳ transcribing ${file.name}…`, `(could not transcribe ${file.name})`))
      }
      return
    }
    // Anything else — zip, video, csv, exe, whatever, any size → workspace upload
    onUploadFile && onUploadFile(file)
  }

  return (
    <main className="chat-main">
      {pressureBanner && (
        <div className={`pressure-banner ${pressureBanner.cls}`}>
          ⚠ {pressureBanner.text}
        </div>
      )}

      <MessageList
        messages={messages}
        onFeedback={onFeedback}
        onSpeak={onSpeak}
        onRegenerate={onRegenerate}
        onDeleteMessage={onDeleteMessage}
        onEditMessage={onEditMessage}
        onOpenArtifact={onOpenArtifact}
      />

      {artifactHtml != null && (
        <ArtifactPane html={artifactHtml} onClose={onCloseArtifact} />
      )}

      <div className="input-area">
        {/* Pinned document — stays in context for every follow-up until cleared */}
        {activeDocument && (
          <div className="document-preview pinned-document">
            <span style={{fontSize:'16px'}}>📌📄</span>
            <span style={{fontSize:'12px',color:'#cbd5e1'}}>{activeDocument.filename} — in context for follow-ups</span>
            <button className="remove-image-btn" style={{position:'static',marginLeft:'4px'}} onClick={onClearActiveDocument} title="Stop including this document">✕</button>
          </div>
        )}

        {/* Mode buttons */}
        <div className="input-controls">
          <span className="model-badge">{activeModel || 'Auto'}</span>
          <button className={`mode-btn ${forceLarge ? 'active' : ''}`} onClick={onToggleForceLarge}>Force Large</button>
          <button className={`mode-btn ${forceSearch ? 'active' : ''}`} onClick={onToggleForceSearch}>Search</button>
          <button className="mode-btn refresh-btn" onClick={() => onChat('!refresh')} title="Clear context">↺</button>
        </div>

        {/* Action buttons */}
        <div className="action-btns">
          <button
            className="action-btn research"
            onClick={() => onStartResearch(inputValue.trim())}
            disabled={isResearching}
          >Research</button>
          <button
            className="action-btn browser"
            onClick={onOpenBrowser}
          >Browser</button>
          <button
            className="action-btn imggen"
            onClick={onOpenImage}
          >Image</button>
          <button
            className="action-btn vidgen"
            onClick={onOpenVideo}
          >Video</button>
          <button
            className="action-btn game"
            onClick={onOpenGames}
          >Games</button>
          <button
            className="action-btn team"
            onClick={() => {
              const g = inputValue.trim()
              if (g) { onChat('/task ' + g); setInputValue('') }
              else {
                // No goal typed — don't silently do nothing. Prompt for one.
                inputRef.current?.focus()
                setInputValue('build me ')
              }
            }}
            title="Type what to build, then hit Team to run it through the agent crew"
          >Team</button>
        </div>

        {/* Image preview */}
        {pendingImage && (
          <div className="image-preview">
            <img src={pendingImage.dataUrl} alt="preview" style={{maxHeight:'90px',borderRadius:'8px',border:'2px solid #00ffff'}} />
            <button className="remove-image-btn" onClick={() => onSetPendingImage(null)}>✕</button>
          </div>
        )}

        {/* Document (PDF) chip — no image render, just filename */}
        {pendingDocument && (
          <div className="image-preview document-preview">
            <span style={{fontSize:'20px'}}>📄</span>
            <span style={{fontSize:'12px',color:'#cbd5e1'}}>{pendingDocument.file.name}</span>
            <button className="remove-image-btn" onClick={() => onSetPendingDocument(null)}>✕</button>
          </div>
        )}

        {/* Research panel */}
        {researchOpen && (
          <ResearchPanel
            depth={researchDepth}
            steps={researchSteps}
            answer={researchAnswer}
            sources={researchSources}
            isActive={isResearching}
            onClose={onCloseResearch}
            onSetDepth={onSetResearchDepth}
          />
        )}

        {/* Browser panel */}
        {browserOpen && (
          <BrowserPanel
            steps={browserSteps}
            screen={browserScreen}
            result={browserResult}
            isActive={isBrowsing}
            onClose={onCloseBrowser}
            onRun={onRunBrowser}
            defaultTask={inputValue.trim()}
            hasSavedSession={hasSavedSession}
            onClearSession={onClearBrowserSession}
          />
        )}

        {/* Image/Video panels (absolute positioned) */}
        {imagePanelOpen && <ImagePanel onClose={onCloseImage} />}
        {videoPanelOpen && <VideoPanel onClose={onCloseVideo} />}

        {/* Command palette — appears while typing a "/…" command */}
        {menuVisible && (
          <div className="slash-hints" role="listbox">
            <div className="slash-hints-head">
              <span>Commands</span>
              <span className="slash-hints-keys">↑↓ move · ⏎/Tab pick · Esc close</span>
            </div>
            {slashMatches.map((c, i) => (
              <button
                key={c.cmd}
                type="button"
                role="option"
                aria-selected={c === selected}
                className={`slash-hint ${c === selected ? 'selected' : ''}`}
                onMouseEnter={() => setMenuIndex(i)}
                onClick={() => acceptSlash(c)}
              >
                <span className="slash-hint-cmd">{c.cmd}</span>
                {c.arg && <span className="slash-hint-arg">{c.arg}</span>}
                <span className="slash-hint-desc">{c.desc}</span>
              </button>
            ))}
          </div>
        )}

        {/* Chat form */}
        <form className="chat-form" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className={`message-input ${isSlashCommand ? 'slash-active' : ''}`}
            rows={1}
            value={inputValue}
            onChange={e => {
              setInputValue(e.target.value)
              setSlashDismissed(false)   // typing re-opens the palette after Esc/accept
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
            }}
            onKeyDown={e => {
              // Command palette navigation takes priority while it's open, but
              // Enter still runs a fully-typed command (e.g. "/doctor⏎").
              if (menuVisible) {
                if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  setMenuIndex(i => (i + 1) % slashMatches.length); return
                }
                if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  setMenuIndex(i => (i - 1 + slashMatches.length) % slashMatches.length); return
                }
                if (e.key === 'Escape') { e.preventDefault(); setSlashDismissed(true); return }
                if (e.key === 'Tab') { e.preventDefault(); if (selected) acceptSlash(selected); return }
                if (e.key === 'Enter' && !e.shiftKey && !exactComplete) {
                  e.preventDefault(); if (selected) acceptSlash(selected); return
                }
              }
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            placeholder={isLoading ? 'ILLIP is working…' : 'Message ILLIP… (Shift+Enter for a new line)'}
            disabled={isLoading}
          />
          <button
            type="button"
            className={`mic-btn ${isRecording ? 'recording' : ''}`}
            onClick={onMic}
            disabled={!voiceAvailable}
            title={voiceAvailable ? 'Voice input' : 'Voice unavailable'}
          >
            {isRecording ? '⏹' : '🎤'}
          </button>
          <label className="img-btn" title="Attach any file — images, PDFs, zips, anything, any size">
            📎
            <input type="file" style={{display:'none'}} onChange={handleFileSelect} />
          </label>
          {isLoading ? (
            <button type="button" className="send-button stop-button" onClick={onStop}>
              ⏹ Stop
            </button>
          ) : (
            <button type="submit" className="send-button">
              Send ▶
            </button>
          )}
        </form>

        {voiceStatus && (
          <div className={`voice-status ${voiceStatus.type}`}>{voiceStatus.msg}</div>
        )}
      </div>
    </main>
  )
}
