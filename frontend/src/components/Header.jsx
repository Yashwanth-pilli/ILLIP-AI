import React from 'react'

export default function Header({
  connected, statusText, modelsData, pinnedModel, ghostBadge,
  dismissedSuggestion, projects, activeProject,
  onSwitchModel, onSwitchProject, onDismissSuggestion, onNewProject,
  onRefresh, onAutoSpeak, autoSpeak,
}) {
  const suggestion = !dismissedSuggestion && modelsData?.recommended && modelsData?.active &&
    modelsData.recommended.split(':')[0] !== modelsData.active.split(':')[0]
      ? modelsData : null

  return (
    <>
      <header className="app-header">
        <div className="logo-area">
          <div className="cat-wrap">
            <svg className="cat-svg" viewBox="0 0 56 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <filter id="catGlow">
                  <feGaussianBlur stdDeviation="1.5" result="blur"/>
                  <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
              </defs>
              {/* Body */}
              <ellipse cx="28" cy="26" rx="16" ry="10" fill="#FFD700" filter="url(#catGlow)"/>
              {/* Head */}
              <circle cx="44" cy="18" r="9" fill="#FFD700"/>
              {/* Ears */}
              <polygon points="38,11 41,4 44,11" fill="#FFD700"/>
              <polygon points="44,11 47,4 50,11" fill="#FFD700"/>
              <polygon points="39,11 41,6 43,11" fill="#FF9CC0"/>
              <polygon points="45,11 47,6 49,11" fill="#FF9CC0"/>
              {/* Eyes */}
              <ellipse cx="41" cy="17" rx="2.5" ry="3" fill="#00FF88"/>
              <ellipse cx="47" cy="17" rx="2.5" ry="3" fill="#00FF88"/>
              <ellipse cx="41" cy="18" rx="1" ry="2" fill="#000"/>
              <ellipse cx="47" cy="18" rx="1" ry="2" fill="#000"/>
              <circle cx="41.8" cy="16.5" r=".6" fill="#fff"/>
              <circle cx="47.8" cy="16.5" r=".6" fill="#fff"/>
              {/* Nose + mouth */}
              <polygon points="44,20 42.5,22 45.5,22" fill="#FF6B9D"/>
              <path d="M42.5 22 Q44 24 45.5 22" stroke="#333" strokeWidth=".8" fill="none"/>
              {/* Fangs */}
              <polygon points="43,22 42.3,24.5 44,22" fill="#fff"/>
              <polygon points="45,22 45.7,24.5 44,22" fill="#fff"/>
              {/* Whiskers */}
              <line x1="33" y1="20" x2="40" y2="19" stroke="#fff" strokeWidth=".6" opacity=".8"/>
              <line x1="33" y1="22" x2="40" y2="21.5" stroke="#fff" strokeWidth=".6" opacity=".8"/>
              <line x1="48" y1="19" x2="55" y2="18" stroke="#fff" strokeWidth=".6" opacity=".8"/>
              <line x1="48" y1="21.5" x2="55" y2="21" stroke="#fff" strokeWidth=".6" opacity=".8"/>
              {/* Front raised paw */}
              <ellipse cx="13" cy="22" rx="5" ry="4" fill="#FFD700"/>
              <ellipse cx="12" cy="20" rx="3.5" ry="3" fill="#FFD700"/>
              {/* Back legs */}
              <ellipse cx="16" cy="35" rx="4" ry="3" fill="#e6b800"/>
              <ellipse cx="38" cy="35" rx="4" ry="3" fill="#e6b800"/>
              {/* Tail — high curled */}
              <path d="M12 26 Q2 18 6 10 Q10 4 16 8" stroke="#FFD700" strokeWidth="3.5" fill="none" strokeLinecap="round"/>
              <circle cx="16" cy="8" r="2.5" fill="#FFD700"/>
            </svg>
          </div>
          <div className="brand">
            <span className="brand-name">ILLIP <span className="brand-ai">AI</span></span>
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

          <button className="icon-btn" onClick={onNewProject} title="New project">+</button>
          <button className={`mode-btn refresh-btn`} onClick={onRefresh} title="Clear context">↺ Refresh</button>
          <button
            className={`mode-btn ${autoSpeak ? 'active' : ''}`}
            onClick={onAutoSpeak}
            title="Auto-speak responses"
          >
            {autoSpeak ? '🔊 Speak' : '🔇 Speak'}
          </button>
        </div>

        <div className="header-right">
          <div className="header-status">
            <span className={`status-dot ${connected ? '' : 'offline'}`} />
            <span>{statusText}</span>
          </div>
        </div>
      </header>

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
