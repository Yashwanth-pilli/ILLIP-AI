import React, { useState } from 'react'
import { api } from '../../api.js'

const STRAT_META = {
  full_gpu:   { color: '#00FF88', icon: '⚡', label: 'Full GPU' },
  kv_offload: { color: '#00ffff', icon: '🔀', label: 'KV Offload' },
  hybrid:     { color: '#FFD700', icon: '⚙️',  label: 'Hybrid' },
  cpu_only:   { color: '#ef4444', icon: '🐢', label: 'CPU Only' },
}

function Bar({ value, max, color }) {
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div style={{ background: '#1a1a2e', borderRadius: 4, height: 8, overflow: 'hidden', marginTop: 3 }}>
      <div style={{ width: `${pct}%`, height: '100%', background: color, transition: 'width .4s', boxShadow: `0 0 6px ${color}` }} />
    </div>
  )
}

export default function GhostEnginePanel({ models, activeModel }) {
  const [plans, setPlans] = useState({})
  const [loading, setLoading] = useState({})
  const [expanded, setExpanded] = useState(null)

  const loadPlan = async (modelName) => {
    if (plans[modelName] || loading[modelName]) return
    setLoading(l => ({ ...l, [modelName]: true }))
    try {
      const d = await api.ghostEngine(modelName)
      setPlans(p => ({ ...p, [modelName]: d }))
    } catch {}
    setLoading(l => ({ ...l, [modelName]: false }))
  }

  const toggle = (modelName) => {
    if (expanded === modelName) { setExpanded(null); return }
    setExpanded(modelName)
    loadPlan(modelName)
  }

  const modelList = models?.models || []

  return (
    <div>
      <p style={{ color: '#7070a0', fontSize: 11, marginBottom: 10 }}>
        Ghost Engine maps each model to an optimal GPU/CPU split for your hardware.
      </p>
      {modelList.length === 0 && <p style={{ color: '#7070a0' }}>No models detected — run <code>ollama list</code></p>}
      {modelList.map(m => {
        const plan = plans[m.name]
        const strat = STRAT_META[plan?.strategy || m.strategy] || STRAT_META.hybrid
        const isActive = m.name === activeModel
        const isOpen = expanded === m.name

        return (
          <div key={m.name}
            style={{ marginBottom: 8, background: '#0d0d1a', border: `1px solid ${isActive ? '#00ffff44' : '#1e1e3a'}`, borderRadius: 8, overflow: 'hidden' }}
          >
            <div
              style={{ padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
              onClick={() => toggle(m.name)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: strat.color, fontSize: 14 }}>{strat.icon}</span>
                <span style={{ color: isActive ? '#00ffff' : '#e2e8f0', fontSize: 13, fontWeight: isActive ? 700 : 400 }}>
                  {m.name}
                  {isActive && <span style={{ color: '#00ffff', fontSize: 10, marginLeft: 6 }}>● ACTIVE</span>}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: strat.color }}>{strat.label}</span>
                <span style={{ color: '#4a4a6a', fontSize: 10 }}>{isOpen ? '▲' : '▼'}</span>
              </div>
            </div>

            {isOpen && (
              <div style={{ padding: '8px 12px', borderTop: '1px solid #1e1e3a' }}>
                {loading[m.name] && <p style={{ color: '#7070a0', fontSize: 11 }}>Loading plan…</p>}
                {plan && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 8 }}>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>GPU Layers
                        <div style={{ color: '#00FF88', fontWeight: 700 }}>{plan.gpu_layers} / {plan.total_layers}</div>
                      </div>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>CPU Layers
                        <div style={{ color: '#f59e0b', fontWeight: 700 }}>{plan.cpu_layers}</div>
                      </div>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>VRAM Used
                        <div style={{ color: '#00ffff', fontWeight: 700 }}>{plan.vram_used_gb?.toFixed(2)} GB</div>
                        <Bar value={plan.vram_used_gb || 0} max={8} color="#00ffff" />
                      </div>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>Context
                        <div style={{ color: '#BF00FF', fontWeight: 700 }}>{(plan.context_limit || 0).toLocaleString()} tok</div>
                      </div>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>Threads
                        <div style={{ color: '#e2e8f0', fontWeight: 700 }}>{plan.ollama_options?.num_thread || '?'}</div>
                      </div>
                      <div style={{ fontSize: 11, color: '#7070a0' }}>Feasible
                        <div style={{ color: plan.feasible ? '#00FF88' : '#ef4444', fontWeight: 700 }}>
                          {plan.feasible ? '✓ Yes' : '✗ No'}
                        </div>
                      </div>
                    </div>
                    {plan.draft_model && (
                      <div style={{ fontSize: 11, color: '#7070a0', marginBottom: 6 }}>
                        Speculative draft: <span style={{ color: '#FFD700' }}>{plan.draft_model}</span>
                      </div>
                    )}
                    {(plan.warnings || []).map((w, i) => (
                      <div key={i} style={{ fontSize: 11, color: '#f59e0b', background: '#1a1200', borderRadius: 4, padding: '4px 6px', marginTop: 4 }}>⚠ {w}</div>
                    ))}
                    <div style={{ fontSize: 10, color: '#4a4a6a', marginTop: 6 }}>
                      Strategy: {plan.strategy} · mmap: {plan.ollama_options?.use_mmap ? 'on' : 'off'} · mlock: {plan.ollama_options?.use_mlock ? 'on' : 'off'}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
