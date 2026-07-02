import React, { useState, useEffect } from 'react'
import { api } from '../../api.js'

export default function InstallSkillDialog({ onClose, onInstalled }) {
  const [url, setUrl] = useState('')
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const install = async () => {
    if (!url.trim()) return
    setLoading(true)
    setStatus({ msg: '⏳ Installing…', color: '#64748b' })
    try {
      const d = await api.installSkill(url.trim())
      if (d.installed || d.success) {
        setStatus({ msg: `✅ Installed! ${d.name || ''}`, color: '#22c55e' })
        setTimeout(onInstalled, 1500)
      } else {
        setStatus({ msg: `❌ ${d.error || 'Install failed'}`, color: '#ef4444' })
      }
    } catch (e) {
      setStatus({ msg: `❌ ${e.message}`, color: '#ef4444' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={e => e.stopPropagation()}>
        <h3>Install Skill from URL</h3>
        <input
          className="dialog-input"
          type="text"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://github.com/user/skill-repo"
          onKeyDown={e => e.key === 'Enter' && install()}
        />
        {status && <div style={{fontSize:'13px',marginBottom:'10px',color:status.color}}>{status.msg}</div>}
        <div className="dialog-btns">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={install} disabled={loading}>Install</button>
        </div>
      </div>
    </div>
  )
}
