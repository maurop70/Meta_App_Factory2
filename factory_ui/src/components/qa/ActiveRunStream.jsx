import { memo, useState } from 'react'

// ── SCREENSHOT MODAL ────────────────────────────────────────
function ScreenshotModal({ src, onClose }) {
  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.85)',
          zIndex: 9998,
          backdropFilter: 'blur(4px)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          top: '50%', left: '50%',
          transform: 'translate(-50%,-50%)',
          zIndex: 10000,
          maxWidth: '90vw', maxHeight: '90vh',
          background: 'rgba(15,23,42,0.98)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 24px 64px rgba(0,0,0,0.7)',
        }}
      >
        <img
          src={src}
          alt="Screenshot"
          style={{ display: 'block', maxWidth: '85vw', maxHeight: '80vh', objectFit: 'contain' }}
        />
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: 10, right: 12,
            background: 'rgba(239,68,68,0.8)',
            border: 'none', borderRadius: 6,
            color: '#fff', fontWeight: 700,
            fontSize: 14, padding: '4px 10px',
            cursor: 'pointer',
          }}
        >
          ✕ Close
        </button>
      </div>
    </>
  )
}

// ── TEST ROW ────────────────────────────────────────────────
function TestRow({ result }) {
  const [modalSrc, setModalSrc] = useState(null)
  const { name, status, duration_ms, error, screenshot } = result

  const statusIcon = {
    pass:    <span style={{ color: '#10b981', fontSize: 16 }}>✅</span>,
    fail:    <span style={{ color: '#ef4444', fontSize: 16 }}>❌</span>,
    running: <span style={{ color: '#f59e0b', fontSize: 16, animation: 'qa-pulse 1.2s infinite' }}>⏳</span>,
    pending: <span style={{ color: '#64748b', fontSize: 16 }}>○</span>,
  }[status] || <span style={{ color: '#64748b', fontSize: 16 }}>○</span>

  return (
    <div style={{ marginBottom: 2 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 12px',
        background: status === 'fail'
          ? 'rgba(239,68,68,0.06)'
          : status === 'pass'
          ? 'rgba(16,185,129,0.04)'
          : 'rgba(255,255,255,0.02)',
        borderRadius: 8,
        border: `1px solid ${status === 'fail'
          ? 'rgba(239,68,68,0.2)'
          : status === 'pass'
          ? 'rgba(16,185,129,0.15)'
          : 'rgba(255,255,255,0.05)'}`,
      }}>
        {statusIcon}
        <span style={{ flex: 1, fontSize: 13, color: '#e2e8f0' }}>{name}</span>
        {duration_ms != null && (
          <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
            {duration_ms}ms
          </span>
        )}
      </div>

      {status === 'fail' && (
        <div style={{
          marginLeft: 24, marginTop: 2, marginBottom: 4,
          padding: '8px 12px',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.15)',
          borderRadius: '0 0 8px 8px',
          fontSize: 12,
        }}>
          <span style={{ color: '#f87171' }}>Error: {error}</span>
          {screenshot && (
            <div style={{ marginTop: 6 }}>
              <img
                src={`/api/qa-lab/screenshot/${screenshot}`}
                alt="Failure screenshot"
                onClick={() => setModalSrc(`/api/qa-lab/screenshot/${screenshot}`)}
                style={{
                  width: 80, height: 50, objectFit: 'cover',
                  borderRadius: 4, cursor: 'pointer',
                  border: '1px solid rgba(239,68,68,0.3)',
                }}
                title="Click to expand"
              />
            </div>
          )}
        </div>
      )}

      {modalSrc && <ScreenshotModal src={modalSrc} onClose={() => setModalSrc(null)} />}
    </div>
  )
}

// ── ACTIVE RUN STREAM ───────────────────────────────────────
const ActiveRunStream = memo(function ActiveRunStream({
  testResults,
  cycle,
  maxCycles,
  currentTest,
  passed,
  failed,
  totalTests,
  status,
}) {
  const completed = passed + failed
  const pct = totalTests > 0 ? Math.round((completed / totalTests) * 100) : 0
  const isFixing = status === 'running' && cycle > 1
  const isRunning = status === 'running'

  const statusLabel = {
    running: isFixing ? `🔧 Fixing — Cycle ${cycle}/${maxCycles}` : '▶ Running',
    complete: '✅ Complete',
    escalate: '⚠️ Escalation Required',
    failed: '❌ Failed',
  }[status] || status

  const statusColor = {
    running: '#f59e0b',
    complete: '#10b981',
    escalate: '#f59e0b',
    failed: '#ef4444',
  }[status] || '#64748b'

  return (
    <div style={{
      background: 'rgba(15,23,42,0.7)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 12,
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      padding: '20px 24px',
      marginBottom: 20,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
          Live Test Results
        </h3>
        <span style={{
          fontSize: 12, fontWeight: 600, color: statusColor,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          {(isRunning) && (
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#f59e0b',
              display: 'inline-block',
              animation: 'qa-pulse 1.2s infinite',
            }} />
          )}
          {statusLabel}
        </span>
      </div>

      {/* Progress bar */}
      {totalTests > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 11, color: '#64748b', marginBottom: 4,
          }}>
            <span>{completed}/{totalTests} tests</span>
            <span style={{ color: '#10b981' }}>{passed} passed</span>
            {failed > 0 && <span style={{ color: '#ef4444' }}>{failed} failed</span>}
            <span>{pct}%</span>
          </div>
          <div style={{
            height: 6, background: 'rgba(255,255,255,0.06)',
            borderRadius: 6, overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${pct}%`,
              background: 'linear-gradient(90deg, #10b981, #3b82f6)',
              borderRadius: 6,
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Fix cycle indicator */}
      {isFixing && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 12px',
          background: 'rgba(245,158,11,0.08)',
          border: '1px solid rgba(245,158,11,0.2)',
          borderRadius: 8,
          marginBottom: 12,
          fontSize: 12,
          color: '#fbbf24',
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: '#f59e0b',
            animation: 'qa-pulse 1.2s infinite',
          }} />
          🔧 ClaudeAY fixing — Cycle {cycle}/{maxCycles}...
        </div>
      )}

      {/* Current test indicator */}
      {currentTest && isRunning && (
        <div style={{
          fontSize: 12, color: '#94a3b8',
          marginBottom: 10, fontStyle: 'italic',
        }}>
          Testing: {currentTest}
        </div>
      )}

      {/* Test list */}
      <div>
        {testResults.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '32px 0',
            color: '#475569', fontSize: 13,
          }}>
            {isRunning ? 'Initialising test run...' : 'No results yet.'}
          </div>
        )}
        {testResults.map((r, i) => (
          <TestRow key={`${r.name}-${i}`} result={r} />
        ))}
      </div>

      <style>{`
        @keyframes qa-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
})

export default ActiveRunStream
