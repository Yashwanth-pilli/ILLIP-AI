import React, { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import { api } from '../api.js'

const AGENT_ICON = {
  planner: '🧠', research: '🔍', code: '💻', builder: '🔨', reviewer: '🔎',
  tester: '🧪', writer: '✍️', analyst: '📊', summarizer: '📝', design: '🎨',
  finance: '💰', ceo: '👔', data: '📈', qa: '✅', content: '📰',
}
const ic = (a) => AGENT_ICON[a] || '🤖'

// Suggest a tidy folder name from the task text.
const slugFolder = (t) =>
  (t || 'my-project').toLowerCase().replace(/[^\w\s-]/g, '').trim()
    .split(/\s+/).slice(0, 4).join('-').slice(0, 40) || 'my-project'

// Live view of the agent company working a task. Streams steps over SSE and
// shows each agent thinking → working → done, then the combined result.
export default function AgentsRunPanel({ task, loop = false, onClose }) {
  const [steps, setSteps] = useState([])     // [{agent, text, state}]
  const [plan, setPlan] = useState([])
  const [final, setFinal] = useState(null)
  const [files, setFiles] = useState([])
  const [runId, setRunId] = useState(null)
  const [running, setRunning] = useState(true)
  const [loopInfo, setLoopInfo] = useState(null) // {loop, max, done, feedback}
  // Clarify phase (loop mode): ask questions BEFORE building, like top models do.
  const [questions, setQuestions] = useState(null)   // null=loading, []=none
  const [answers, setAnswers] = useState({})
  const [startTask, setStartTask] = useState(null)
  // Folder phase: ask WHERE to create the work before anything is built.
  const [dest, setDest] = useState(slugFolder(task))
  const [destConfirmed, setDestConfirmed] = useState(false)
  const sseRef = useRef(null)

  const confirmDest = () => {
    setDestConfirmed(true)
    if (!loop) setStartTask(task)   // plain /task: folder chosen -> build now
    // loop mode: the clarify effect below fires once destConfirmed is true
  }

  useEffect(() => {
    if (!loop || !task || !destConfirmed) return
    let alive = true
    api.agentsClarify(task)
      .then(d => { if (alive) setQuestions(d.questions || []) })
      .catch(() => { if (alive) setQuestions([]) })
    return () => { alive = false }
  }, [task, loop, destConfirmed])

  // No questions came back -> start immediately (folder already confirmed)
  useEffect(() => {
    if (loop && destConfirmed && questions !== null && questions.length === 0 && !startTask) setStartTask(task)
  }, [questions, loop, task, startTask, destConfirmed])

  const beginRun = (skip = false) => {
    const qa = skip ? [] : (questions || [])
      .map((q, i) => ({ q, a: (answers[i] || '').trim() }))
      .filter(x => x.a)
    const augmented = qa.length
      ? `${task}\n\nUser clarifications:\n${qa.map(x => `Q: ${x.q}\nA: ${x.a}`).join('\n')}`
      : task
    setStartTask(augmented)
  }

  useEffect(() => {
    if (!startTask) return
    const sse = new EventSource(loop ? api.agentsLoopUrl(startTask, 3, dest) : api.agentsRunUrl(startTask, dest))
    sseRef.current = sse
    sse.onmessage = (e) => {
      let d; try { d = JSON.parse(e.data) } catch { return }
      if (d.type === 'loop_start') {
        setLoopInfo({ loop: d.loop, max: d.max, done: false, feedback: d.feedback })
        if (d.loop > 1) { setSteps([]); setPlan([]); setFinal(null) } // fresh attempt view
      } else if (d.type === 'loop_check') {
        setLoopInfo(prev => ({ loop: d.loop, max: prev?.max || d.loop, done: d.done, feedback: d.feedback }))
        if (!d.done && d.feedback) {
          setSteps(prev => [...prev, { agent: 'reviewer', text: `QA rejected — retrying: ${d.feedback.slice(0, 180)}`, state: 'done' }])
        }
      } else if (d.type === 'loop_end') {
        setLoopInfo(prev => prev ? { ...prev, ended: true, done: d.done } : prev)
      } else if (d.type === 'plan') {
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
  }, [startTask, loop])

  return (
    <div className="agents-run-overlay" onClick={onClose}>
      <div className="agents-run" onClick={e => e.stopPropagation()}>
        <div className="agents-run-head">
          <span>
            {loop ? '🔁' : '🏢'} Agent company working{running ? '…' : ' — done'}
            {loopInfo && ` · loop ${loopInfo.loop}${loopInfo.max ? `/${loopInfo.max}` : ''}`}
            {loopInfo?.ended && (loopInfo.done ? ' · ✅ QA passed' : ' · ⚠ max loops hit')}
          </span>
          <button className="slide-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="agents-run-task">🎯 {task}</div>

        {/* Folder phase — ask WHERE to create the work, before anything is built */}
        {!destConfirmed && (
          <div className="agents-clarify">
            <div className="agents-clarify-label">📁 Which folder should I create this in?</div>
            <div className="agents-clarify-q">
              <input
                className="mem-search"
                value={dest}
                autoFocus
                onChange={e => setDest(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && dest.trim() && confirmDest()}
                placeholder="folder name"
              />
              <div style={{ fontSize: '11px', color: '#7070a0', marginTop: '4px' }}>
                Created at <code>workspace/{slugFolder(dest) || 'my-project'}/</code> — files &amp; folders build one by one inside it.
              </div>
            </div>
            <div className="agents-clarify-btns">
              <button className="tab-action-btn" disabled={!dest.trim()} onClick={confirmDest}>📁 Use this folder</button>
            </div>
          </div>
        )}

        {/* Clarify phase — questions before building */}
        {destConfirmed && loop && !startTask && (
          <div className="agents-clarify">
            {questions === null && <div className="agent-step working"><em>🤔 Thinking about what to ask you…</em></div>}
            {questions !== null && questions.length > 0 && (
              <>
                <div className="agents-clarify-label">Before I start — quick questions (answer any, skip the rest):</div>
                {questions.map((q, i) => (
                  <div key={i} className="agents-clarify-q">
                    <label>{q}</label>
                    <input
                      className="mem-search"
                      value={answers[i] || ''}
                      onChange={e => setAnswers(a => ({ ...a, [i]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && beginRun(false)}
                      placeholder="(optional)"
                    />
                  </div>
                ))}
                <div className="agents-clarify-btns">
                  <button className="tab-action-btn" onClick={() => beginRun(false)}>▶ Start building</button>
                  <button className="tab-action-btn" onClick={() => beginRun(true)}>Skip questions</button>
                </div>
              </>
            )}
          </div>
        )}

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
