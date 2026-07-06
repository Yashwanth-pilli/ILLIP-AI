import React from 'react'

export default function ChatHistoryPanel({ projects, activeProject, onSwitchProject, onDeleteProject, onNewChat, onClose }) {
  const sorted = [...(projects || [])].sort((a, b) =>
    (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || '')
  )

  return (
    <div className="chat-history-panel">
      <button className="new-chat-btn" onClick={() => { onNewChat(); onClose && onClose() }}>
        + New chat
      </button>
      <div className="chat-history-list">
        {sorted.map(p => (
          <div
            key={p.id}
            className={`chat-history-item ${p.id === activeProject ? 'active' : ''}`}
            onClick={() => { onSwitchProject(p.id); onClose && onClose() }}
          >
            <span className="chat-history-name">📁 {p.name}</span>
            {p.id !== 'default' && (
              <button
                className="chat-history-delete"
                onClick={(e) => { e.stopPropagation(); onDeleteProject(p.id) }}
                title="Delete this chat"
              >
                🗑️
              </button>
            )}
          </div>
        ))}
        {!sorted.length && <div className="chat-history-empty">No chats yet.</div>}
      </div>
    </div>
  )
}
