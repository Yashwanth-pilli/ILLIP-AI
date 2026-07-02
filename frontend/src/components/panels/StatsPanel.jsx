import React from 'react'

export default function StatsPanel({ data }) {
  if (!data) return <p className="status-label">Loading…</p>
  const { tasks, memory } = data
  return (
    <div className="stats-content">
      <div className="stat-item"><span className="stat-label">Tasks total</span><span className="stat-value">{tasks?.total ?? '—'}</span></div>
      <div className="stat-item"><span className="stat-label">Pending</span><span className="stat-value">{tasks?.pending ?? '—'}</span></div>
      <div className="stat-item"><span className="stat-label">Completed</span><span className="stat-value">{tasks?.completed ?? '—'}</span></div>
      <div className="stat-item"><span className="stat-label">Memory entries</span><span className="stat-value">{memory?.total_entries ?? '—'}</span></div>
    </div>
  )
}
