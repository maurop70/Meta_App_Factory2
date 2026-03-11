import { useState, useEffect, useRef } from 'react'

const API = ''  // Proxied via Vite config

export default function App() {
  const [tab, setTab] = useState('scout')
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch(`${API}/api/health`).then(r => r.json()).then(setHealth).catch(() => {})
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-logo">
          <div className="app-logo-icon">🔍</div>
          <div>
            <h1>GeoTalent Scout</h1>
            <div className="subtitle">Aether Intelligence</div>
          </div>
        </div>
        <div className="health-badge">
          <div className={`health-dot${health ? '' : ' off'}`} />
          {health ? `${health.employees_loaded} employees loaded` : 'Connecting...'}
        </div>
      </header>

      <div className="tabs">
        <button id="tab-scout" className={`tab-btn${tab === 'scout' ? ' active' : ''}`} onClick={() => setTab('scout')}>
          🔎 Talent Scout
        </button>
        <button id="tab-employees" className={`tab-btn${tab === 'employees' ? ' active' : ''}`} onClick={() => setTab('employees')}>
          📋 Employee Directory
        </button>
        <button id="tab-console" className={`tab-btn${tab === 'console' ? ' active' : ''}`} onClick={() => setTab('console')}>
          ⚡ Command Console
        </button>
      </div>

      {tab === 'scout' && <ScoutPanel />}
      {tab === 'employees' && <EmployeesPanel />}
      {tab === 'console' && <ConsolePanel />}
    </div>
  )
}

/* ═══════════════════════════════════════════════════
   SCOUT PANEL
   ═══════════════════════════════════════════════════ */

function ScoutPanel() {
  const [roleTitle, setRoleTitle] = useState('')
  const [location, setLocation] = useState('')
  const [jobDesc, setJobDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)

  async function handleScout() {
    if (!roleTitle || !jobDesc) return
    setLoading(true)
    setResults(null)
    try {
      const resp = await fetch(`${API}/api/scout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_title: roleTitle, location, job_description: jobDesc }),
      })
      const data = await resp.json()
      setResults(data)
    } catch (err) {
      console.error('Scout failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="card">
        <div className="card-title"><span className="icon">🎯</span> Scouting Parameters</div>
        <div className="form-grid">
          <div className="form-group">
            <label className="form-label" htmlFor="role-title">Role Title</label>
            <input id="role-title" className="form-input" placeholder="e.g. Production Line Worker"
              value={roleTitle} onChange={e => setRoleTitle(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="location">Location</label>
            <input id="location" className="form-input" placeholder="e.g. Miami, FL or Remote"
              value={location} onChange={e => setLocation(e.target.value)} />
          </div>
          <div className="form-group full-width">
            <label className="form-label" htmlFor="job-desc">Job Description</label>
            <textarea id="job-desc" className="form-textarea"
              placeholder="Paste the full job description here. The scout will extract keywords, certifications, and skill clusters..."
              value={jobDesc} onChange={e => setJobDesc(e.target.value)} />
          </div>
        </div>
        <button id="btn-scout" className="btn btn-primary" onClick={handleScout} disabled={loading || !roleTitle || !jobDesc}>
          {loading ? <><span className="spinner" /> Scouting...</> : '🔍 Launch Scout'}
        </button>
      </div>

      {results && (
        <div className="results-section">
          {/* Stats */}
          <div className="stats-row">
            <div className="stat-box">
              <div className="stat-value">{results.summary?.total_found || 0}</div>
              <div className="stat-label">Total Candidates</div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{results.summary?.internal_matches || 0}</div>
              <div className="stat-label">Internal Matches</div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{results.summary?.external_leads || 0}</div>
              <div className="stat-label">External Leads</div>
            </div>
            <div className="stat-box">
              <div className="stat-value">{results.extraction?.certifications?.length || 0}</div>
              <div className="stat-label">Certifications</div>
            </div>
          </div>

          {/* Extraction */}
          <div className="extraction-panel">
            <div className="extraction-card">
              <div className="extraction-title">Keywords Extracted</div>
              <div className="keyword-tags">
                {results.extraction?.keywords?.slice(0, 12).map((kw, i) => (
                  <span key={i} className="keyword-tag">{kw}</span>
                ))}
              </div>
            </div>
            <div className="extraction-card">
              <div className="extraction-title">Certifications</div>
              <div className="keyword-tags">
                {results.extraction?.certifications?.length
                  ? results.extraction.certifications.map((c, i) => <span key={i} className="cert-tag">{c}</span>)
                  : <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>None detected</span>
                }
              </div>
            </div>
            <div className="extraction-card">
              <div className="extraction-title">Skill Clusters</div>
              <div className="keyword-tags">
                {Object.keys(results.extraction?.skill_clusters || {}).map((cl, i) => (
                  <span key={i} className="keyword-tag">{cl}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Candidate Table */}
          <div className="card">
            <div className="results-header">
              <div className="card-title"><span className="icon">👥</span> Candidate Results</div>
              <div className="results-count"><strong>{results.candidates?.length || 0}</strong> candidates found</div>
            </div>
            <table className="results-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Name</th>
                  <th>Title / Platform</th>
                  <th>Match Score</th>
                  <th>Contact</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {results.candidates?.map((c, i) => (
                  <tr key={i}>
                    <td>
                      <span className={`badge badge-${c.source === 'Internal' ? 'internal' : 'external'}`}>
                        {c.source}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{c.name}</td>
                    <td>{c.job_title || c.platform || '—'}</td>
                    <td><ScoreBar score={c.match_score} /></td>
                    <td style={{ fontSize: '12px' }}>{c.email || c.contact || '—'}</td>
                    <td>
                      <span className={`badge badge-${c.status === 'Active' ? 'active' : 'inactive'}`}>
                        {c.status || 'N/A'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreBar({ score }) {
  const pct = Math.round((score || 0) * 100)
  const level = pct >= 60 ? 'high' : pct >= 30 ? 'medium' : 'low'
  return (
    <div className="score-bar">
      <div className="score-track">
        <div className={`score-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="score-label" style={{ color: `var(--accent-${level === 'high' ? 'emerald' : level === 'medium' ? 'amber' : 'rose'})` }}>
        {pct}%
      </span>
    </div>
  )
}

/* ═══════════════════════════════════════════════════
   EMPLOYEES PANEL
   ═══════════════════════════════════════════════════ */

function EmployeesPanel() {
  const [employees, setEmployees] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`${API}/api/employees${search ? `?search=${encodeURIComponent(search)}` : ''}`)
      .then(r => r.json())
      .then(data => { setEmployees(data.employees || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [search])

  return (
    <div className="card">
      <div className="card-title"><span className="icon">📋</span> Internal Employee Database</div>
      <div className="search-bar">
        <input id="employee-search" className="search-input" placeholder="Search by name, email, title, or phone..."
          value={search} onChange={e => setSearch(e.target.value)} />
        <div className="results-count" style={{ alignSelf: 'center', whiteSpace: 'nowrap' }}>
          <strong>{employees.length}</strong> records
        </div>
      </div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}><span className="spinner" /></div>
      ) : (
        <table className="results-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Full Name</th>
              <th>Job Title</th>
              <th>Department</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {employees.slice(0, 50).map((e, i) => (
              <tr key={i}>
                <td style={{ color: 'var(--text-muted)' }}>{e['Employee Number']}</td>
                <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{e['Full Name']}</td>
                <td>{e['Job Title']}</td>
                <td>{e['Department Code']}</td>
                <td style={{ fontSize: '12px' }}>{e['Home Email']}</td>
                <td style={{ fontSize: '12px' }}>{e['Mobile Phone'] || '—'}</td>
                <td>
                  <span className={`badge badge-${e.Status === 'Active' ? 'active' : 'inactive'}`}>
                    {e.Status || e.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════
   COMMAND CONSOLE PANEL
   ═══════════════════════════════════════════════════ */

function ConsolePanel() {
  const [logs, setLogs] = useState([{ text: 'GeoTalent Scout Console v1.0.0 — Aether Runtime', type: 'info' }])
  const [triggering, setTriggering] = useState(false)
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [logs])

  function addLog(text, type = '') {
    const ts = new Date().toLocaleTimeString()
    setLogs(prev => [...prev, { text, type, ts }])
  }

  async function triggerWorkflow() {
    setTriggering(true)
    addLog('Triggering drive_manager_workflow...', 'info')
    try {
      const resp = await fetch(`${API}/api/trigger-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'ensure_folder', folder_name: 'GeoTalent_Scout_Output' }),
      })
      const data = await resp.json()
      if (data.status === 'triggered') {
        addLog(`Workflow triggered successfully (HTTP ${data.response_code})`, 'success')
        addLog(`Action: ${data.action} | Webhook: ${data.webhook_url}`, 'info')
      } else {
        addLog(`Workflow error: ${data.error || 'Unknown'}`, 'error')
      }
    } catch (err) {
      addLog(`Connection error: ${err.message}`, 'error')
    } finally {
      setTriggering(false)
    }
  }

  async function fetchSyncLog() {
    addLog('Fetching sync log...', 'info')
    try {
      const resp = await fetch(`${API}/api/sync-log?lines=20`)
      const data = await resp.json()
      if (data.lines?.length) {
        data.lines.forEach(line => addLog(line, ''))
      } else {
        addLog('Sync log is empty', 'info')
      }
    } catch (err) {
      addLog(`Failed to fetch sync log: ${err.message}`, 'error')
    }
  }

  return (
    <div className="console">
      <div className="console-header">
        <div className="console-dots">
          <div className="console-dot red" />
          <div className="console-dot yellow" />
          <div className="console-dot green" />
        </div>
        <div className="console-title">Aether Command Console — GeoTalent Scout</div>
      </div>
      <div className="console-body" ref={bodyRef}>
        {logs.map((log, i) => (
          <div key={i} className="console-line">
            {log.ts && <span className="timestamp">[{log.ts}] </span>}
            <span className={log.type}>{log.text}</span>
          </div>
        ))}
      </div>
      <div className="console-actions">
        <button id="btn-trigger-workflow" className="btn btn-console" onClick={triggerWorkflow} disabled={triggering}>
          {triggering ? <><span className="spinner" /> Running...</> : '⚡ Trigger Drive Manager Workflow'}
        </button>
        <button id="btn-sync-log" className="btn btn-secondary" onClick={fetchSyncLog}>
          📄 Fetch Sync Log
        </button>
      </div>
    </div>
  )
}
