import React from 'react'
import { formatSecs } from '../../api.js'

function MetricBar({ label, value }) {
  const pct = Math.min(100, value || 0)
  const color = pct > 85 ? '#ef4444' : pct > 65 ? '#f59e0b' : undefined
  return (
    <div className="metric-row">
      <span>{label}</span>
      <div className="metric-bar-wrap">
        <div className="metric-bar" style={{width: `${pct}%`, ...(color ? {background: color, boxShadow: `0 0 5px ${color}`} : {})}} />
      </div>
      <span>{pct.toFixed(0)}%</span>
    </div>
  )
}

export default function HealthPanel({ data }) {
  if (!data) return <p className="status-label">Loading…</p>
  const sys = data.system || {}
  return (
    <div>
      <MetricBar label="CPU" value={sys.cpu_pct} />
      <MetricBar label="RAM" value={sys.ram_pct} />
      <div className="metric-row">
        <span>GPU</span>
        <div className="metric-bar-wrap">
          <div className="metric-bar gpu" style={{width:`${Math.min(100,sys.gpu_util_pct||sys.gpu_pct||0)}%`}}/>
        </div>
        <span>{(sys.gpu_util_pct||sys.gpu_pct||0).toFixed(0)}%</span>
      </div>
      <div className="metric-row">
        <span>Disk</span>
        <div className="metric-bar-wrap">
          <div className="metric-bar disk" style={{width:`${Math.min(100,sys.disk_pct||0)}%`}}/>
        </div>
        <span>{(sys.disk_pct||0).toFixed(0)}%</span>
      </div>

      {(data.jobs || []).length > 0 && (
        <div className="health-jobs" style={{marginTop:'10px'}}>
          <div style={{fontSize:'10px',color:'#7070a0',marginBottom:'4px',textTransform:'uppercase',letterSpacing:'1px'}}>Scheduler</div>
          {data.jobs.map(j => (
            <div key={j.id} className={`health-job ${j.enabled ? '' : 'disabled'}`}>
              <span>{j.name}</span>
              <span className="job-next">{j.last_error ? '⚠' : '✓'} {formatSecs(j.next_run_in)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
