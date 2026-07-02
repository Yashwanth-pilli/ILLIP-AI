import React from 'react'

export default function ResearchPanel({ depth, steps, answer, sources, isActive, onClose, onSetDepth }) {
  const DEPTHS = ['quick', 'standard', 'deep']
  return (
    <div className="research-panel">
      <div className="research-header">
        <span>🔬 Deep Research</span>
        <div className="research-depth-btns">
          {DEPTHS.map(d => (
            <button
              key={d}
              className={`depth-btn ${depth === d ? 'active' : ''}`}
              onClick={() => onSetDepth(d)}
            >{d}</button>
          ))}
        </div>
        <button className="research-close" onClick={onClose}>✕</button>
      </div>

      {steps.length > 0 && (
        <div className="research-steps">
          {steps.map((s, i) => (
            <div key={i} className={`research-step research-step-${s.type}`}>{s.text}</div>
          ))}
        </div>
      )}

      {answer && (
        <div className="research-answer">
          <div dangerouslySetInnerHTML={{ __html: answer.replace(/\n\n/g,'</p><p>').replace(/^/,'<p>').replace(/$/,'</p>') }} />
        </div>
      )}

      {sources?.length > 0 && (
        <div className="research-sources">
          <div className="sources-title">Sources</div>
          {sources.map((s, i) => (
            <a key={i} href={s.url} target="_blank" rel="noreferrer" className="source-chip">
              <span className="source-num">{i + 1}</span>
              <span className="source-title">{s.title || s.url}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
