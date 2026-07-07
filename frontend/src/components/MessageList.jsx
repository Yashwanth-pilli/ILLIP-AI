import React, { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'

const WORKING_LINES = [
  '🧠 Firing up the neurons…',
  '⚡ Thinking really hard (like, forehead-vein hard)…',
  '🔧 Tightening some bolts in my brain…',
  '📚 Flipping through everything I know…',
  '🤔 Doing the smart-people squint…',
  '🚀 Cooking up something good…',
  '🕵️ Connecting the dots…',
  '💭 Almost got it, hang tight…',
  '🎯 Lining up the perfect answer…',
  '☕ Sipping imaginary coffee, working on it…',
]

function ThinkingBubble() {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI(v => (v + 1) % WORKING_LINES.length), 1800)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="message assistant thinking">
      <div className="message-content"><em>{WORKING_LINES[i]}</em></div>
    </div>
  )
}

function Message({ msg, onFeedback, onSpeak, onRegenerate, onDeleteMessage, onEditMessage, isLast }) {
  const [feedbackDone, setFeedbackDone] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')

  if (msg.role === 'thinking') {
    return <ThinkingBubble />
  }

  if (editing) {
    return (
      <div className={`message ${msg.role}`}>
        <div className="message-content" style={{width:'100%'}}>
          <textarea
            className="message-input"
            style={{width:'100%',minHeight:'70px',resize:'vertical'}}
            value={editText}
            onChange={e => setEditText(e.target.value)}
            autoFocus
          />
          <div style={{display:'flex',gap:'8px',marginTop:'6px'}}>
            <button className="feedback-btn" onClick={() => { setEditing(false); onEditMessage(msg, editText) }}>✓ Send edited</button>
            <button className="feedback-btn" onClick={() => setEditing(false)}>✕ Cancel</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`message ${msg.role}`}>
      <div className="message-content">
        {msg.routing && (
          <span className="routing-badge">{msg.routing._badge}</span>
        )}
        {msg._pending && !msg.content && (
          <span style={{color:'#7070a0',fontSize:'12px',fontStyle:'italic'}}>{msg._pending}</span>
        )}
        {msg.content && <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) }} />}
        <span className="msg-actions">
          {msg.role === 'user' && onEditMessage && (
            <button className="msg-action-btn" title="Edit and resend"
              onClick={() => { setEditText(msg.content); setEditing(true) }}>✏️</button>
          )}
          {onDeleteMessage && (
            <button className="msg-action-btn" title="Delete message"
              onClick={() => onDeleteMessage(msg)}>🗑️</button>
          )}
        </span>
      </div>
      {msg.role === 'assistant' && msg.done && !feedbackDone && (
        <div className="feedback-bar">
          <span className="feedback-label">Helpful?</span>
          <button className="feedback-btn" onClick={() => { setFeedbackDone(true); onFeedback(msg.question, msg.content, true) }}>👍</button>
          <button className="feedback-btn" onClick={() => { setFeedbackDone(true); onFeedback(msg.question, msg.content, false) }}>👎</button>
          <button className="speaker-btn" onClick={() => onSpeak(msg.content)} title="Read aloud">🔊</button>
          {isLast && onRegenerate && (
            <button className="speaker-btn" onClick={onRegenerate} title="Regenerate response">↻</button>
          )}
        </div>
      )}
      {feedbackDone && (
        <div className="feedback-bar"><span className="feedback-label" style={{color:'#22c55e'}}>✓ Saved</span></div>
      )}
    </div>
  )
}

export default function MessageList({ messages, onFeedback, onSpeak, onRegenerate, onDeleteMessage, onEditMessage, onOpenArtifact }) {
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Event delegation: copy + preview code blocks. One handler for all blocks.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onClick = (e) => {
      const previewBtn = e.target.closest('.preview-btn')
      if (previewBtn) {
        const code = previewBtn.closest('.code-block')?.querySelector('code')
        if (code && onOpenArtifact) onOpenArtifact(code.innerText)
        return
      }
      const btn = e.target.closest('.copy-btn')
      if (!btn) return
      const code = btn.closest('.code-block')?.querySelector('code')
      if (!code) return
      navigator.clipboard.writeText(code.innerText).then(() => {
        btn.textContent = 'Copied'
        setTimeout(() => { btn.textContent = 'Copy' }, 1500)
      })
    }
    el.addEventListener('click', onClick)
    return () => el.removeEventListener('click', onClick)
  }, [onOpenArtifact])

  const lastAssistantId = [...messages].reverse().find(m => m.role === 'assistant' && m.done)?.id

  return (
    <div className="messages" ref={containerRef}>
      {messages.length === 0 && (
        <div style={{textAlign:'center',color:'#7070a0',marginTop:'60px',fontSize:'14px'}}>
          <video src="/illip-logo.mp4" poster="/illip-logo.png" autoPlay loop muted playsInline
            style={{width:'96px',height:'96px',borderRadius:'50%',marginBottom:'12px',objectFit:'cover'}} />
          <div>ILLIP — Local · Private · Yours</div>
          <div style={{fontSize:'12px',marginTop:'6px',color:'#4a4a6a'}}>Ask anything. Your data never leaves your device.</div>
          <div style={{fontSize:'11px',marginTop:'10px',color:'#4a4a6a'}}>Tip: <code>/idea &lt;your idea&gt;</code> · <code>/stuck</code> · <code>/opps</code> · <code>/scan &lt;file&gt;</code> · <code>/task &lt;goal&gt;</code> · <code>/doctor</code></div>
        </div>
      )}
      {messages.map(msg => (
        <Message key={msg.id} msg={msg} onFeedback={onFeedback} onSpeak={onSpeak}
          onRegenerate={onRegenerate} onDeleteMessage={onDeleteMessage} onEditMessage={onEditMessage}
          isLast={msg.id === lastAssistantId} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
