import { memo, useState, useEffect } from 'react'

const STATUS_COLOR = {
  complete: '#10b981',
  failed:   '#ef4444',
  escalate: '#f59e0b',
  running:  '#3b82f6',
}

const STATUS_ICON = {
  complete: '✅',
  failed:   '❌',
  escalate: '⚠️',
  running:  '▶',
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso.slice(0, 16).replace('T', ' ') }
}

// ── HISTORY LEDGER ──────────────────────────────────────────
// Isolated component — fetches its own data on mount, does not re-render
// when an active run is in progress (React.memo ensures this).
const HistoryLedger = memo(function HistoryLedger() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/qa-lab/history')
      .then(r => r.json())
      .then(data => {
        if (!cancelled) {
          setRuns(data.runs || [])
          setLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{
      background: 'rgba(15,23,42,0.7)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 12,
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      padding: '20px 24px',
    }}>
      <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
        📋 Run History
      </h3>

      {loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#475569', fontSize: 13 }}>
          Loading history...
        </div>
      )}

      {error && (
        <div style={{
          padding: '10px 14px', background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8,
          fontSize: 12, color: '#f87171',
        }}>
          Failed to load history: {error}
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#475569', fontSize: 13 }}>
          No runs yet. Start a QA run above.
        </div>
      )}

      {!loading && runs.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{
            width: '100%', borderCollapse: 'collapse',
            fontSize: 12,
          }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                {['Status', 'App', 'Passed', 'Failed', 'Cycles', 'Started'].map(h => (
                  <th key={h} style={{
                    padding: '6px 10px', textAlign: 'left',
                    color: '#64748b', fontWeight: 500,
                    textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.05em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map(run => {
                const color = STATUS_COLOR[run.status] || '#64748b'
                const icon = STATUS_ICON[run.status] || '?'
                return (
                  <tr
                    key={run.run_id}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                    }}
                  >
                    <td style={{ padding: '8px 10px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                        padding: '2px 8px', borderRadius: 6,
                        background: `${color}18`,
                        border: `1px solid ${color}33`,
                        color, fontWeight: 600, fontSize: 11,
                      }}>
                        {icon} {run.status}
                      </span>
                    </td>
                    <td style={{ padding: '8px 10px', color: '#e2e8f0' }}>
                      {run.app_name}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#10b981', fontWeight: 600 }}>
                      {run.passed ?? '—'}
                    </td>
                    <td style={{ padding: '8px 10px', color: run.failed > 0 ? '#ef4444' : '#64748b', fontWeight: 600 }}>
                      {run.failed ?? '—'}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#94a3b8' }}>
                      {run.cycle ?? 1}/{run.max_cycles ?? 5}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#64748b', fontFamily: 'monospace' }}>
                      {formatDate(run.created_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
})

export default HistoryLedger
