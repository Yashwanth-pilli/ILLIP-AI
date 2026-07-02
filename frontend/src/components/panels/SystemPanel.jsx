import React from 'react'
import { formatUptime } from '../../api.js'

export default function SystemPanel({ data }) {
  if (!data) return <p className="status-label">Loading…</p>
  return (
    <div className="status-content">
      <div className="status-item"><span className="status-label">Provider</span><span className="status-value">{data.model_provider}</span></div>
      <div className="status-item"><span className="status-label">Model</span><span className="status-value" style={{color:'#00FF88'}}>{data.active_model || 'unknown'}</span></div>
      <div className="status-item"><span className="status-label">DB</span><span className={`status-value ${data.database_connected ? '' : 'error'}`}>{data.database_connected ? '✓ Connected' : '✗ Error'}</span></div>
      <div className="status-item"><span className="status-label">Uptime</span><span className="status-value">{formatUptime(data.uptime_seconds)}</span></div>
      <div className="status-item"><span className="status-label">Tasks</span><span className="status-value">{data.task_count}</span></div>
      <div className="status-item"><span className="status-label">Memory</span><span className="status-value">{data.memory_count}</span></div>
    </div>
  )
}
