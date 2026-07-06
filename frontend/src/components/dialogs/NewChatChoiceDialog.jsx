import React from 'react'

export default function NewChatChoiceDialog({ onClose, onPickChat, onPickProject }) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog choice-dialog" onClick={e => e.stopPropagation()}>
        <h3>Start something new</h3>
        <p className="choice-subtitle">What do you want to do?</p>
        <div className="choice-cards">
          <button className="choice-card" onClick={onPickChat}>
            <span className="choice-icon">💬</span>
            <span className="choice-title">Just chat</span>
            <span className="choice-desc">Quick conversation — starts right away, no setup</span>
          </button>
          <button className="choice-card" onClick={onPickProject}>
            <span className="choice-icon">📁</span>
            <span className="choice-title">New project</span>
            <span className="choice-desc">Give it a name — keeps its own chat &amp; memory separate</span>
          </button>
        </div>
        <div className="dialog-btns">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  )
}
