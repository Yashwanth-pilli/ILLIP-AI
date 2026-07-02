import React from 'react'

export default function SkillsPanel({ skills, onInstall }) {
  return (
    <div>
      <div className="tab-action-row">
        <button className="tab-action-btn" onClick={onInstall}>+ Install Skill</button>
      </div>
      {skills.length === 0 && <p className="status-label">No skills loaded</p>}
      {skills.map(s => (
        <div key={s.name} className="skill-item">
          <span className="skill-name">{s.name}</span>
          <span className="skill-desc">{(s.description || '').slice(0, 60)}{(s.description || '').length > 60 ? '…' : ''}</span>
        </div>
      ))}
    </div>
  )
}
