import { useState } from 'react'

// ── ESCALATION OVERLAY ──────────────────────────────────────
// Only renders when escalation !== null.
// Full-screen overlay prompts user to choose A / B / C.
export default function EscalationOverlay({ escalation, onChoice }) {
  const [chosen, setChosen] = useState(null)

  if (!escalation) return null

  const handleChoice = (choice) => {
    setChosen(choice)
    onChoice(choice)
  }

  const question = escalation.question || 'The automated fix cycle could not resolve all failures. How should ClaudeAY proceed?'
  const options = escalation.options || [
    { key: 'A', label: 'Retry with deeper analysis', desc: 'Allow ClaudeAY to spend more time diagnosing root causes and rewrite the fix.' },
    { key: 'B', label: 'Skip failing tests', desc: 'Mark remaining failures as known issues and complete the run with a partial pass.' },
    { key: 'C', label: 'Abort and escalate to human', desc: 'Stop the run immediately and flag for manual review.' },
  ]

  return (
    <>
      {/* Backdrop */}
      <div style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.8)',
        zIndex: 9998,
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
      }} />

      {/* Card */}
      <div style={{
        position: 'fixed',
        top: '50%', left: '50%',
        transform: 'translate(-50%,-50%)',
        zIndex: 9999,
        width: '100%',
        maxWidth: 560,
        background: 'rgba(15,23,42,0.97)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid rgba(245,158,11,0.3)',
        borderRadius: 16,
        boxShadow: '0 8px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(245,158,11,0.15)',
        padding: '32px 28px',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <span style={{ fontSize: 32 }}>⚠️</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: '#fbbf24' }}>
              Escalation Required
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
              Human decision needed to continue
            </p>
          </div>
        </div>

        <p style={{ fontSize: 14, color: '#94a3b8', marginBottom: 24, lineHeight: 1.6 }}>
          {question}
        </p>

        {/* Choices */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {options.map((opt) => {
            const isSelected = chosen === opt.key
            return (
              <button
                key={opt.key}
                onClick={() => handleChoice(opt.key)}
                disabled={!!chosen}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 14,
                  padding: '14px 16px',
                  borderRadius: 10,
                  border: isSelected
                    ? '1.5px solid #f59e0b'
                    : '1px solid rgba(255,255,255,0.1)',
                  background: isSelected
                    ? 'rgba(245,158,11,0.12)'
                    : 'rgba(255,255,255,0.03)',
                  cursor: chosen ? 'default' : 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s',
                  opacity: chosen && !isSelected ? 0.45 : 1,
                }}
              >
                <span style={{
                  minWidth: 28, height: 28,
                  borderRadius: '50%',
                  background: isSelected ? '#f59e0b' : 'rgba(255,255,255,0.07)',
                  color: isSelected ? '#000' : '#94a3b8',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: 13,
                  flexShrink: 0,
                }}>
                  {opt.key}
                </span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 2 }}>
                    {opt.label}
                  </div>
                  <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
                    {opt.desc}
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {chosen && (
          <div style={{
            marginTop: 18, padding: '10px 14px',
            background: 'rgba(16,185,129,0.1)',
            border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: 8,
            fontSize: 13, color: '#34d399',
          }}>
            ✅ Choice <strong>{chosen}</strong> recorded — processing...
          </div>
        )}
      </div>
    </>
  )
}
