import React from 'react'

export default function PluginsPanel({ plugins, onAdd, onDelete, onMarketplace }) {
  return (
    <div>
      <p className="panel-section-desc">
        Plugins let ILLIP push things out to other apps — post a Slack message, log to Notion,
        open a GitHub issue, trigger an n8n workflow. Nothing here yet unless you add one.
      </p>
      <div className="tab-action-row">
        <button className="tab-action-btn" onClick={onAdd}>+ Add</button>
        <button className="tab-action-btn" onClick={onMarketplace}>🛒 Marketplace (ready-made ones)</button>
      </div>
      {!plugins.length && <p style={{color:'#94a3b8',fontSize:'12px'}}>No plugins yet.</p>}
      {plugins.map(p => (
        <div key={p.name} className="plugin-item">
          <span className="plugin-name">{p.display_name || p.name}</span>
          <span className="plugin-type">{p.plugin_type || 'http'}</span>
          <button className="plugin-del" onClick={() => onDelete(p.name)} title="Remove">✕</button>
        </div>
      ))}
    </div>
  )
}
