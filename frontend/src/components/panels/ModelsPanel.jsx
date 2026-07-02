import React from 'react'

const STRAT_COLORS = { full_gpu: '#22c55e', hybrid: '#f59e0b', cpu_only: '#ef4444' }

export default function ModelsPanel({ data, onSwitch }) {
  if (!data) return <p className="status-label">Loading…</p>
  if (!data.ollama_running) return <p style={{color:'#ef4444'}}>Ollama offline — run: <code>ollama serve</code></p>

  return (
    <div>
      {(data.models || []).map(m => (
        <div key={m.name} className="model-item" onClick={() => onSwitch(m.name)}>
          <div className="model-name">
            {m.name}{m.is_recommended ? ' ⭐' : ''}
            {m.name === data.active ? <span style={{color:'#667eea'}}> (active)</span> : null}
          </div>
          <div className="model-meta">
            <span style={{color: STRAT_COLORS[m.strategy] || '#94a3b8'}}>{m.strategy || 'unknown'}</span>
            <span>{m.size_gb}GB</span>
            {m.vram_used_gb ? <span>{m.vram_used_gb}GB VRAM</span> : null}
          </div>
          {m.warnings?.length ? <div className="model-warn">⚠ {m.warnings[0]}</div> : null}
        </div>
      ))}
      {!data.models?.length && <p>No models. Run: <code>ollama pull qwen2.5:7b</code></p>}
      <div style={{fontSize:'11px',color:'#94a3b8',marginTop:'8px'}}>{data.hardware_summary}</div>
    </div>
  )
}
