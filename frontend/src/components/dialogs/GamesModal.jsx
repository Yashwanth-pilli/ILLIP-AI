import React, { useState } from 'react'
import { GAMES } from '../../games.js'
import { api } from '../../api.js'

// Pull the first HTML/code block out of an LLM reply; fall back to raw text if
// it already looks like a document.
function extractHtml(text) {
  if (!text) return ''
  const fence = text.match(/```(?:html)?\s*([\s\S]*?)```/i)
  if (fence) return fence[1].trim()
  if (text.includes('<') && text.includes('>')) return text.trim()
  return ''
}

export default function GamesModal({ onClose }) {
  const [active, setActive] = useState(null)      // built-in game
  const [creating, setCreating] = useState(false) // create panel open
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [custom, setCustom] = useState(null)      // generated {name, html}
  const [error, setError] = useState('')

  const generate = async () => {
    const idea = prompt.trim()
    if (!idea || busy) return
    setBusy(true); setError(''); setCustom(null)
    try {
      const ask =
        `You are a game engine. Build a COMPLETE, fully-playable, single-file HTML5 canvas game: ${idea}.\n` +
        `Hard requirements:\n` +
        `- Output ONLY one \`\`\`html code block. No words before or after it.\n` +
        `- Everything inline in ONE file: <style> and <script> included. No external files, no CDN, no network.\n` +
        `- Use <canvas> and requestAnimationFrame. Real game loop, collision, scoring.\n` +
        `- Keyboard controls (arrow keys), on-screen score, and a Restart button.\n` +
        `- Dark neon theme. Must run immediately with zero setup. Finish the whole game, no TODOs, no stubs.`
      const res = await api.chatOnce(ask)
      const html = extractHtml(res.assistant_message)
      if (!html) { setError('The AI did not return a usable game. Try rephrasing.'); return }
      setCustom({ name: `✨ ${idea.slice(0, 40)}`, html })
    } catch (e) {
      setError('Generation failed: ' + e.message)
    } finally {
      setBusy(false)
    }
  }

  const playing = active || custom

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box games-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>🎮 ILLIP Arcade</h3>
          <button className="slide-close-btn" onClick={onClose}>✕</button>
        </div>

        {playing ? (
          <div className="game-play">
            <div className="game-play-head">
              <button className="mode-btn" onClick={() => { setActive(null); setCustom(null) }}>← Arcade</button>
              <span>{playing.name}</span>
            </div>
            <iframe
              className="game-frame"
              title={playing.id || 'custom'}
              sandbox="allow-scripts allow-modals"
              srcDoc={playing.html}
            />
          </div>
        ) : creating ? (
          <div className="create-game">
            <button className="mode-btn" onClick={() => { setCreating(false); setError('') }} style={{alignSelf:'flex-start'}}>← Arcade</button>
            <h4 style={{margin:'10px 0 4px'}}>✨ Create your own game</h4>
            <p style={{fontSize:'12px',color:'#7070a0',margin:'0 0 10px'}}>
              Describe a game and ILLIP builds it, right here. e.g. "a breakout game", "pong vs computer", "memory card matching".
            </p>
            <textarea
              className="create-job-field"
              rows={3}
              placeholder="Describe your game…"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              disabled={busy}
            />
            <button className="browser-run-btn" onClick={generate} disabled={busy || !prompt.trim()}>
              {busy ? '🛠 Building…' : '🚀 Build & Play'}
            </button>
            {error && <p style={{color:'#ef4444',fontSize:'12px',marginTop:'8px'}}>{error}</p>}
            {busy && <p style={{color:'#7070a0',fontSize:'12px',marginTop:'8px'}}>The local model is writing your game — this takes a few seconds.</p>}
          </div>
        ) : (
          <>
            <div className="games-grid">
              {GAMES.map(g => (
                <button key={g.id} className="game-card" onClick={() => setActive(g)}>
                  <div className="game-name">{g.name}</div>
                  <div className="game-desc">{g.desc}</div>
                </button>
              ))}
              <button className="game-card create-card" onClick={() => setCreating(true)}>
                <div className="game-name">➕ Create your own</div>
                <div className="game-desc">Describe any game — ILLIP builds it and you play it here.</div>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
