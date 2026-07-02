import React, { useState, useEffect } from 'react'
import { api } from '../api.js'

export default function ImagePanel({ onClose }) {
  const [prompt, setPrompt] = useState('')
  const [negPrompt, setNegPrompt] = useState('')
  const [backend, setBackend] = useState('auto')
  const [steps, setSteps] = useState(20)
  const [width, setWidth] = useState(512)
  const [height, setHeight] = useState(512)
  const [result, setResult] = useState(null)
  const [gallery, setGallery] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.imageGallery().then(d => setGallery(d.images || [])).catch(() => {})
  }, [])

  const generate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    try {
      const d = await api.imageGenerate({ prompt, negative_prompt: negPrompt, width, height, steps, backend })
      if (d.ok && d.image_b64) {
        setResult({ src: `data:image/png;base64,${d.image_b64}`, meta: `${d.backend} · ${d.width}×${d.height} · ${d.duration_s}s` })
        api.imageGallery().then(d => setGallery(d.images || [])).catch(() => {})
      } else {
        alert('Generation failed: ' + (d.error || 'Unknown'))
      }
    } catch (e) { alert('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const SIZES = [[512,512,'512²'],[768,512,'768×512'],[512,768,'512×768'],[1024,1024,'1024²']]

  return (
    <div className="image-panel">
      <div className="image-panel-header">
        <span>🎨 Image Generation</span>
        <select className="img-select" value={backend} onChange={e => setBackend(e.target.value)}>
          <option value="auto">Auto</option>
          <option value="comfy">ComfyUI</option>
          <option value="sd_webui">SD WebUI</option>
          <option value="ollama">Ollama</option>
        </select>
        <button className="research-close" onClick={onClose}>✕</button>
      </div>
      <div className="image-gen-form">
        <textarea className="image-prompt-field" rows={2} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Prompt…" />
        <textarea className="image-neg-field" rows={1} value={negPrompt} onChange={e => setNegPrompt(e.target.value)} placeholder="Negative prompt…" />
        <div className="image-size-row">
          {SIZES.map(([w,h,lbl]) => (
            <button key={lbl} className={`size-btn ${width===w&&height===h?'active':''}`} onClick={()=>{setWidth(w);setHeight(h)}}>{lbl}</button>
          ))}
          <span>Steps:</span>
          <input className="steps-input" type="number" value={steps} min={1} max={50} onChange={e => setSteps(+e.target.value)} />
          <button
            id="imageGenRunBtn"
            className="browser-run-btn"
            style={{marginLeft:'auto'}}
            disabled={loading}
            onClick={generate}
          >{loading ? '⏳' : '▶ Generate'}</button>
        </div>
        {result && (
          <div className="image-gen-result">
            <img className="gen-img" src={result.src} alt="generated" />
            <div className="gen-meta">{result.meta}</div>
          </div>
        )}
        {gallery.length > 0 && (
          <div className="image-gallery">
            {gallery.map(img => (
              <div key={img.name} className="gallery-thumb" onClick={() => setResult({ src: img.url, meta: img.name })}>
                <img src={img.url} alt={img.name} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
