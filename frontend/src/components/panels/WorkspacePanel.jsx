import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api.js'

const STATUS_ICONS = { pending: '○', in_progress: '◐', completed: '●', failed: '✕' }

export default function WorkspacePanel() {
  const [tab, setTab] = useState('overview')
  const [analysis, setAnalysis] = useState(null)
  const [health, setHealth] = useState(null)
  const [tasks, setTasks] = useState([])
  const [files, setFiles] = useState([])
  const [fileView, setFileView] = useState(null)
  const [newTask, setNewTask] = useState('')

  const load = useCallback(async () => {
    try {
      const [a, h, t, f] = await Promise.allSettled([
        api.wsAnalyze(), api.wsHealth(), api.tasksList(), api.wsFiles(),
      ])
      if (a.status === 'fulfilled') setAnalysis(a.value)
      if (h.status === 'fulfilled') setHealth(h.value)
      if (t.status === 'fulfilled') setTasks(t.value.tasks || t.value || [])
      if (f.status === 'fulfilled') setFiles(f.value.files || [])
    } catch { /* panel stays empty */ }
  }, [])

  useEffect(() => { load() }, [load])

  const addTask = async () => {
    const title = newTask.trim()
    if (!title) return
    await api.taskCreate(title)
    setNewTask('')
    load()
  }

  const setTaskStatus = async (id, status) => {
    await api.taskUpdate(id, { status })
    load()
  }

  const openFile = async (name) => {
    try {
      const d = await api.wsFileContent(name)
      setFileView(d)
    } catch { /* unsupported type */ }
  }

  return (
    <div>
      <div className="ws-tabs">
        {['overview', 'tasks', 'files'].map(t => (
          <button key={t} className={`ws-tab ${tab === t ? 'active' : ''}`} onClick={() => { setTab(t); setFileView(null) }}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div>
          {analysis ? (
            <>
              <div className="ws-stat"><b>{analysis.project_type}</b></div>
              <div className="ws-stat">{analysis.total_files} files</div>
              {analysis.detected_features?.length > 0 && (
                <div className="ws-chips">
                  {analysis.detected_features.map(f => <span key={f} className="ws-chip">{f}</span>)}
                </div>
              )}
            </>
          ) : <p className="ws-muted">No workspace analysis</p>}
          {health && (
            <>
              <div className="ws-stat" style={{ marginTop: '10px' }}>
                Health: {health.status === 'healthy' ? '🟢 healthy' : '🟡 needs attention'}
              </div>
              {(health.warnings || []).map((w, i) => <div key={i} className="ws-warn">⚠ {w}</div>)}
            </>
          )}
        </div>
      )}

      {tab === 'tasks' && (
        <div>
          <div className="tab-action-row" style={{ display: 'flex', gap: '6px' }}>
            <input
              className="mem-search" style={{ flex: 1, minWidth: 0 }}
              placeholder="New task…" value={newTask}
              onChange={e => setNewTask(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addTask()}
            />
            <button className="tab-action-btn" onClick={addTask}>Add</button>
          </div>
          {!tasks.length && <p className="ws-muted">No tasks</p>}
          {tasks.map(t => (
            <div key={t.id} className="ws-task">
              <button
                className="ws-task-check"
                title={t.status}
                onClick={() => setTaskStatus(t.id, t.status === 'completed' ? 'pending' : 'completed')}
              >
                {STATUS_ICONS[t.status] || '○'}
              </button>
              <span className={`ws-task-title ${t.status === 'completed' ? 'done' : ''}`}>{t.title}</span>
              <button className="mem-del-btn" onClick={async () => { await api.taskDelete(t.id); load() }}>✕</button>
            </div>
          ))}
        </div>
      )}

      {tab === 'files' && !fileView && (
        <div>
          {!files.length && <p className="ws-muted">Workspace empty — drop files in data/workspaces/</p>}
          {files.map(f => (
            <div key={f.name} className="ws-file" onClick={() => openFile(f.name)}>
              📄 {f.name}
            </div>
          ))}
        </div>
      )}

      {tab === 'files' && fileView && (
        <div>
          <div className="tab-action-row">
            <button className="tab-action-btn" onClick={() => setFileView(null)}>← Back</button>
            <span style={{ fontSize: '12px', marginLeft: '8px' }}>{fileView.name}</span>
          </div>
          <pre className="ws-file-content">{fileView.content}</pre>
        </div>
      )}
    </div>
  )
}
