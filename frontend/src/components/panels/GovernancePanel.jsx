import React from 'react'
import { escapeHtml } from '../../api.js'

export default function GovernancePanel({ pending, onApprove, onDeny }) {
  if (!pending.length) return <p style={{color:'#64748b',fontSize:'12px'}}>No pending approvals</p>
  return (
    <div>
      {pending.map(item => (
        <div key={item.id} className="gov-item">
          <div className="gov-desc">{item.description || item.action || JSON.stringify(item)}</div>
          <div className="gov-btns">
            <button className="gov-approve" onClick={() => onApprove(item.id)}>Approve</button>
            <button className="gov-deny" onClick={() => onDeny(item.id)}>Deny</button>
          </div>
        </div>
      ))}
    </div>
  )
}
