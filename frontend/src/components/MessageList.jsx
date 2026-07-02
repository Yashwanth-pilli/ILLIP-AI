import React, { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'

function Message({ msg, onFeedback, onSpeak }) {
  const [feedbackDone, setFeedbackDone] = useState(false)

  if (msg.role === 'thinking') {
    return (
      <div className="message assistant thinking">
        <div className="message-content"><em>{msg.content}</em></div>
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
      </div>
      {msg.role === 'assistant' && msg.done && !feedbackDone && (
        <div className="feedback-bar">
          <span className="feedback-label">Helpful?</span>
          <button className="feedback-btn" onClick={() => { setFeedbackDone(true); onFeedback(msg.question, msg.content, true) }}>👍</button>
          <button className="feedback-btn" onClick={() => { setFeedbackDone(true); onFeedback(msg.question, msg.content, false) }}>👎</button>
          <button className="speaker-btn" onClick={() => onSpeak(msg.content)} title="Read aloud">🔊</button>
        </div>
      )}
      {feedbackDone && (
        <div className="feedback-bar"><span className="feedback-label" style={{color:'#22c55e'}}>✓ Saved</span></div>
      )}
    </div>
  )
}

export default function MessageList({ messages, onFeedback, onSpeak }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="messages">
      {messages.length === 0 && (
        <div style={{textAlign:'center',color:'#7070a0',marginTop:'60px',fontSize:'14px'}}>
          <div style={{fontSize:'48px',marginBottom:'12px'}}>🐱</div>
          <div>ILLIP AI — Local · Private · Yours</div>
          <div style={{fontSize:'12px',marginTop:'6px',color:'#4a4a6a'}}>Ask anything. Your data never leaves your device.</div>
        </div>
      )}
      {messages.map(msg => (
        <Message key={msg.id} msg={msg} onFeedback={onFeedback} onSpeak={onSpeak} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
