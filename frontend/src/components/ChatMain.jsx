import React, { useState, useRef, useEffect } from 'react'
import MessageList from './MessageList.jsx'
import ResearchPanel from './ResearchPanel.jsx'
import BrowserPanel from './BrowserPanel.jsx'
import ImagePanel from './ImagePanel.jsx'
import VideoPanel from './VideoPanel.jsx'

export default function ChatMain({
  messages, isLoading, forceLarge, forceSearch, pressureBanner,
  voiceAvailable, isRecording, voiceStatus, autoSpeak, pendingImage, pendingDocument,
  activeDocument, onClearActiveDocument,
  researchOpen, researchDepth, researchSteps, researchAnswer, researchSources, isResearching,
  browserOpen, browserSteps, browserScreen, browserResult, isBrowsing,
  imagePanelOpen, videoPanelOpen, activeModel,
  onChat, onToggleForceLarge, onToggleForceSearch, onMic, onSetPendingImage, onSetPendingDocument,
  onStartResearch, onCloseResearch, onSetResearchDepth,
  onOpenBrowser, onCloseBrowser, onRunBrowser,
  onOpenImage, onCloseImage, onOpenVideo, onCloseVideo,
  onFeedback, onSpeak,
}) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef(null)

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

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      onSetPendingDocument({ file })
      return
    }
    const reader = new FileReader()
    reader.onload = ev => onSetPendingImage({ file, dataUrl: ev.target.result })
    reader.readAsDataURL(file)
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
      />

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
          <span className="model-badge">🤖 {activeModel || 'Auto'}</span>
          <button className={`mode-btn ${forceLarge ? 'active' : ''}`} onClick={onToggleForceLarge}>⚡ Force Large</button>
          <button className={`mode-btn ${forceSearch ? 'active' : ''}`} onClick={onToggleForceSearch}>🔍 Search</button>
          <button className="mode-btn refresh-btn" onClick={() => onChat('!refresh')}>↺</button>
        </div>

        {/* Action buttons */}
        <div className="action-btns">
          <button
            className="action-btn research"
            onClick={() => onStartResearch(inputValue.trim())}
            disabled={isLoading || isResearching}
          >🔍 Research</button>
          <button
            className="action-btn browser"
            onClick={onOpenBrowser}
            disabled={isLoading}
          >🌐 Browser</button>
          <button
            className="action-btn imggen"
            onClick={onOpenImage}
            disabled={isLoading}
          >🎨 Image</button>
          <button
            className="action-btn vidgen"
            onClick={onOpenVideo}
            disabled={isLoading}
          >🎬 Video</button>
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
          />
        )}

        {/* Image/Video panels (absolute positioned) */}
        {imagePanelOpen && <ImagePanel onClose={onCloseImage} />}
        {videoPanelOpen && <VideoPanel onClose={onCloseVideo} />}

        {/* Chat form */}
        <form className="chat-form" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className="message-input"
            rows={1}
            value={inputValue}
            onChange={e => {
              setInputValue(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            placeholder="Message ILLIP AI… (Shift+Enter for a new line)"
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
          <label className="img-btn" title="Attach image or PDF">
            📎
            <input type="file" accept="image/*,application/pdf,.pdf" style={{display:'none'}} onChange={handleFileSelect} />
          </label>
          <button type="submit" className="send-button" disabled={isLoading}>
            {isLoading ? '…' : 'Send ▶'}
          </button>
        </form>

        {voiceStatus && (
          <div className={`voice-status ${voiceStatus.type}`}>{voiceStatus.msg}</div>
        )}
      </div>
    </main>
  )
}
