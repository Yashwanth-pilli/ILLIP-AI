import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function VideoPanel({ onClose }) {
  const [prompt, setPrompt] = useState('')
  const [backend, setBackend] = useState('auto')
  const [frames, setFrames] = useState(16)
  const [fps, setFps] = useState(8)
  const [width, setWidth] = useState(512)
  const [height, setHeight] = useState(320)
  const [result, setResult] = useState(null)
  const [gallery, setGallery] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.videoGallery().then(d => setGallery(d.videos || [])).catch(() => {})
  }, [])

  const generate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    try {
      const d = await api.videoGenerate({ prompt, num_frames: frames, fps, width, height, backend })
      if (d.ok) {
        const mime = d.url?.endsWith('.gif') ? 'image/gif' : 'video/mp4'
        const src = d.video_b64 ? `data:${mime};base64,${d.video_b64}` : d.url
        setResult({ src, meta: `${d.backend} · ${d.frames} frames · ${d.fps}fps · ${d.duration_s}s` })
        api.videoGallery().then(d => setGallery(d.videos || [])).catch(() => {})
      } else {
        alert('Failed: ' + (d.error || 'Unknown'))
      }
    } catch (e) { alert('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const SIZES = [[512,320,'512×320'],[768,432,'768×432'],[1024,576,'1024×576']]

  return (
    <div className="image-panel">
      <div className="image-panel-header">
        <span>🎬 Video Generation</span>
        <select className="img-select" value={backend} onChange={e => setBackend(e.target.value)}>
          <option value="auto">Auto</option>
          <option value="wan">Wan 2.1</option>
          <option value="mochi">Mochi</option>
          <option value="ltx">LTX Video</option>
        </select>
        <button className="research-close" onClick={onClose}>✕</button>
      </div>
      <div className="image-gen-form">
        <textarea className="image-prompt-field" rows={2} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Describe your video…" />
        <div className="image-size-row">
          {SIZES.map(([w,h,lbl]) => (
            <button key={lbl} className={`vsize-btn ${width===w&&height===h?'active':''}`} onClick={()=>{setWidth(w);setHeight(h)}}>{lbl}</button>
          ))}
          <span>Frames:</span>
          <input className="steps-input" type="number" value={frames} min={8} max={64} onChange={e => setFrames(+e.target.value)} />
          <span>FPS:</span>
          <input className="steps-input" type="number" value={fps} min={4} max={24} style={{width:'40px'}} onChange={e => setFps(+e.target.value)} />
          <button className="browser-run-btn" style={{marginLeft:'auto'}} disabled={loading} onClick={generate}>
            {loading ? '⏳' : '▶ Generate'}
          </button>
        </div>
        {result && (
          <div className="image-gen-result">
            {result.src?.includes('.gif') || result.src?.startsWith('data:image') ? (
              <img className="gen-img" src={result.src} alt="generated" />
            ) : (
              <video className="gen-img" src={result.src} controls autoPlay loop style={{maxWidth:'100%'}} />
            )}
            <div className="gen-meta">{result.meta}</div>
          </div>
        )}
        {gallery.length > 0 && (
          <div className="image-gallery">
            {gallery.map(v => (
              <div key={v.name} className="gallery-thumb" onClick={() => setResult({ src: v.url, meta: v.name })} style={{padding:'4px',fontSize:'10px',textAlign:'center'}}>
                🎬 {v.name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
