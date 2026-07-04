import React from 'react'

// Stops one render crash from blanking the whole app. Shows the error + a
// reload button instead of a white screen.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  componentDidCatch(error, info) {
    console.error('ILLIP UI crash:', error, info)
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{padding:'40px',color:'#e2e8f0',fontFamily:'system-ui',maxWidth:'640px',margin:'0 auto'}}>
          <h2 style={{color:'#ef4444'}}>⚠ Something broke in the UI</h2>
          <p>The chat kept running — this is just the screen. Reload to recover.</p>
          <pre style={{background:'#1a1a2e',padding:'12px',borderRadius:'8px',overflow:'auto',fontSize:'12px'}}>
            {String(this.state.error?.stack || this.state.error)}
          </pre>
          <button onClick={() => window.location.reload()}
            style={{padding:'8px 16px',background:'#00ffff',color:'#000',border:'none',borderRadius:'8px',fontWeight:700,cursor:'pointer'}}>
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
