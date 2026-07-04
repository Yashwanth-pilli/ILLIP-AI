import React from 'react'

// Stacked toast notifications (bottom-right). Each auto-dismisses via App timer.
export default function Toasts({ toasts, onDismiss }) {
  if (!toasts.length) return null
  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.kind || 'info'}`} onClick={() => onDismiss(t.id)}>
          <span className="toast-icon">{t.icon || '🔧'}</span>
          <span className="toast-msg">{t.msg}</span>
        </div>
      ))}
    </div>
  )
}
