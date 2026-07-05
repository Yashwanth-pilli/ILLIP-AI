import React from 'react'

const NAV_ITEMS = [
  { id: 'system',      icon: '⚙️',  label: 'System' },
  { id: 'hardware',    icon: '🖥️',  label: 'Hardware' },
  { id: 'models',      icon: '🧠',  label: 'Models' },
  { id: 'ghost',       icon: '👻',  label: 'Ghost Engine' },
  { id: 'workspace',   icon: '🗂️',  label: 'Workspace' },
  { id: 'memory',      icon: '🧿',  label: 'Memory' },
  { id: 'skills',      icon: '🔧',  label: 'Skills' },
  { id: 'agents',      icon: '🤖',  label: 'Agents', badge: 'agentCount' },
  { id: 'health',      icon: '📊',  label: 'Health' },
  { id: 'governance',  icon: '🛡️',  label: 'Governance', badge: 'govCount' },
  { id: 'workflows',   icon: '⚡',  label: 'Workflows' },
  { id: 'scheduler',   icon: '⏰',  label: 'Scheduler' },
  { id: 'plugins',     icon: '🔌',  label: 'Plugins' },
  { id: 'stats',       icon: '📈',  label: 'Stats' },
]

export default function NavRail({ activePanel, onTogglePanel, agentCount, govCount }) {
  const counts = { agentCount, govCount }

  return (
    <nav className="nav-rail">
      {/* Hidden toggle for JS compat */}
      <button id="sidebarToggle" style={{ display: 'none' }} />

      {NAV_ITEMS.map(item => {
        const badgeVal = item.badge ? counts[item.badge] : 0
        return (
          <button
            key={item.id}
            className={`nav-btn ${activePanel === item.id ? 'active' : ''}`}
            data-panel={item.id}
            onClick={() => onTogglePanel(item.id)}
            title={item.label}
          >
            <span>{item.icon}</span>
            {badgeVal > 0 && (
              <span className="nav-badge">{badgeVal}</span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
