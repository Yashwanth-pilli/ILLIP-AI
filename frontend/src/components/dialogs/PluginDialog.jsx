import React, { useState, useEffect } from 'react'
import { api } from '../../api.js'

export default function PluginDialog({ onClose, onSave }) {
  const [json, setJson] = useState('')
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')

  useEffect(() => {
    api.pluginTemplates().then(d => setTemplates(d.templates || [])).catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleTemplate = (name) => {
    setSelectedTemplate(name)
    const t = templates.find(t => t.name === name)
    if (t) setJson(JSON.stringify(t, null, 2))
  }

  const handleSave = () => {
    let spec
    try { spec = JSON.parse(json) } catch (e) { alert(`Invalid JSON: ${e.message}`); return }
    onSave(spec)
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" style={{minWidth:'420px'}} onClick={e => e.stopPropagation()}>
        <h3>Add Plugin / Connector</h3>
        <select className="dialog-input" value={selectedTemplate} onChange={e => handleTemplate(e.target.value)} style={{marginBottom:'8px'}}>
          <option value="">— Load template —</option>
          {templates.map(t => <option key={t.name} value={t.name}>{t.display_name || t.name}</option>)}
        </select>
        <textarea
          className="dialog-input"
          style={{height:'200px',fontFamily:'monospace',fontSize:'12px',resize:'vertical'}}
          value={json}
          onChange={e => setJson(e.target.value)}
          placeholder='{"name": "my-plugin", "plugin_type": "http", "url": "...", "method": "POST"}'
        />
        <div className="dialog-btns">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  )
}
