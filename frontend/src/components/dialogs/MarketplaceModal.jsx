import React, { useEffect } from 'react'
import { MARKETPLACE_PLUGINS } from '../../api.js'

export default function MarketplaceModal({ onClose, onInstall }) {
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>🛒 Plugin Marketplace</h3>
          <button className="slide-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="marketplace-list">
          {MARKETPLACE_PLUGINS.map(p => (
            <div key={p.name} className="marketplace-item">
              <div>
                <strong>{p.display}</strong>
                <span className="plugin-type" style={{marginLeft:'6px'}}>{p.type}</span>
                <p style={{color:'#94a3b8',fontSize:'11px',margin:'2px 0 0'}}>{p.desc}</p>
              </div>
              <button
                className="browser-run-btn"
                style={{fontSize:'11px',padding:'4px 10px'}}
                onClick={() => onInstall(p.spec)}
              >Install</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
