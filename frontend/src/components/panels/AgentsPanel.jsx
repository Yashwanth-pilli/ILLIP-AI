import React from 'react'

export default function AgentsPanel({ agents }) {
  const maxTasks = Math.max(1, ...agents.map(a => a.task_count || 0))
  return (
    <div>
      <div style={{fontSize:'11px',color:'#7070a0',marginBottom:'8px'}}>{agents.length} total</div>
      {agents.length === 0 && <p className="status-label">No agents</p>}
      {agents.map(a => {
        const pct = Math.round(((a.task_count || 0) / maxTasks) * 100)
        const lastAct = a.last_activity ? new Date(a.last_activity).toLocaleTimeString() : '—'
        return (
          <div key={a.name || a.agent_type} className="agent-card">
            <div className="agent-card-header">
              <span className={a.is_available ? 'agent-dot-ok' : 'agent-dot-err'}>●</span>
              <span className="agent-card-name">{a.name || a.agent_type}</span>
            </div>
            <div className="agent-card-stats">
              <span>{a.task_count || 0} tasks</span>
              <span>{lastAct}</span>
            </div>
            <div className="agent-perf-bar-wrap">
              <div className="agent-perf-bar" style={{width: `${pct}%`}} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
