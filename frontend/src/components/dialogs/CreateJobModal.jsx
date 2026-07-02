import React, { useState, useEffect } from 'react'

const CRON_PRESETS = [
  { label: 'Every hour', secs: 3600 },
  { label: 'Every 6h', secs: 21600 },
  { label: 'Daily', secs: 86400 },
  { label: 'Every 30m', secs: 1800 },
]

export default function CreateJobModal({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [interval, setInterval] = useState(3600)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const create = async () => {
    if (!name.trim() || !prompt.trim()) { alert('Name and prompt required'); return }
    setLoading(true)
    try { await onCreate({ name: name.trim(), prompt: prompt.trim(), interval_s: interval, enabled: true }) }
    finally { setLoading(false) }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" style={{minWidth:'360px'}} onClick={e => e.stopPropagation()}>
        <h3>Create Scheduled Job</h3>
        <input className="dialog-input" type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Job name" />
        <textarea className="dialog-input" rows={3} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Prompt to run…" style={{resize:'vertical'}} />
        <div style={{marginBottom:'10px'}}>
          <label style={{fontSize:'12px',color:'#7070a0',display:'block',marginBottom:'5px'}}>Interval (seconds): {interval}</label>
          <div className="cron-hints">
            {CRON_PRESETS.map(p => (
              <button key={p.secs} className="cron-hint-btn" onClick={() => setInterval(p.secs)}>{p.label}</button>
            ))}
          </div>
          <input className="create-job-field" type="number" value={interval} min={60} onChange={e => setInterval(+e.target.value)} />
        </div>
        <div className="dialog-btns">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" id="createJobBtn" onClick={create} disabled={loading}>Create</button>
        </div>
      </div>
    </div>
  )
}
