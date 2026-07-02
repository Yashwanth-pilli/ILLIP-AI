import React from 'react'

const TIER_COLORS = ['', '#e74c3c', '#f39c12', '#3498db', '#2ecc71']

export default function HardwarePanel({ data, live, onSwitchModel }) {
  if (!data) return <p className="status-label">Loading…</p>
  const tierColor = TIER_COLORS[data.tier] || '#999'

  return (
    <div className="hardware-panel">
      <div className="status-item"><span className="status-label">Tier</span><span className="status-value" style={{color:tierColor}}>T{data.tier} — {data.tier_label}</span></div>
      <div className="status-item"><span className="status-label">RAM</span><span className="status-value">{data.ram_gb}GB ({data.ram_available_gb}GB free)</span></div>
      <div className="status-item"><span className="status-label">GPU</span><span className="status-value">{data.gpu_name}</span></div>
      <div className="status-item"><span className="status-label">VRAM</span><span className="status-value">{data.gpu_vram_gb}GB</span></div>
      <div className="status-item">
        <span className="status-label">Recommended</span>
        <span className="status-value" style={{color:'#7c6ff7',cursor:'pointer'}} onClick={() => onSwitchModel(data.recommended_model)}>
          {data.recommended_model}
        </span>
      </div>
      <div className="status-item"><span className="status-label">Max ctx</span><span className="status-value">{(data.max_context || 0).toLocaleString()} tokens</span></div>
      {(data.warnings || []).map((w, i) => <div key={i} className="hw-warning">⚠ {w}</div>)}

      {live && (
        <>
          <div style={{height:'1px',background:'rgba(0,255,255,.08)',margin:'8px 0'}}/>
          <div className="status-item"><span className="status-label">GPU temp</span><span className="status-value" style={{color:live.gpu_temp_c>75?'#ef4444':'#00FF88'}}>{live.gpu_temp_c}°C · {live.gpu_util_percent}%</span></div>
          <div className="status-item"><span className="status-label">VRAM</span><span className="status-value">{live.vram_used_mb?.toFixed(0)}/{live.vram_total_mb?.toFixed(0)} MB</span></div>
          <div className="status-item"><span className="status-label">CPU</span><span className="status-value">{live.cpu_percent?.toFixed(0)}% · RAM {live.ram_percent?.toFixed(0)}%</span></div>
          <div className="status-item"><span className="status-label">Pressure</span><span className="status-value">{live.pressure}</span></div>
        </>
      )}
    </div>
  )
}
