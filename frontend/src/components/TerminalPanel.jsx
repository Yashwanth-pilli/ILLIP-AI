import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

// A real dev terminal. Runs shell commands on the machine (localhost), scoped to
// a workspace. Dangerous commands ask for confirmation before running.
export default function TerminalPanel({ onClose }) {
  const [lines, setLines] = useState([
    { kind: 'sys', text: 'ILLIP terminal — real shell, scoped to the workspace. Type a command.' },
  ])
  const [cmd, setCmd] = useState('')
  const [cwd, setCwd] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState([])
  const [hIdx, setHIdx] = useState(-1)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => { api.terminalStatus().then(d => setCwd(d.cwd)).catch(() => {}) }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lines])
  useEffect(() => { inputRef.current?.focus() }, [])

  const push = (kind, text) => setLines(prev => [...prev, { kind, text }])

  const run = async (command, confirm = false) => {
    setBusy(true)
    push('cmd', `${cwd} $ ${command}`)
    try {
      const d = await api.terminalRun(command, confirm)
      if (d.needs_confirm) {
        push('warn', `⚠ ${d.warning}`)
        setPendingConfirm(command)
      } else {
        if (d.stdout) push('out', d.stdout.replace(/\n+$/, ''))
        if (d.stderr) push('err', d.stderr.replace(/\n+$/, ''))
        if (!d.stdout && !d.stderr && d.exit_code === 0) push('sys', '(no output)')
        if (d.exit_code !== 0 && d.exit_code !== -1 && !d.stderr) push('err', `exit ${d.exit_code}`)
        if (d.cwd) setCwd(d.cwd)
        setPendingConfirm(null)
      }
    } catch (e) {
      push('err', `error: ${e.message}`)
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }

  const submit = (e) => {
    e.preventDefault()
    const c = cmd.trim()
    if (!c || busy) return
    if (c === 'clear' || c === 'cls') { setLines([]); setCmd(''); return }
    setHistory(prev => [...prev, c]); setHIdx(-1)
    setCmd('')
    run(c)
  }

  const onKey = (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      const i = hIdx < 0 ? history.length - 1 : Math.max(0, hIdx - 1)
      if (history[i] != null) { setHIdx(i); setCmd(history[i]) }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (hIdx < 0) return
      const i = hIdx + 1
      if (i >= history.length) { setHIdx(-1); setCmd('') } else { setHIdx(i); setCmd(history[i]) }
    }
  }

  return (
    <div className="terminal-overlay" onClick={onClose}>
      <div className="terminal" onClick={e => e.stopPropagation()}>
        <div className="terminal-head">
          <span>▶ ILLIP Terminal</span>
          <span className="terminal-cwd">{cwd}</span>
          <button className="slide-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="terminal-body">
          {lines.map((l, i) => <div key={i} className={`term-line ${l.kind}`}>{l.text}</div>)}
          {busy && <div className="term-line sys">⏳ running…</div>}
          {pendingConfirm && (
            <div className="term-confirm">
              <span>Run anyway? This may be destructive.</span>
              <button onClick={() => run(pendingConfirm, true)}>Yes, run it</button>
              <button onClick={() => { setPendingConfirm(null); push('sys', '(cancelled)') }}>Cancel</button>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <form className="terminal-input" onSubmit={submit}>
          <span className="term-prompt">$</span>
          <input
            ref={inputRef}
            value={cmd}
            onChange={e => setCmd(e.target.value)}
            onKeyDown={onKey}
            placeholder="ls, git status, python script.py, npm install…"
            disabled={busy}
            spellCheck={false}
            autoComplete="off"
          />
        </form>
      </div>
    </div>
  )
}
