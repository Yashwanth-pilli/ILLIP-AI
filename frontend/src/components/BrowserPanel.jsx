import React, { useState } from 'react'

export default function BrowserPanel({ steps, screen, result, isActive, onClose, onRun, defaultTask, hasSavedSession, onClearSession }) {
  const [task, setTask] = useState(defaultTask || '')
  const [startUrl, setStartUrl] = useState('')
  const [headless, setHeadless] = useState(true)

  return (
    <div className="browser-panel">
      <div className="browser-header">
        <span>🌐 Browser Agent</span>
        {hasSavedSession && (
          <span className="session-badge" title="Logged-in session saved — future runs stay signed in">
            🔐 Session saved
            <button className="session-clear-btn" onClick={onClearSession} title="Clear saved login">🗑️</button>
          </span>
        )}
        <label className="browser-mode-toggle">
          <input type="checkbox" checked={!headless} onChange={e => setHeadless(!e.target.checked)} />
          <span style={{marginLeft:'4px'}}>Show browser</span>
        </label>
        <button className="research-close" onClick={onClose}>✕</button>
      </div>
      <div className="browser-task-input">
        <input
          className="browser-task-field"
          type="text"
          value={task}
          onChange={e => setTask(e.target.value)}
          placeholder="Task: book a flight, fill this form…"
        />
        <input
          className="browser-url-field"
          type="text"
          value={startUrl}
          onChange={e => setStartUrl(e.target.value)}
          placeholder="Start URL (optional)"
        />
        <button
          className="browser-run-btn"
          disabled={isActive || !task.trim()}
          onClick={() => onRun(task, startUrl, headless)}
        >
          {isActive ? '⏳ Running…' : '▶ Run'}
        </button>
      </div>
      {steps.length > 0 && (
        <div className="browser-steps" style={{maxHeight:'140px',overflowY:'auto',padding:'6px 12px'}}>
          {steps.map((s, i) => (
            <div key={i} className={`research-step ${s.type === 'error' ? 'research-step-error' : s.type === 'done' ? 'research-step-done' : ''}`}>
              {s.text}
            </div>
          ))}
        </div>
      )}
      {screen && (
        <div className="browser-screenshot">
          <img src={`data:image/jpeg;base64,${screen}`} alt="browser" />
        </div>
      )}
      {result && (
        <div className="browser-result">
          <div className="browser-result-text">{result}</div>
        </div>
      )}
    </div>
  )
}
