import React from 'react'
import { formatSecs } from '../../api.js'

export default function SchedulerPanel({ jobs, onRun, onToggle, onCreate }) {
  return (
    <div>
      <div className="tab-action-row">
        <button className="tab-action-btn" onClick={onCreate}>+ New Job</button>
      </div>
      {!jobs.length && <p style={{color:'#64748b',fontSize:'12px'}}>No jobs</p>}
      {jobs.map(j => (
        <div key={j.id} className="sched-job">
          <div className={`sched-job-name ${j.enabled ? '' : 'disabled'}`}>{j.name}</div>
          <div className="sched-job-meta">
            every {formatSecs(j.interval_s)} · ran {j.run_count}×
            {j.last_error ? ` ⚠ ${j.last_error.slice(0, 30)}` : ''}
          </div>
          <div className="sched-btns">
            <button className="sched-run-btn" onClick={() => onRun(j.id)}>▶</button>
            <button className="sched-toggle-btn" onClick={() => onToggle(j.id, !j.enabled)}>
              {j.enabled ? 'Pause' : 'Resume'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
