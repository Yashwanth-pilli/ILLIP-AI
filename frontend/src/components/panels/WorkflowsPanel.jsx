import React from 'react'
import { formatSecs } from '../../api.js'

export default function WorkflowsPanel({ jobs, onRun, onToggle, onCreate }) {
  return (
    <div>
      <div className="tab-action-row">
        <button className="tab-action-btn" onClick={onCreate}>+ New</button>
      </div>
      {!jobs.length && <p style={{color:'#64748b',fontSize:'12px'}}>No workflows yet.</p>}
      {jobs.map(j => (
        <div key={j.id} className="workflow-item">
          <div className={`workflow-name ${j.enabled ? '' : 'disabled'}`}>{j.name}</div>
          <div className="workflow-meta">every {formatSecs(j.interval_s)} · ran {j.run_count}×{j.last_error ? ' ⚠' : ''}</div>
          <div className="sched-btns">
            <button className="sched-run-btn" onClick={() => onRun(j.id)} title="Run now">▶</button>
            <button className="sched-toggle-btn" onClick={() => onToggle(j.id, !j.enabled)}>
              {j.enabled ? 'Pause' : 'Resume'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
