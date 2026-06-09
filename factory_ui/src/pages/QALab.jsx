import { useState, useEffect, useRef, useCallback } from 'react'
import ActiveRunStream from '../components/qa/ActiveRunStream'
import EscalationOverlay from '../components/qa/EscalationOverlay'
import HistoryLedger from '../components/qa/HistoryLedger'

// ── QA LAB PAGE (Parent Coordinator) ───────────────────────
// Manages run_id, SSE connection, and passes data down as props.
// Does not re-implement rendering — delegates to child components.
export default function QALab() {
  // ── App selector state ─────────────────────────────────
  const [apps, setApps] = useState([])
  const [selectedApp, setSelectedApp] = useState('')
  const [maxCycles, setMaxCycles] = useState(5)
  const [appsLoading, setAppsLoading] = useState(true)

  // ── Active run state ──────────────────────────────────
  const [runId, setRunId] = useState(null)
  const [runStatus, setRunStatus] = useState('idle')  // idle | running | complete | escalate | failed
  const [testResults, setTestResults] = useState([])
  const [cycle, setCycle] = useState(1)
  const [currentTest, setCurrentTest] = useState(null)
  const [passed, setPassed] = useState(0)
  const [failed, setFailed] = useState(0)
  const [totalTests, setTotalTests] = useState(0)
  const [escalation, setEscalation] = useState(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState(null)

  const esRef = useRef(null)
  const runIdRef = useRef(null)

  // ── Fetch app list ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false
    fetch('/api/qa-lab/apps')
      .then(r => r.json())
      .then(data => {
        if (!cancelled) {
          const list = data.apps || []
          setApps(list)
          if (list.length > 0 && !selectedApp) {
            setSelectedApp(list[0].name)
          }
          setAppsLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setAppsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // ── Close SSE on unmount ───────────────────────────────
  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
    }
  }, [])

  // ── Connect SSE stream ─────────────────────────────────
  const connectStream = useCallback((id) => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    const es = new EventSource(`/api/qa-lab/stream/${id}`)
    esRef.current = es
    runIdRef.current = id

    es.onmessage = (evt) => {
      try {
        const event = JSON.parse(evt.data)
        handleStreamEvent(event)
      } catch { /* ignore malformed */ }
    }

    es.onerror = () => {
      // Reconnect silently after brief pause if run not complete
      if (runIdRef.current) {
        setTimeout(() => {
          if (runIdRef.current) connectStream(runIdRef.current)
        }, 3000)
      }
    }
  }, [])

  const handleStreamEvent = (event) => {
    if (!event || !event.type) return

    switch (event.type) {
      case 'test_result':
        setTestResults(prev => {
          const updated = [...prev]
          const idx = updated.findIndex(r => r.name === event.test_name)
          const result = {
            name: event.test_name,
            status: event.status,
            duration_ms: event.duration_ms,
            error: event.error,
            screenshot: event.screenshot || null,
          }
          if (idx >= 0) updated[idx] = result
          else updated.push(result)
          return updated
        })
        if (event.status === 'pass') setPassed(p => p + 1)
        if (event.status === 'fail') setFailed(f => f + 1)
        break

      case 'run_start':
        setRunStatus('running')
        break

      case 'fix_cycle':
        setCycle(event.cycle || 1)
        break

      case 'fix_applied':
        // Refresh full status from API to get corrected counts
        if (runIdRef.current) {
          fetch(`/api/qa-lab/status/${runIdRef.current}`)
            .then(r => r.json())
            .then(data => {
              setPassed(data.passed || 0)
              setFailed(data.failed || 0)
              setTestResults(data.test_results || [])
            })
            .catch(() => {})
        }
        break

      case 'run_complete':
        setRunStatus(event.status || 'complete')
        setPassed(event.passed || 0)
        setFailed(event.failed || 0)
        runIdRef.current = null
        if (esRef.current) {
          esRef.current.close()
          esRef.current = null
        }
        break

      case 'run_end':
        setRunStatus(event.status || 'complete')
        runIdRef.current = null
        if (esRef.current) {
          esRef.current.close()
          esRef.current = null
        }
        break

      case 'error':
        setRunStatus('failed')
        setError(event.message || 'Unknown error')
        runIdRef.current = null
        if (esRef.current) {
          esRef.current.close()
          esRef.current = null
        }
        break

      case 'escalation':
        setEscalation(event.escalation || { question: event.message })
        setRunStatus('escalate')
        break

      case 'ping':
        // keep-alive — no state update needed
        break

      default:
        break
    }
  }

  // ── Start run ──────────────────────────────────────────
  const startRun = async () => {
    if (!selectedApp || starting) return
    setStarting(true)
    setError(null)
    setTestResults([])
    setCycle(1)
    setPassed(0)
    setFailed(0)
    setTotalTests(0)
    setCurrentTest(null)
    setEscalation(null)
    setRunStatus('running')

    try {
      const res = await fetch('/api/qa-lab/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_name: selectedApp, max_cycles: maxCycles }),
      })
      const data = await res.json()
      const id = data.run_id
      setRunId(id)

      // Fetch initial state to get totalTests once set
      setTimeout(async () => {
        try {
          const st = await fetch(`/api/qa-lab/status/${id}`).then(r => r.json())
          setTotalTests(st.total_tests || 0)
        } catch { /* ignore */ }
      }, 500)

      connectStream(id)
    } catch (err) {
      setError(err.message)
      setRunStatus('failed')
    } finally {
      setStarting(false)
    }
  }

  // Poll total_tests since it's set async in the background thread
  useEffect(() => {
    if (!runId || runStatus !== 'running') return
    const iv = setInterval(async () => {
      try {
        const st = await fetch(`/api/qa-lab/status/${runId}`).then(r => r.json())
        if (st.total_tests > 0) setTotalTests(st.total_tests)
        if (st.current_test) setCurrentTest(st.current_test)
        if (st.cycle) setCycle(st.cycle)
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(iv)
  }, [runId, runStatus])

  // ── Escalation choice ──────────────────────────────────
  const handleEscalationChoice = async (choice) => {
    if (!runId) return
    try {
      await fetch(`/api/qa-lab/escalation/${runId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ choice }),
      })
      setEscalation(null)
      setRunStatus('complete')
    } catch { /* ignore */ }
  }

  const isRunning = runStatus === 'running' || starting

  return (
    <div style={{ padding: '20px 0' }}>
      {/* ── Page Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{
          margin: '0 0 6px',
          fontSize: 22, fontWeight: 700,
          background: 'linear-gradient(135deg, #e2e8f0, #a78bfa)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          🧪 QA Lab
        </h2>
        <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
          Automated end-to-end testing with self-healing fix cycles powered by ClaudeAY
        </p>
      </div>

      {/* ── Control Panel ── */}
      <div style={{
        background: 'rgba(15,23,42,0.7)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        padding: '20px 24px',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        flexWrap: 'wrap',
      }}>
        <div style={{ flex: '1 1 220px' }}>
          <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Target App
          </label>
          <select
            value={selectedApp}
            onChange={e => setSelectedApp(e.target.value)}
            disabled={isRunning}
            style={{
              width: '100%', padding: '8px 12px',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 8, color: '#e2e8f0',
              fontSize: 13, outline: 'none',
              cursor: isRunning ? 'not-allowed' : 'pointer',
            }}
          >
            {appsLoading && <option value="">Loading apps...</option>}
            {!appsLoading && apps.length === 0 && <option value="">No apps registered</option>}
            {apps.map(a => (
              <option key={a.name} value={a.name}>{a.name}</option>
            ))}
          </select>
        </div>

        <div style={{ flex: '0 0 120px' }}>
          <label style={{ fontSize: 11, color: '#64748b', display: 'block', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Max Fix Cycles
          </label>
          <select
            value={maxCycles}
            onChange={e => setMaxCycles(Number(e.target.value))}
            disabled={isRunning}
            style={{
              width: '100%', padding: '8px 12px',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 8, color: '#e2e8f0',
              fontSize: 13, outline: 'none',
            }}
          >
            {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        <div style={{ flex: '0 0 auto', alignSelf: 'flex-end' }}>
          <button
            onClick={startRun}
            disabled={isRunning || !selectedApp}
            style={{
              padding: '9px 22px',
              borderRadius: 8,
              border: 'none',
              background: isRunning
                ? 'rgba(99,102,241,0.3)'
                : 'linear-gradient(135deg, #6366f1, #a78bfa)',
              color: isRunning ? '#94a3b8' : '#fff',
              fontWeight: 600, fontSize: 13,
              cursor: isRunning || !selectedApp ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              boxShadow: isRunning ? 'none' : '0 4px 16px rgba(99,102,241,0.35)',
            }}
          >
            {starting ? '⏳ Starting...' : isRunning ? '▶ Running...' : '🧪 Run QA'}
          </button>
        </div>

        {error && (
          <div style={{
            flex: '1 1 100%',
            padding: '8px 12px',
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 8, fontSize: 12, color: '#f87171',
          }}>
            ❌ {error}
          </div>
        )}

        {runStatus === 'complete' && (
          <div style={{
            flex: '1 1 100%',
            padding: '8px 12px',
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: 8, fontSize: 12, color: '#34d399',
          }}>
            ✅ Run complete — {passed} passed, {failed} failed
          </div>
        )}
      </div>

      {/* ── Live Results ── */}
      {(isRunning || testResults.length > 0) && (
        <ActiveRunStream
          testResults={testResults}
          cycle={cycle}
          maxCycles={maxCycles}
          currentTest={currentTest}
          passed={passed}
          failed={failed}
          totalTests={totalTests}
          status={runStatus}
        />
      )}

      {/* ── History Ledger ── */}
      <HistoryLedger />

      {/* ── Escalation Overlay ── */}
      <EscalationOverlay
        escalation={escalation}
        onChoice={handleEscalationChoice}
      />
    </div>
  )
}
