import React, { useState } from 'react'

// Live-renders an HTML/SVG artifact in a sandboxed iframe — like Claude artifacts.
// srcDoc + sandbox="allow-scripts": runs the artifact's own JS but blocks it from
// touching ILLIP (no same-origin, no top navigation, no form posts to our API).
export default function ArtifactPane({ html, onClose }) {
  const [view, setView] = useState('preview')  // preview | code

  const isSvg = html.trim().toLowerCase().startsWith('<svg')
  const doc = isSvg
    ? `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;display:grid;place-items:center;min-height:100vh;background:#fff}</style>${html}`
    : html

  const openInTab = () => {
    const blob = new Blob([doc], { type: 'text/html' })
    window.open(URL.createObjectURL(blob), '_blank')
  }

  return (
    <div className="artifact-pane">
      <div className="artifact-head">
        <span className="artifact-title">🖼 Artifact</span>
        <div className="artifact-actions">
          <button className={`mode-btn ${view === 'preview' ? 'active' : ''}`} onClick={() => setView('preview')}>Preview</button>
          <button className={`mode-btn ${view === 'code' ? 'active' : ''}`} onClick={() => setView('code')}>Code</button>
          <button className="mode-btn" onClick={openInTab} title="Open in new tab">⧉</button>
          <button className="mode-btn" onClick={onClose} title="Close">✕</button>
        </div>
      </div>
      {view === 'preview' ? (
        <iframe
          className="artifact-frame"
          title="artifact"
          sandbox="allow-scripts allow-modals allow-popups"
          srcDoc={doc}
        />
      ) : (
        <pre className="artifact-code"><code>{html}</code></pre>
      )}
    </div>
  )
}
