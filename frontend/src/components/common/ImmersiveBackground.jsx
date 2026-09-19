function ImmersiveBackground() {
  return (
    <div className="immersive-bg" aria-hidden="true">
      <div className="grid-overlay" />
      <div
        className="orb"
        style={{
          top: '-12%',
          left: '68%',
          width: '520px',
          height: '520px',
          background: 'radial-gradient(circle, rgba(34,211,238,0.22), transparent 65%)',
          animation: 'float-slow 12s ease-in-out infinite',
        }}
      />
      <div
        className="orb"
        style={{
          bottom: '-18%',
          left: '-6%',
          width: '620px',
          height: '620px',
          background: 'radial-gradient(circle, rgba(139,92,246,0.24), transparent 65%)',
          animation: 'float-slower 18s ease-in-out infinite',
        }}
      />
      <div
        className="orb"
        style={{
          top: '30%',
          left: '30%',
          width: '420px',
          height: '420px',
          background: 'radial-gradient(circle, rgba(16,185,129,0.1), transparent 65%)',
          animation: 'float-slow 16s ease-in-out infinite reverse',
        }}
      />
    </div>
  )
}

export default ImmersiveBackground