import React from 'react'

// Trimmed to the tabs that matter. Everything else was removed to keep the
// UI simple and neat. Text labels, no emoji symbols.
const NAV_ITEMS = [
  { id: 'chats',  label: 'Chats' },
  { id: 'system', label: 'System & Health' },
  { id: 'models', label: 'Models & Ghost Engine' },
]

export default function NavRail({ activePanel, onTogglePanel }) {
  return (
    <nav className="nav-rail">
      {/* Hidden toggle for JS compat */}
      <button id="sidebarToggle" style={{ display: 'none' }} />

      {NAV_ITEMS.map(item => (
        <button
          key={item.id}
          className={`nav-btn ${activePanel === item.id ? 'active' : ''}`}
          data-panel={item.id}
          onClick={() => onTogglePanel(item.id)}
          title={item.label}
        >
          {item.label}
        </button>
      ))}
    </nav>
  )
}
