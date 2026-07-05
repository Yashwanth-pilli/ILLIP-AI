import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../../api.js'

export default function MemoryPanel({ projectId }) {
  const [entries, setEntries] = useState([])
  const [stats, setStats] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (q = '') => {
    setLoading(true)
    try {
      const d = await api.memoryList(projectId, q)
      setEntries(d.entries || [])
      setStats(d.stats || null)
    } catch { setEntries([]) }
    setLoading(false)
  }, [projectId])

  useEffect(() => { load() }, [load])

  const del = async (id) => {
    await api.memoryDelete(id, projectId)
    setEntries(e => e.filter(x => x.id !== id))
  }

  const clearAll = async () => {
    if (!confirm(`Wipe ALL ${entries.length}+ memories for "${projectId}"? Cannot be undone.`)) return
    const d = await api.memoryClear(projectId)
    alert(`Removed ${d.removed} memories.`)
    load()
  }

  return (
    <div>
      <div className="tab-action-row" style={{ display: 'flex', gap: '6px' }}>
        <input
          className="mem-search"
          placeholder="Search memories…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && load(search)}
          style={{ flex: 1, minWidth: 0 }}
        />
        <button className="tab-action-btn" onClick={() => load(search)}>Search</button>
        <button className="tab-action-btn danger" onClick={clearAll} title="Wipe all memories (fixes stale persona)">Clear All</button>
      </div>

      {stats && (
        <p style={{ color: '#64748b', fontSize: '11px', margin: '4px 0 8px' }}>
          {stats.fts_memories} stored · {stats.vector_memories} vectors ·
          semantic {stats.semantic_active ? 'on' : 'off'}
        </p>
      )}

      {loading && <p style={{ color: '#64748b', fontSize: '12px' }}>Loading…</p>}
      {!loading && !entries.length && <p style={{ color: '#64748b', fontSize: '12px' }}>No memories</p>}

      {entries.map(m => (
        <div key={m.id} className="mem-entry">
          <div className="mem-entry-text">{m.text}</div>
          <div className="mem-entry-meta">
            <span>{m.category}{m.ts ? ` · ${new Date(m.ts * 1000).toLocaleDateString()}` : ''}</span>
            <button className="mem-del-btn" onClick={() => del(m.id)} title="Forget this">✕</button>
          </div>
        </div>
      ))}
    </div>
  )
}
