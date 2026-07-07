import React, { useState } from 'react'

function SafetyBadge({ hwLive }) {
  if (!hwLive || hwLive.gpu_temp_c == null) return null
  const temp = hwLive.gpu_temp_c
  const pressure = hwLive.pressure || 'low'
  // Map pressure → colour + label. Temps here run ~40-55°C; 85°C is the hard limit.
  const map = {
    low:      { cls: 'safe',    dot: '🟢', label: 'Safe' },
    medium:   { cls: 'warm',    dot: '🟡', label: 'Busy' },
    high:     { cls: 'warm',    dot: '🟡', label: 'Warm' },
    critical: { cls: 'hot',     dot: '🔴', label: 'Cooling' },
  }
  const s = map[pressure] || map.low
  const ramPct = hwLive.ram_percent || 0
  // RAM starvation is the #1 "why is ILLIP suddenly slow" cause — when other
  // apps eat RAM, Windows swaps and token generation crawls. Say it plainly.
  if (ramPct >= 90) {
    return (
      <span
        className="safety-badge warm"
        title={`Your PC's RAM is ${ramPct.toFixed(0)}% full — other apps (browser tabs, etc.) are squeezing ILLIP, so replies get slow. Close some apps to speed it up. GPU is fine: ${temp.toFixed(0)}°C.`}
      >
        🟡 RAM {ramPct.toFixed(0)}% · close apps
      </span>
    )
  }
  const title = temp > 0
    ? `GPU ${temp.toFixed(0)}°C · limit 85°C · ${s.label}. ILLIP auto-throttles before it ever gets hot.`
    : `${s.label} · running on CPU`
  return (
    <span className={`safety-badge ${s.cls}`} title={title}>
      {s.dot} {temp > 0 ? `${temp.toFixed(0)}°C` : 'CPU'} · {s.label}
    </span>
  )
}

export default function Header({
  connected, statusText, modelsData, pinnedModel, ghostBadge,
  dismissedSuggestion, projects, activeProject, hwLive, isLoading,
  onSwitchModel, onSwitchProject, onDismissSuggestion, onNewProject,
  onRefresh, onAutoSpeak, autoSpeak, onDeleteProject,
  chatModes = {}, onToggleChatMode,
}) {
  const pressure = hwLive?.pressure || 'low'
  const catClass = `cat-wrap pressure-${pressure}${isLoading ? ' thinking' : ''}`
  const [logoBig, setLogoBig] = useState(false)
  const suggestion = !dismissedSuggestion && modelsData?.recommended && modelsData?.active &&
    modelsData.recommended.split(':')[0] !== modelsData.active.split(':')[0]
      ? modelsData : null

  return (
    <>
      <header className="app-header">
        <div className="logo-area">
          <div
            className={catClass}
            title={isLoading ? 'ILLIP is thinking...' : 'Click to see the ILLIP emblem'}
            onClick={() => setLogoBig(true)}
          >
            <img className="cat-logo" src="/illip-logo.png" alt="ILLIP" />
          </div>
          <div className="brand">
            <span className="brand-name">ILLIP</span>
            <span className="brand-sub">Local · Private · Yours</span>
          </div>
        </div>

        <div className="header-controls">
          <div className="header-model-group">
            <select
              className="model-select-header"
              value={pinnedModel || ''}
              onChange={e => onSwitchModel(e.target.value || null)}
            >
              <option value="">🤖 Auto</option>
              {(modelsData?.models || []).map(m => (
                <option key={m.name} value={m.name}>
                  {m.name}{m.is_recommended ? ' ⭐' : ''}{pinnedModel === m.name ? ' 📌' : ''}
                </option>
              ))}
            </select>
            {ghostBadge.text && (
              <span className={`ghost-badge ${ghostBadge.cls}`}>{ghostBadge.text}</span>
            )}
          </div>

          <select
            className="project-select"
            value={activeProject}
            onChange={e => onSwitchProject(e.target.value)}
          >
            {projects.map(p => (
              <option key={p.id} value={p.id}>📁 {p.name}</option>
            ))}
            {!projects.length && <option value="default">📁 Default</option>}
          </select>

          <button className="icon-btn" onClick={onNewProject} title="New space">+</button>
          {activeProject !== 'default' && (
            <button className="icon-btn" onClick={() => onDeleteProject(activeProject)} title="Delete this space">🗑️</button>
          )}
          <button className={`mode-btn refresh-btn`} onClick={onRefresh} title="Clear context">↺ Refresh</button>
          <button
            className={`mode-btn ${autoSpeak ? 'active' : ''}`}
            onClick={onAutoSpeak}
            title="Auto-speak responses"
          >
            {autoSpeak ? '🔊 Speak' : '🔇 Speak'}
          </button>
          <button
            className={`mode-btn ${chatModes.caveman ? 'active' : ''}`}
            onClick={() => onToggleChatMode && onToggleChatMode('caveman')}
            title="Caveman mode — terse, faster replies on local hardware"
          >
            🗿 Caveman
          </button>
          <button
            className={`mode-btn ${chatModes.ponytail ? 'active' : ''}`}
            onClick={() => onToggleChatMode && onToggleChatMode('ponytail')}
            title="Ponytail mode — simplest solution, flags over-engineering"
          >
            🐴 Ponytail
          </button>
        </div>

        <div className="header-right">
          <SafetyBadge hwLive={hwLive} />
          <div className="header-status">
            <span className={`status-dot ${connected ? '' : 'offline'}`} />
            <span>{statusText}</span>
          </div>
        </div>
      </header>

      {logoBig && (
        <div className="modal-overlay" onClick={() => setLogoBig(false)} title="Click to close">
          <img
            src="/illip-logo.png"
            alt="ILLIP emblem"
            style={{
              maxWidth: 'min(80vw, 560px)', maxHeight: '80vh', borderRadius: '16px',
              boxShadow: '0 0 80px rgba(232,199,102,0.35)', cursor: 'pointer',
            }}
          />
        </div>
      )}

      {suggestion && (
        <div className="model-suggestion">
          <span>💡 {modelsData.hardware_summary} → best match: <strong>{modelsData.recommended}</strong> (using {modelsData.active})</span>
          <button className="suggestion-btn" onClick={() => onSwitchModel(modelsData.recommended)}>
            Switch to {modelsData.recommended}
          </button>
          <button className="suggestion-dismiss" onClick={onDismissSuggestion}>✕</button>
        </div>
      )}
    </>
  )
}
