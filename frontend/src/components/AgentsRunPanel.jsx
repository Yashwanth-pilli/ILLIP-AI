import React, { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import { api } from '../api.js'

const AGENT_ICON = {
  planner: '🧠', research: '🔍', code: '💻', builder: '🔨', reviewer: '🔎',
  tester: '🧪', writer: '✍️', analyst: '📊', summarizer: '📝', design: '🎨',
  finance: '💰', ceo: '👔', data: '📈', qa: '✅', content: '📰',
}
const ic = (a) => AGENT_ICON[a] || '🤖'

// Live view of the agent company working a task. Streams steps over SSE and
// shows each agent thinking → working → done, then the combined result.
export default function AgentsRunPanel({ task, onClose }) {
  const [steps, setSteps] = useState([])     // [{agent, text, state}]
  const [plan, setPlan] = useState([])
  const [final, setFinal] = useState(null)
  const [files, setFiles] = useState([])
  const [runId, setRunId] = useState(null)
  const [running, setRunning] = useState(true)
  const sseRef = useRef(null)

  useEffect(() => {
    if (!task) return
    const sse = new EventSource(api.agentsRunUrl(task))
    sseRef.current = sse
    sse.onmessage = (e) => {
      let d; try { d = JSON.parse(e.data) } catch { return }
      if (d.type === 'plan') {
        setPlan(d.steps || [])
      } else if (d.type === 'step_start') {
        setSteps(prev => [...prev, { agent: d.agent, text: d.task, state: 'working', idx: d.idx }])
      } else if (d.type === 'step_done') {
        setSteps(prev => {
          const c = [...prev]
          for (let i = c.length - 1; i >= 0; i--) {
            if (c[i].agent === d.agent && c[i].state === 'working') { c[i] = { ...c[i], state: 'done', summary: d.summary }; break }
          }
          return c
        })
      } else if (d.type === 'files') {
        setFiles(prev => [...prev, ...(d.files || [])])
      } else if (d.type === 'final') {
        setFinal(d.result)
        if (d.files) setFiles(d.files)
        if (d.run_id) setRunId(d.run_id)
      } else if (d.type === 'end' || d.type === 'error') {
        if (d.type === 'error') setFinal(prev => prev || `**Error:** ${d.message}`)
        setRunning(false)
        sse.close()
      }
    }
    sse.onerror = () => { setRunning(false); sse.close() }
    return () => sse.close()
  }, [task])

  return (
    <div className="agents-run-overlay" onClick={onClose}>
      <div className="agents-run" onClick={e => e.stopPropagation()}>
        <div className="agents-run-head">
          <span>🏢 Agent company working{running ? '…' : ' — done'}</span>
          <button className="slide-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="agents-run-task">🎯 {task}</div>

        {plan.length > 0 && (
          <div className="agents-plan">
            {plan.map((s, i) => (
              <span key={i} className="agents-plan-chip">{ic(s.agent)} {s.agent}</span>
            ))}
          </div>
        )}

        <div className="agents-steps">
          {steps.map((s, i) => (
            <div key={i} className={`agent-step ${s.state}`}>
              <div className="agent-step-head">
                <span className="agent-step-icon">{ic(s.agent)}</span>
                <strong>{s.agent}</strong>
                <span className="agent-step-state">
                  {s.state === 'working' ? '⚙️ working…' : '✅ done'}
                </span>
              </div>
              <div className="agent-step-task">{s.text}</div>
              {s.summary && <div className="agent-step-summary">{s.summary}</div>}
            </div>
          ))}
          {running && steps.length === 0 && <div className="agent-step working"><em>🧠 Planner is thinking…</em></div>}
        </div>

        {files.length > 0 && (
          <div className="agents-files">
            <div className="agents-files-label">
              📁 Files created ({files.length})
              {runId && (
                <a className="agents-zip-btn" href={`/api/agents/run/${runId}/zip`} download>
                  ⬇ Download all (.zip)
                </a>
              )}
            </div>
            {files.map((f, i) => (
              <div key={i} className="agent-file">
                <span className="agent-file-name">📄 {f.name}</span>
                <span className="agent-file-meta">{f.lang} · {f.bytes}b</span>
                <a className="agent-file-link" href={f.url} target="_blank" rel="noreferrer">view</a>
                <a className="agent-file-link" href={f.url} download={f.name}>download</a>
              </div>
            ))}
          </div>
        )}

        {final && (
          <div className="agents-final">
            <div className="agents-final-label">✨ Result</div>
            <div dangerouslySetInnerHTML={{ __html: marked.parse(final) }} />
          </div>
        )}
      </div>
    </div>
  )
}
