import React, { useState, useEffect } from 'react'

export default function NewProjectDialog({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const create = async () => {
    if (!name.trim()) return
    setLoading(true)
    try { await onCreate(name.trim()) } finally { setLoading(false) }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <h3>New Project</h3>
        <input
          className="dialog-input"
          type="text"
          value={name}
          autoFocus
          onChange={e => setName(e.target.value)}
          placeholder="Project name"
          onKeyDown={e => e.key === 'Enter' && create()}
        />
        <div className="dialog-btns">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={create} disabled={loading || !name.trim()}>Create</button>
        </div>
      </div>
    </div>
  )
}
