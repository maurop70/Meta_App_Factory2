import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

// ═══════════════════════════════════════════════════════════
//  WAR ROOM — Commander's Control Panel (Phase 8 Upgrade)
//  Real-time agent dialogue | Aether-Native UI Stepper
// ═══════════════════════════════════════════════════════════

const WS_URL = 'ws://localhost:5000/ws/warroom';
const API_BASE = 'http://localhost:5000';

const SEQUENCE_STAGES = [
  { id: 'CMO_STRATEGY', label: '1. CMO Strategy', icon: '📈' },
  { id: 'CTO_FEASIBILITY', label: '2. CTO Stack Evaluator', icon: '⚙️' },
  { id: 'CFO_FINANCIAL_MODEL', label: '3. CFO Architect', icon: '📊' },
  { id: 'PHANTOM_STRESS_TEST', label: '4. Critic & UI Phantom', icon: '🛡️' },
  { id: 'COMMERCIALLY_READY', label: '5. Launch Ready', icon: '🚀' }
];

const AGENT_STYLES = {
  CEO:       { icon: '👔', color: '#3b82f6', bg: 'rgba(59,130,246,0.08)' },
  CMO:       { icon: '📢', color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)' },
  CFO:       { icon: '💰', color: '#22c55e', bg: 'rgba(34,197,94,0.08)' },
  CTO:       { icon: '🔧', color: '#06b6d4', bg: 'rgba(6,182,212,0.08)' },
  CRITIC:    { icon: '🔍', color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
  ARCHITECT: { icon: '🏗️', color: '#06b6d4', bg: 'rgba(6,182,212,0.08)' },
  DR_ARIS:   { icon: '🩻', color: '#14b8a6', bg: 'rgba(20,184,166,0.08)' },
  SYSTEM:    { icon: '⚡', color: '#eab308', bg: 'rgba(234,179,8,0.08)' },
  COMMANDER: { icon: '⚡', color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
};

const SEVERITY_COLORS = {
  CRITICAL: '#ef4444',
  SIGNIFICANT: '#f97316',
  MODERATE: '#eab308',
};

export default function WarRoom({ ventureMode = false, onHandoff }) {
  const [selectedProject, setSelectedProject] = useState(localStorage.getItem('last_active_project') || '');
  const [projectList, setProjectList] = useState([]);
  const projectName = selectedProject; // alias
  
  useEffect(() => {
    fetch('http://localhost:5020/api/projects')
      .then(r => r.json())
      .then(data => setProjectList(Array.isArray(data) ? data : data.projects || []))
      .catch(() => {});
  }, []);

  const handleProjectSelect = (e) => {
    const val = e.target.value;
    setSelectedProject(val);
    if (val) localStorage.setItem('last_active_project', val);
  };

  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [eosState, setEosState] = useState(null);
  const [persuasion, setPersuasion] = useState(5);
  const [connected, setConnected] = useState(false);
  const [topicInput, setTopicInput] = useState('');
  // Phase 3 state
  const [activeChallenge, setActiveChallenge] = useState(null);
  const [challengeScore, setChallengeScore] = useState('');
  const [convinceMode, setConvinceMode] = useState(false);
  // UPGRADE 2: History state
  const [showHistory, setShowHistory] = useState(false);
  const [historySessions, setHistorySessions] = useState([]);
  // UPGRADE: Outcome Decision Flow
  const [outcomeProposal, setOutcomeProposal] = useState(null);
  const [implementationPlan, setImplementationPlan] = useState(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [workingAgents, setWorkingAgents] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [consensusIteration, setConsensusIteration] = useState(null);
  
  // Phase 8 variables
  const [sequenceState, setSequenceState] = useState({});
  const [isExecutingCmd, setIsExecutingCmd] = useState(false);
  const [isReadyToDeploy, setIsReadyToDeploy] = useState(false);
  const [marketPulse, setMarketPulse] = useState(null);

  // ── UI Integration (Phase 1, 2, 3 & 11) ────────────────────
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [strategyMode, setStrategyMode] = useState('balanced');
  const [customDirective, setCustomDirective] = useState('');
  const [stressTest, setStressTest] = useState(false);
  
  // Phase 11 Autonomous Forge Command Bar — fully isolated from legacy messages state
  const [operatorCmd, setOperatorCmd] = useState('');
  const [isSendingCmd, setIsSendingCmd] = useState(false);
  const [operatorLog, setOperatorLog] = useState([]);
  const [isFeedExpanded, setIsFeedExpanded] = useState(false);
  // Floating detached popup
  const [isFeedPopped, setIsFeedPopped] = useState(false);
  const [popPos, setPopPos] = useState({ x: 80, y: 80, w: 680, h: 520 });
  const _dragRef = useRef(null);

  const sendOperatorCmd = async () => {
    if (!operatorCmd.trim()) return;
    const cmdText = operatorCmd.trim();
    setIsSendingCmd(true);
    // Prepend @operator prefix so backend routing is guaranteed
    const payload = cmdText.toLowerCase().startsWith('@operator')
      ? cmdText
      : `@operator ${cmdText}`;
    // Immediately write to the ISOLATED operator log — never to legacy messages
    setOperatorLog(prev => [...prev, {
      type: 'sent', text: payload, ts: new Date().toLocaleTimeString()
    }]);
    setOperatorCmd('');
    try {
      const res = await axios.post('http://localhost:5000/api/warroom/dispatch', {
        commander_intent: payload
      });
      setOperatorLog(prev => [...prev, {
        type: 'ack', text: `CEO SYNTHESIS COMPLETE.`, ts: new Date().toLocaleTimeString()
      }]);
      
      if (res?.data?.data?.strategy) {
        setMessages(prev => [...prev, { 
          type: 'dialogue', 
          agent: 'CEO', 
          message: res.data.data.strategy, 
          timestamp: new Date().toISOString() 
        }]);
      } else if (res?.data?.data?.error) {
        setOperatorLog(prev => [...prev, {
          type: 'error', text: `SYNTHESIS ERROR: ${res.data.data.error}`, ts: new Date().toLocaleTimeString()
        }]);
      }
    } catch(e) {
      console.error('Operator dispatch failed', e);
      setOperatorLog(prev => [...prev, {
        type: 'error', text: `DISPATCH FAILED: ${e.message}`, ts: new Date().toLocaleTimeString()
      }]);
    } finally {
      setIsSendingCmd(false);
    }
  };
  
  const [showWisdomVault, setShowWisdomVault] = useState(false);
  const [pendingStandards, setPendingStandards] = useState([]);
  const [activeStandards, setActiveStandards] = useState([]);
  const [wisdomLoading, setWisdomLoading] = useState(false);

  // Phase 4: COO Operations Integration
  const [cooMetrics, setCooMetrics] = useState(null);
  const [showCooModal, setShowCooModal] = useState(false);

  const wsRef = useRef(null);
  const feedEndRef = useRef(null);
  const feedScrollRef = useRef(null);
  const fileRef = useRef(null);
  const _seenIds = useRef(new Set());
  const _msgIdCounter = useRef(0);

  // Load history
  const loadHistory = () => {
    setHistoryLoading(true);
    fetch(`/api/warroom/history?project_name=${encodeURIComponent(projectName)}`)
      .then(r => r.json())
      .then(data => setHistorySessions(data.sessions || []))
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  };

  // ── EOS Polling (Phase Tracker) ───────────────────────
  useEffect(() => {
    if (!ventureMode) return;
    const interval = setInterval(() => {
      fetch(`/api/eos/state?project_name=${encodeURIComponent(projectName)}`)
        .then(r => r.json())
        .then(setEosState)
        .catch(() => {});
    }, 2000);
    return () => clearInterval(interval);
  }, [ventureMode, projectName]);

  // ── True Backend State Sync on Mount ───────────────────────
  useEffect(() => {
    if (!projectName) return;
    fetch(`http://localhost:5000/api/warroom/state?project_name=${encodeURIComponent(projectName)}`)
      .then(r => r.json())
      .then(data => {
        if (data.is_executing) {
          setIsExecutingCmd(true);
        }
        if (data.sequence_state && Object.keys(data.sequence_state).length > 0) {
          setSequenceState(data.sequence_state);
        }
      })
      .catch((e) => console.error("Failed to sync backend state on mount:", e));
  }, [projectName]);

  // ── WebSocket Connection (dedup-safe for StrictMode) ──
  useEffect(() => {
    let ws;
    let reconnectTimer;
    let didCancel = false;

    const dedup = (data) => {
      // Create a fingerprint from agent + message + timestamp
      const fp = `${data.agent || ''}:${(data.message || '').slice(0, 80)}:${data.timestamp || ''}`;
      if (_seenIds.current.has(fp)) return true; // duplicate
      _seenIds.current.add(fp);
      // Keep set bounded — prune after 500 entries
      if (_seenIds.current.size > 500) {
        const arr = [..._seenIds.current];
        _seenIds.current = new Set(arr.slice(-250));
      }
      return false;
    };

    const connect = () => {
      if (didCancel) return;
      ws = new WebSocket(`${WS_URL}?project=${encodeURIComponent(projectName)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!didCancel) setConnected(true);
      };

      ws.onmessage = (event) => {
        if (didCancel) return;
        const data = JSON.parse(event.data);

        // ── Phase 11 sentinel strings that must NEVER trigger startDebate ──
        const _isPhase11Msg = (msg) => {
          if (!msg) return false;
          const m = msg.toLowerCase();
          return m.includes('[state_machine]') ||
                 m.includes('executive fork') ||
                 m.includes('incubator gate') ||
                 m.includes('incubator_gate') ||
                 m.includes('pre-flight intelligence') ||
                 m.includes('@operator approve') ||
                 m.includes('@operator reject');
        };

        if (data.type === 'init') {
          setMessages(data.history || []);
          setPersuasion(data.persuasion || 5);
        } else if (data.type === 'dialogue') {
          // ── Intercept [state_machine] messages masquerading as dialogue ──
          const rawMsg = data.message || '';
          if (rawMsg.includes('[state_machine]')) {
            // Parse: "[state_machine] phase=CMO_STRATEGY status=ACTIVE"
            // Also handles: "[state_machine] CMO_STRATEGY: ACTIVE" and similar variants
            const phaseMatch = rawMsg.match(/phase=([\w]+)/) || rawMsg.match(/\[state_machine\]\s+([\w]+)[:\s]/);
            const statusMatch = rawMsg.match(/status=([\w]+)/) || rawMsg.match(/(?:ACTIVE|PROCESSING|DONE|PASS|FAIL|WAITING)/);
            if (phaseMatch) {
              const phase = phaseMatch[1];
              // Map verbose status strings to canonical UI status tokens
              const rawStatus = statusMatch ? statusMatch[1] || statusMatch[0] : 'PROCESSING';
              const STATUS_MAP = { ACTIVE: 'PROCESSING', DONE: 'PASS', STARTED: 'PROCESSING', COMPLETE: 'PASS', COMPLETED: 'PASS', ERROR: 'FAIL' };
              const status = STATUS_MAP[rawStatus.toUpperCase()] || rawStatus.toUpperCase();
              setSequenceState(prev => ({ ...prev, [phase]: status }));
            }
            return; // swallow — do NOT render in feed
          }
          if (!dedup(data)) {
            data._id = ++_msgIdCounter.current;
            setMessages(prev => [...prev, data]);
          }
        } else if (data.type === 'persuasion_update') {
          setPersuasion(data.score);
        } else if (data.type === 'challenge') {
          setActiveChallenge(prev => prev?.challenge_id === data.challenge_id ? prev : data);
          setConvinceMode(true);
        } else if (data.type === 'challenge_resolved') {
          if (data.verdict === 'CONVINCED' || data.verdict === 'OVERRIDE') {
            setActiveChallenge(null);
            setConvinceMode(false);
          }
        } else if (data.type === 'outcome_proposal') {
          setOutcomeProposal(data);
        } else if (data.type === 'implementation_plan') {
          setImplementationPlan(data);
          setGeneratingPlan(false);
        } else if (data.type === 'agent_working') {
          setWorkingAgents(prev => {
            if (prev.some(a => a.agent === data.agent)) return prev;
            return [...prev, { agent: data.agent, timestamp: Date.now() }];
          });
        } else if (data.type === 'coo_alert') {
          setCooMetrics({
            tokens: data.tokens_total,
            budget: data.budget,
            status: data.status,
            cost: data.est_cost
          });
        } else if (data.type === 'consensus_iteration') {
          setConsensusIteration({
            iteration: data.iteration,
            maxIterations: data.max_iterations,
            status: data.status || 'RUNNING',
          });
          if (data.status === 'CONSENSUS' || data.status === 'MAX_REACHED') {
            setTimeout(() => setConsensusIteration(null), 8000);
          }
        } else if (data.type === 'state_reset') {
          setSequenceState({});
          setIsReadyToDeploy(false);
          setIsExecutingCmd(false);
          setOutcomeProposal(null);
          setImplementationPlan(null);
          if (!dedup(data)) {
            data._id = ++_msgIdCounter.current;
            setMessages(prev => [...prev, {
              type: 'dialogue',
              agent: 'SYSTEM',
              icon: '💥',
              color: '#ef4444',
              message: `**STATE RESET**\n${data.message || 'Commander Override: Session flushed.'}`,
              timestamp: data.timestamp || Date.now()
            }]);
          }
        } else if (data.type === 'state_machine') {
          setSequenceState(prev => ({ ...prev, [data.phase]: data.status }));
          if (data.phase === 'COMMERCIALLY_READY' && data.status === 'PASS') {
            setIsReadyToDeploy(true);
            setIsExecutingCmd(false);
          }
          if (data.status === 'FAIL') {
            setIsExecutingCmd(false);
          }
        } else if (data.type === 'market_pulse') {
          setMarketPulse(data);
        } else if (data.type === 'wisdom_proposal') {
          setMessages(prev => [...prev, {
            type: 'dialogue', agent: 'SYSTEM',
            message: `💡 New standard proposed: ${data.candidate.title}. Open Wisdom Vault to review.`,
            timestamp: data.timestamp
          }]);
        } else if (data.type === 'persona_update') {
          setMessages(prev => [...prev, {
            type: 'dialogue', agent: data.agent,
            icon: data.level_up ? '🌟' : '🩹',
            isPersonaUpdate: true,
            levelUp: data.level_up,
            message: `**[${data.level_up ? 'PERSISTENT MEMORY UPDATE' : 'SCAR RECORDED'}]**\n\n${data.message}`,
            timestamp: data.timestamp
          }]);
        } else if (data.type === 'telemetry') {
          if (!dedup(data)) {
            data._id = ++_msgIdCounter.current;
            setMessages(prev => [...prev, {
              type: 'dialogue',
              agent: 'FORGE_QA',
              icon: '⚙️',
              message: `📡 **TELEMETRY CORE FEED**\n${data.message}`,
              timestamp: data.timestamp || Date.now()
            }]);
          }
        }
        
        // Clear agent from working state when they speak
        if (data.type === 'dialogue' && data.agent) {
          setWorkingAgents(prev => prev.filter(a => a.agent !== data.agent));
        }
      };

      ws.onclose = () => {
        if (!didCancel) {
          setConnected(false);
          setWorkingAgents([]);
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    // ── Keepalive ping every 20s to prevent WS timeout during long debates ──
    const pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(JSON.stringify({ type: 'ping' })); } catch (_) {}
      }
    }, 20000);

    connect();

    return () => {
      didCancel = true;
      clearTimeout(reconnectTimer);
      clearInterval(pingInterval);
      if (ws) ws.close();
    };
  }, [projectName]);

  const loadWisdom = async () => {
    setWisdomLoading(true);
    try {
      const pRes = await axios.get('http://localhost:5000/api/wisdom/pending');
      setPendingStandards(pRes.data);
      const aRes = await axios.get('http://localhost:5000/api/wisdom/standards');
      setActiveStandards(aRes.data);
    } catch(e) { console.error('Wisdom load failed', e); }
    setWisdomLoading(false);
  };

  const approveStandard = async (id) => {
    await axios.post('http://localhost:5000/api/wisdom/approve', { standard_id: id });
    loadWisdom();
  };

  const rejectStandard = async (id) => {
    await axios.post('http://localhost:5000/api/wisdom/reject', { standard_id: id });
    loadWisdom();
  };

  useEffect(() => {
    if (!projectName) return;
    fetch(`/api/coo/budget?project_id=${encodeURIComponent(projectName)}`)
      .then(res => res.json())
      .then(data => setCooMetrics({ tokens: data.tokens_total, budget: data.budget, status: data.status, cost: data.est_cost }))
      .catch(e => console.error("COO fetch failed", e));
  }, [projectName]);

  // ── Auto-scroll (smart: only scrolls if Commander is near bottom) ──────────
  useEffect(() => {
    const container = feedScrollRef.current;
    if (!container) { feedEndRef.current?.scrollIntoView({ behavior: 'smooth' }); return; }
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    // Only auto-scroll if within 200px of the bottom — respect manual scroll position
    if (distanceFromBottom < 200) {
      feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, operatorLog]);

  // ── Escape key closes expanded feed / popup ────────────────────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (isFeedExpanded) setIsFeedExpanded(false);
        if (isFeedPopped)   setIsFeedPopped(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isFeedExpanded, isFeedPopped]);

  // ── Popup drag handler ────────────────────────────────────────────────────
  const startPopupDrag = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX - popPos.x;
    const startY = e.clientY - popPos.y;
    const onMove = (ev) => {
      setPopPos(p => ({ ...p,
        x: Math.max(0, ev.clientX - startX),
        y: Math.max(0, ev.clientY - startY),
      }));
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [popPos]);

  // ── Trigger Debate on Commander Intervention ──────────
  const startDebate = useCallback(() => {
    if (projectName && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'intervention', message: 'START_DEBATE' }));
    } else if (projectName) {
      // Fallback
      fetch(`/api/warroom/intervene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'intervention', message: 'START_DEBATE', project_name: projectName }),
      }).catch(e => console.error('START_DEBATE HTTP fallback failed:', e));
    }
  }, [projectName]);

  useEffect(() => {
    if (messages.length > 0 && selectedProject) {
      const lastMsg = messages[messages.length - 1];
      // ── Phase 11: Agents that must NEVER trigger startDebate ──
      const _isOperatorAgent = [
        'INCUBATOR_GATE', 'GHOST_OPERATOR', 'FORGE_QA', 'OPERATOR', 'SYSTEM'
      ].includes(lastMsg.agent);

      if (lastMsg.agent === 'COMMANDER' && lastMsg.message && !lastMsg.message.includes('START_DEBATE') && !_isOperatorAgent) {
        const m = lastMsg.message.toLowerCase();
        // Phase 11 hard mute — never debate these payloads
        if (
          m.includes('[operator command]') ||
          m.includes('@operator') ||
          m.includes('executive fork') ||
          m.includes('[state_machine]') ||
          m.includes('incubator gate') ||
          m.includes('incubator_gate') ||
          m.includes('pre-flight intelligence') ||
          m.includes('ghost operator')
        ) return;
        startDebate();
      }
    }
  }, [messages, selectedProject, startDebate]);

  // ── Safe WebSocket Send with HTTP fallback ──────────
  const sendSafe = useCallback((payload) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    } else {
      // WS is closed — use HTTP fallback so intervention always reaches backend
      fetch(`/api/warroom/intervene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, project_name: projectName }),
      }).catch(e => console.error('Intervention HTTP fallback failed:', e));
    }
  }, [projectName]);

  // ── Send Intervention (Phase 2) ───────────────────────
  const sendIntervention = useCallback(() => {
    if (!inputText.trim()) return;

    if (convinceMode && activeChallenge) {
      // Phase 3: Submit as convince reasoning
      fetch(`/api/warroom/convince`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: projectName,
          challenge_id: activeChallenge.challenge_id,
          reasoning: inputText.trim(),
        }),
      });
    } else {
      const intentTxt = inputText.trim();
      const isOp = intentTxt.toLowerCase().startsWith('@operator') || intentTxt.toLowerCase().startsWith('operator ');

      if (isOp) {
        setMessages(prev => [...prev, { type: 'dialogue', agent: 'COMMANDER', message: intentTxt, timestamp: new Date().toISOString(), is_user: true }]);
        
        axios.post('http://localhost:5000/api/warroom/dispatch', {
          commander_intent: intentTxt
        }).then(res => {
          if (res?.data?.data?.strategy) {
            setMessages(prev => [...prev, { type: 'dialogue', agent: 'CEO', message: res.data.data.strategy, timestamp: new Date().toISOString() }]);
          }
        }).catch(e => console.error('Operator dispatch failed:', e));
        
      } else {
        // 1. Dispatch hitting C-Suite trigger
        axios.post('http://localhost:5000/api/war-room/dispatch', {
          message: intentTxt,
          project_id: selectedProject || 'AntigravityWorkspace_Q3'
        }, {
          headers: {
            'Content-Type': 'application/json',
            'X-Antigravity-Project-ID': selectedProject || 'AntigravityWorkspace_Q3'
          }
        }).catch(e => console.error('Dispatch failed:', e));

        // 2. Transmit to active the UI session & debate feed
        sendSafe({ type: 'intervention', message: intentTxt });
      }
    }
    setInputText('');
  }, [inputText, convinceMode, activeChallenge, sendSafe, projectName, selectedProject]);

  // ── Hard Override (Phase 3 enhanced) ──────────────────
  const sendOverride = useCallback(() => {
    if (activeChallenge) {
      // Phase 3: Structured force proceed
      fetch(`/api/warroom/force_proceed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: projectName,
          challenge_id: activeChallenge.challenge_id,
          note: inputText.trim() || 'Commander override — proceeding.',
        }),
      });
      setInputText('');
    } else if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'override' }));
    }
  }, [activeChallenge, inputText]);

  // ── Issue Socratic Challenge (Phase 3) ────────────────
  const issueChallenge = useCallback(() => {
    if (!topicInput.trim()) return;
    const score = parseFloat(challengeScore) || persuasion;
    fetch(`/api/warroom/challenge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: projectName,
        proposal: topicInput.trim(),
        critic_score: score,
      }),
    });
    setTopicInput('');
    setChallengeScore('');
  }, [topicInput, challengeScore, persuasion, projectName]);

  // ── Seed Topic (Phase 2) ──────────────────────────────
  const seedTopic = useCallback(() => {
    if (!topicInput.trim()) return;
    fetch(`/api/warroom/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_name: projectName, topic: topicInput.trim() }),
    });
    setTopicInput('');
  }, [topicInput, projectName]);

  // ── 🆕 EOS Action Trigger ─────────────────────────────
  const triggerEosAction = useCallback((cmd) => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'intervention', message: cmd }));
    }
  }, []);

  // ── 🆕 Upload Handler ─────────────────────────────────
  const uploadFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || uploading) return;
    e.target.value = '';
    
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('project_name', projectName);
    
    try {
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'intervention', message: `Uploading document: ${file.name}...` }));
      }
      await fetch(`/api/warroom/upload`, { method: 'POST', body: fd });
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setUploading(false);
    }
  };

  // ── Outcome Decision Handlers ──────────────────────────
  const handleOutcomeChoice = async (choice) => {
    if (choice === 'dismiss') {
      setOutcomeProposal(null);
      return;
    }
    setGeneratingPlan(true);
    setOutcomeProposal(null);
    try {
      await fetch(`/api/warroom/execute_outcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_name: projectName, outcome_type: choice }),
      });
    } catch (err) {
      console.error('Outcome execution failed', err);
      setGeneratingPlan(false);
    }
  };

  const approvePlan = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'intervention',
        message: `✅ APPROVED: Implementation plan for ${implementationPlan?.outcome_type?.toUpperCase() || 'UPDATE'}. Proceeding to build.`,
      }));
    }
    if (implementationPlan?.outcome_type === 'new' && onHandoff) {
      onHandoff({ plan: implementationPlan.plan });
    }
    setImplementationPlan(null);
  };

  const rejectPlan = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'intervention',
        message: '❌ REJECTED: Implementation plan needs revision. Re-entering deliberation.',
      }));
    }
    setImplementationPlan(null);
  };

  // ── Helpers ───────────────────────────────────────────
  const getMeterColor = (score) => {
    if (score <= 3) return '#ef4444';
    if (score <= 5) return '#eab308';
    if (score <= 7) return '#f97316';
    return '#22c55e';
  };

  const getMeterLabel = (score) => {
    if (score <= 2) return 'Hostile';
    if (score <= 4) return 'Skeptical';
    if (score <= 6) return 'Neutral';
    if (score <= 8) return 'Receptive';
    return 'Convinced';
  };

  const formatTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div style={styles.container}>
      {/* ── Header ── */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.headerIcon}>🏛️</span>
          <div>
            <h2 style={styles.headerTitle}>Adversarial War Room</h2>
            {convinceMode ? (
              <span style={styles.headerSub}>🔴 STRATEGIC PAUSE — Socratic Challenge Active</span>
            ) : (
              <select 
                className="bg-gray-800 text-white p-2 rounded mb-4 w-full"
                value={selectedProject}
                onChange={handleProjectSelect}
                style={{ marginTop: '5px', fontSize: '13px', border: '1px solid rgba(100,116,139,0.3)', minWidth: '220px' }}
              >
                <option value="">-- Choose Project --</option>
                <option value="AntigravityWorkspace_Q3">AntigravityWorkspace_Q3 (Fail-safe)</option>
                {projectList.map(p => (
                  <option key={p.name || p} value={p.name || p}>{p.display_name || p}</option>
                ))}
              </select>
            )}
            <style>{`
              @keyframes pulsePhase {
                  0% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0.4); }
                  70% { box-shadow: 0 0 0 8px rgba(234, 179, 8, 0); }
                  100% { box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
              }
            `}</style>
          </div>
        </div>
        <div style={styles.headerRight}>
          <button onClick={() => window.open(`file://C:/Users/mpetr/.gemini/antigravity/projects/${projectName}/artifacts/cfo_reports/business_plan.xlsx`, '_blank')}
            style={{ padding: '6px 14px', borderRadius: '6px', background: '#334155', color: '#f8fafc', border: '1px solid #475569', cursor: 'pointer', fontWeight: 'bold', marginRight: '8px', fontSize: '11px', fontFamily: 'Inter, sans-serif' }}>
            📊 View Financials
          </button>
          <button onClick={() => alert(`🚀 DEPLOYING ${projectName} TO PRODUCTION CLOUD!`)} disabled={!isReadyToDeploy}
            style={{
                padding: '6px 14px', borderRadius: '6px', marginRight: '16px', fontWeight: 'bold', border: 'none', cursor: isReadyToDeploy ? 'pointer' : 'not-allowed',
                background: isReadyToDeploy ? 'linear-gradient(90deg, #10b981, #059669)' : '#1e293b',
                color: isReadyToDeploy ? '#fff' : '#64748b', transition: 'all 0.3s ease', fontSize: '11px', fontFamily: 'Inter, sans-serif'
            }}>
            {isReadyToDeploy ? '🚀 LAUNCH' : '🔒 LOCKED'}
          </button>
          <button onClick={() => { setShowWisdomVault(true); loadWisdom(); }}
            style={{
              padding: '6px 14px', borderRadius: '6px', border: '1px solid #4338ca',
              background: 'linear-gradient(90deg, #4f46e5, #4338ca)',
              color: '#fff', fontSize: '11px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginRight: '8px',
            }}
          >💡 Wisdom Vault</button>
          <button onClick={() => setShowCooModal(true)}
            style={{
              padding: '6px 14px', borderRadius: '6px', border: '1px solid #059669',
              background: 'linear-gradient(90deg, #10b981, #059669)',
              color: '#fff', fontSize: '11px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginRight: '8px',
            }}
          >⏱️ COO Token Ops {cooMetrics && `(${cooMetrics.cost})`}</button>
          <button
            onClick={() => { setShowHistory(!showHistory); if (!showHistory) loadHistory(); }}
            style={{
              padding: '4px 12px', borderRadius: '6px', border: '1px solid rgba(100,116,139,0.3)',
              background: showHistory ? 'rgba(99,102,241,0.15)' : 'rgba(0,0,0,0.2)',
              color: showHistory ? '#818cf8' : '#94a3b8', fontSize: '11px', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginRight: '8px',
            }}
          >📜 History</button>
          {convinceMode && (
            <span style={styles.pauseBadge}>⏸ PAUSED</span>
          )}
          <span style={{
            ...styles.statusDot,
            background: connected ? '#22c55e' : '#ef4444',
            boxShadow: connected ? '0 0 8px rgba(34,197,94,0.5)' : '0 0 8px rgba(239,68,68,0.5)',
          }} />
          <span style={styles.statusText}>{connected ? 'LIVE' : 'RECONNECTING...'}</span>
        </div>
      </div>

      {selectedProject ? (
        <>
          {/* ── Native Stepper (Phase 8 Upgrade) ── */}
          <div style={{ padding: '20px', background: '#0a0e17', borderTop: '1px solid #1e293b', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: 'Inter, sans-serif' }}>
            {SEQUENCE_STAGES.map((stage, i) => {
              const status = sequenceState[stage.id] || 'WAITING';
              let color = '#475569';
              if (status === 'PROCESSING') color = '#eab308';
              if (status === 'PASS') color = '#10b981';
              if (status === 'FAIL') color = '#ef4444';
              return (
                <div key={stage.id} style={{ display: 'flex', flex: 1, alignItems: 'center' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: status === 'WAITING' ? 0.6 : 1, transition: 'all 0.4s ease' }}>
                    <div style={{ width: '42px', height: '42px', borderRadius: '50%', border: `2px solid ${color}`, background: `${color}1A`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', animation: status === 'PROCESSING' ? 'pulsePhase 1.5s infinite' : 'none' }}>
                      {stage.icon}
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: status === 'WAITING' ? '#94a3b8' : '#e2e8f0', letterSpacing: '0.02em' }}>{stage.label}</span>
                    <span style={{ fontSize: '10px', background: `${color}25`, color: color, padding: '3px 8px', borderRadius: '12px', fontWeight: 'bold' }}>{status.replace('_', ' ')}</span>
                  </div>
                  {i < SEQUENCE_STAGES.length - 1 && <div style={{ flex: 1, height: '2px', background: (sequenceState[SEQUENCE_STAGES[i+1]?.id] && sequenceState[SEQUENCE_STAGES[i+1]?.id] !== 'WAITING') ? '#10b981' : '#1e293b', margin: '0 15px', marginTop: '-25px' }} />}
                </div>
              );
            })}
          </div>

          {/* ── Strategic Pivot Card (Phase 9) ── */}
          {marketPulse && (
            <div style={{
              margin: '15px 20px', padding: '16px', borderRadius: '8px',
              background: marketPulse.verdict === 'BEARISH' ? 'rgba(245, 158, 11, 0.15)' : (marketPulse.verdict === 'BULLISH' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(100, 116, 139, 0.1)'),
              border: `1px solid ${marketPulse.verdict === 'BEARISH' ? '#f59e0b' : (marketPulse.verdict === 'BULLISH' ? '#10b981' : '#64748b')}`,
              display: 'flex', alignItems: 'center', gap: '15px', fontFamily: 'Inter, sans-serif'
            }}>
              <div style={{ fontSize: '24px' }}>{marketPulse.verdict === 'BEARISH' ? '⚠️' : (marketPulse.verdict === 'BULLISH' ? '📈' : '⚖️')}</div>
              <div>
                <h4 style={{ margin: 0, color: '#f1f5f9', fontSize: '14px', fontWeight: 600 }}>Strategic Pivot Card: {marketPulse.verdict} Market</h4>
                <p style={{ margin: '4px 0 0 0', color: '#cbd5e1', fontSize: '13px' }}>
                  {marketPulse.verdict === 'BEARISH' 
                    ? `Action Required: Trend velocity is low (${marketPulse.velocity}). System applied a 0.7x target contraction. Commander must review the CMO's Pivot Option.`
                    : `Velocity: ${marketPulse.velocity} | Sentiment: ${marketPulse.sentiment}. System cleared for aggressive expansion roadmap.`}
                </p>
              </div>
            </div>
          )}

          <div style={styles.body}>
        {/* ── History Panel (Upgrade 2) ── */}
        {showHistory && (
          <div style={{
            width: '280px', borderRight: '1px solid rgba(100,116,139,0.12)',
            background: 'rgba(15,23,42,0.4)', overflowY: 'auto', padding: '12px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700, color: '#f1f5f9' }}>📜 Past Debates</h4>
              <span style={{ fontSize: '10px', color: '#64748b' }}>{historySessions.length} sessions</span>
            </div>
            {historyLoading && <p style={{ fontSize: '11px', color: '#64748b' }}>Loading...</p>}
            {historySessions.map((session, i) => (
              <div key={i} style={{
                padding: '10px', marginBottom: '6px', borderRadius: '8px',
                background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(100,116,139,0.1)',
                cursor: 'pointer',
              }}
              onClick={() => {
                setMessages(session.messages);
                setShowHistory(false);
              }}
              >
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  {session.topic?.slice(0, 60) || 'Untitled'}
                </div>
                <div style={{ fontSize: '10px', color: '#64748b' }}>
                  {session.messages?.length || 0} messages • {session.started ? new Date(session.started).toLocaleDateString() : ''}
                </div>
              </div>
            ))}
            {historySessions.length === 0 && !historyLoading && (
              <p style={{ fontSize: '11px', color: '#475569', textAlign: 'center', marginTop: '20px' }}>
                No debate history yet.
              </p>
            )}
          </div>
        )}
        {/* ── Left: LIVE COMMAND CORE FEED ── */}
        <div style={{
          ...styles.feedPanel,
          ...(isFeedExpanded ? {
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: '#0b0f19',
            padding: '32px',
            border: 'none',
          } : {})
        }}>
          {/* Topic Seeder + Challenge Trigger */}
          <div style={styles.topicBar}>
            {/* ── Feed Expand Toggle ── */}
            <button
              id="war-room-expand-btn"
              onClick={() => setIsFeedExpanded(v => !v)}
              title={isFeedExpanded ? 'Collapse feed (Esc)' : 'Expand feed to full-screen'}
              style={{
                padding: '6px 12px', borderRadius: '6px', border: '1px solid rgba(139,92,246,0.5)',
                background: isFeedExpanded ? 'rgba(139,92,246,0.3)' : 'rgba(139,92,246,0.1)',
                color: '#a78bfa', fontSize: '11px', cursor: 'pointer',
                flexShrink: 0, transition: 'all 0.2s ease', fontWeight: 700,
                letterSpacing: '0.5px'
              }}
            >
              {isFeedExpanded ? '↙ COLLAPSE' : '↗ EXPAND'}
            </button>
            {/* ── Pop Out Button ── */}
            <button
              id="war-room-popout-btn"
              onClick={() => setIsFeedPopped(v => !v)}
              title={isFeedPopped ? 'Close floating popup (Esc)' : 'Pop debate feed into floating window'}
              style={{
                padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(6,182,212,0.4)',
                background: isFeedPopped ? 'rgba(6,182,212,0.2)' : 'rgba(6,182,212,0.06)',
                color: '#22d3ee', fontSize: '13px', cursor: 'pointer',
                flexShrink: 0, transition: 'all 0.2s ease', fontWeight: 700,
              }}
            >{isFeedPopped ? '🗗 Docked' : '🗗 Pop Out'}</button>
            <input
              type="text"
              value={topicInput}
              onChange={e => setTopicInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && seedTopic()}
              placeholder="Set debate topic / proposal..."
              style={styles.topicInput}
            />
            <input
              type="number"
              value={challengeScore}
              onChange={e => setChallengeScore(e.target.value)}
              placeholder="Score"
              style={{ ...styles.topicInput, width: '70px', flex: 'none', textAlign: 'center' }}
              min="1" max="10" step="0.5"
            />
            <button onClick={async () => {
              setIsExecutingCmd(true); setIsReadyToDeploy(false); setSequenceState({}); setMarketPulse(null);
              setMessages(prev => [...prev, { type: 'dialogue', agent: 'COMMANDER', message: `▶ PROTOCOL OVERRIDE: Executing Unified Aether-Native Extration Loop for [${projectName}]...`, timestamp: new Date().toISOString() }]);
              try { await fetch(`/api/warroom/execute`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: projectName, intent: "Genesis" }) }); } 
              catch (err) { setMessages(prev => [...prev, { type: 'dialogue', agent: 'SYSTEM', message: `Execution failed: ${err.message}`, isError: true, timestamp: new Date().toISOString() }]); setIsExecutingCmd(false); }
            }} disabled={isExecutingCmd} style={{ ...styles.topicBtn, background: isExecutingCmd ? '#475569' : 'linear-gradient(135deg, #6366f1, #4f46e5)', width: 'auto' }}>
              {isExecutingCmd ? '⏳ Executing...' : '▶ Initialize Protocol'}
            </button>
            <button onClick={seedTopic} style={styles.topicBtn}>🏛️ Debate</button>
            <button onClick={issueChallenge} style={{ ...styles.topicBtn, background: 'linear-gradient(135deg, #ef4444, #dc2626)' }}>🔍 Challenge</button>
            <button onClick={() => fileRef.current?.click()} disabled={uploading} style={{ ...styles.topicBtn, background: uploading ? '#64748b' : 'linear-gradient(135deg, #10b981, #059669)' }}>
              {uploading ? '⏳' : '📎 Upload'}
            </button>
            <input type="file" ref={fileRef} onChange={uploadFile} style={{ display: 'none' }} />
          </div>

          {/* ── FLOATING POPUP (detached draggable chat window) ── */}
          {isFeedPopped && (
            <div style={{
              position: 'fixed',
              left: popPos.x, top: popPos.y,
              width: popPos.w, height: popPos.h,
              minWidth: 380, minHeight: 300,
              zIndex: 9999,
              background: 'linear-gradient(160deg, #0b1120, #0d1829)',
              border: '1px solid rgba(6,182,212,0.35)',
              borderRadius: '14px',
              boxShadow: '0 24px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(6,182,212,0.1)',
              display: 'flex', flexDirection: 'column',
              fontFamily: 'Inter, sans-serif',
              resize: 'both', overflow: 'hidden',
            }}>
              {/* Drag handle / title bar */}
              <div
                onMouseDown={startPopupDrag}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  background: 'linear-gradient(90deg, rgba(6,182,212,0.12), rgba(99,102,241,0.08))',
                  borderBottom: '1px solid rgba(6,182,212,0.2)',
                  cursor: 'grab', userSelect: 'none', borderRadius: '14px 14px 0 0',
                  flexShrink: 0,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '14px' }}>🏛️</span>
                  <span style={{ color: '#22d3ee', fontWeight: 700, fontSize: '12px', letterSpacing: '0.5px' }}>
                    WAR ROOM — DEBATE FEED
                  </span>
                  <span style={{ fontSize: '10px', color: '#475569', marginLeft: '4px' }}>
                    {messages.filter(m => m.type === 'dialogue').length} messages
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => setIsFeedExpanded(true)}
                    title="Go full-screen"
                    style={{
                      background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)',
                      color: '#a78bfa', borderRadius: '6px', padding: '3px 10px',
                      cursor: 'pointer', fontSize: '11px', fontWeight: 700,
                    }}
                  >⛶</button>
                  <button
                    onClick={() => setIsFeedPopped(false)}
                    title="Close popup (Esc)"
                    style={{
                      background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.25)',
                      color: '#ef4444', borderRadius: '6px', padding: '3px 10px',
                      cursor: 'pointer', fontSize: '13px', fontWeight: 700, lineHeight: 1,
                    }}
                  >✕</button>
                </div>
              </div>

              {/* Popup message list */}
              <div style={{
                flex: 1, overflowY: 'auto', padding: '12px 14px',
                display: 'flex', flexDirection: 'column', gap: '8px',
              }}>
                {messages.filter(m => m.type === 'dialogue').length === 0 && (
                  <div style={{ textAlign: 'center', marginTop: '40px', color: '#475569' }}>
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>🏛️</div>
                    <div style={{ fontSize: '13px' }}>No debate messages yet.</div>
                  </div>
                )}
                {messages.filter(m => m.type === 'dialogue').map((msg, i) => {
                  const agentStyle = AGENT_STYLES[msg.agent] || AGENT_STYLES.SYSTEM;
                  const isUser = msg.is_user || msg.agent === 'COMMANDER';
                  return (
                    <div key={i} style={{
                      padding: '10px 14px', borderRadius: '10px',
                      background: isUser ? 'rgba(249,115,22,0.1)' : agentStyle.bg,
                      borderLeft: `3px solid ${isUser ? '#f97316' : agentStyle.color}`,
                      flexShrink: 0,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                        <span style={{ fontSize: '14px' }}>{agentStyle.icon}</span>
                        <span style={{ fontWeight: 700, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: agentStyle.color }}>{msg.agent}</span>
                        <span style={{ fontSize: '10px', color: '#475569', marginLeft: 'auto' }}>{formatTime(msg.timestamp)}</span>
                        {isUser && <span style={{ padding: '1px 5px', borderRadius: '4px', fontSize: '9px', fontWeight: 700, background: 'rgba(249,115,22,0.2)', color: '#f97316' }}>YOU</span>}
                      </div>
                      <div style={{ fontSize: '12.5px', lineHeight: 1.65, color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.message}</div>
                    </div>
                  );
                })}
                <div ref={isFeedPopped ? feedEndRef : undefined} />
              </div>

              {/* Quick-reply bar at bottom of popup */}
              <div style={{
                display: 'flex', gap: '6px', padding: '10px 12px',
                borderTop: '1px solid rgba(6,182,212,0.12)',
                background: 'rgba(0,0,0,0.2)', flexShrink: 0,
              }}>
                <input
                  type="text"
                  placeholder="Quick intervention..."
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendIntervention()}
                  style={{
                    flex: 1, background: '#0f172a', border: '1px solid rgba(6,182,212,0.2)',
                    color: '#e2e8f0', padding: '8px 12px', borderRadius: '8px',
                    fontSize: '12px', fontFamily: 'Inter, sans-serif', outline: 'none',
                  }}
                />
                <button
                  onClick={sendIntervention}
                  disabled={!inputText.trim()}
                  style={{
                    background: inputText.trim() ? 'linear-gradient(135deg, #06b6d4, #0891b2)' : '#1e293b',
                    border: 'none', color: '#fff', padding: '8px 16px',
                    borderRadius: '8px', fontWeight: 700, fontSize: '11px',
                    cursor: inputText.trim() ? 'pointer' : 'not-allowed',
                  }}
                >Send</button>
              </div>
            </div>
          )}


          <div ref={feedScrollRef} style={styles.feed}>
            {messages.length === 0 && (
              <div style={styles.emptyState}>
                <span style={{ fontSize: '48px' }}>🏛️</span>
                <p style={{ color: '#64748b', marginTop: '12px' }}>
                  No boardroom session active.<br />
                  <strong>Debate</strong> opens free discussion. <strong>Challenge</strong> triggers Socratic Pause.
                </p>
              </div>
            )}
            {messages.filter(m => m.type === 'dialogue').map((msg, i) => {
              const agentStyle = AGENT_STYLES[msg.agent] || AGENT_STYLES.SYSTEM;
              const isUser = msg.is_user || msg.agent === 'COMMANDER';
              const isLong = (msg.message || '').length > 800;
              return (
                <div key={i} style={{
                  ...styles.message,
                  background: agentStyle.bg,
                  borderLeft: `3px solid ${agentStyle.color}`,
                  ...(isUser ? { background: 'rgba(249,115,22,0.1)', borderLeft: '3px solid #f97316' } : {}),
                }}>
                  <div style={styles.msgHeader}>
                    <span style={styles.msgIcon}>{msg.isPersonaUpdate ? msg.icon : (agentStyle.icon || msg.icon)}</span>
                    <span style={{ ...styles.msgAgent, color: agentStyle.color }}>{msg.agent}</span>
                    {msg.isPersonaUpdate && (
                      <span style={{
                        background: msg.levelUp ? 'linear-gradient(135deg, #10b981, #059669)' : 'linear-gradient(135deg, #ef4444, #dc2626)',
                        color: '#fff',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.7.5rem',
                        fontWeight: 'bold',
                        marginLeft: '8px',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                      }}>
                        {msg.levelUp ? '⭐ XP GAINED' : '⚠️ EXPERIENCE SCAR'}
                      </span>
                    )}
                    <span style={styles.msgTime}>{formatTime(msg.timestamp)}</span>
                    {isUser && <span style={styles.userBadge}>YOU</span>}
                  </div>
                  <div style={{
                    ...styles.msgText,
                    fontSize: isFeedExpanded ? '1rem' : '0.75rem',
                    // Phase 11 Executive Fork briefs are long — let them breathe
                    ...(isLong ? { maxHeight: '70vh', overflowY: 'auto', paddingRight: '8px' } : {}),
                  }}>{msg.message}</div>
                </div>
              );
            })}
            <div ref={feedEndRef} />
          </div>

          {/* ── Phase 11 Operator Log (isolated — never touches legacy messages) ── */}
          {operatorLog.length > 0 && (
            <div style={{
              flex: '0 0 auto', maxHeight: '180px', overflowY: 'auto',
              padding: '8px 16px',
              background: '#070c14', borderTop: '1px solid rgba(16,185,129,0.15)',
              fontFamily: 'JetBrains Mono, monospace', fontSize: '12px'
            }}>
              {operatorLog.map((entry, i) => (
                <div key={i} style={{
                  color: entry.type === 'error' ? '#ef4444'
                       : entry.type === 'ack'   ? '#10b981'
                       : '#94a3b8',
                  marginBottom: '2px'
                }}>
                  <span style={{ color: '#475569', marginRight: '8px' }}>[{entry.ts}]</span>
                  {entry.type === 'sent' ? '⚡ ' : entry.type === 'ack' ? '✅ ' : '❌ '}
                  {entry.text}
                </div>
              ))}
            </div>
          )}

          {/* ── Active Command Bar (Phase 11) ── */}
          <div style={{
            display: 'flex', gap: '8px', padding: '16px',
            background: '#0a0f18', borderTop: '1px solid rgba(100,116,139,0.2)'
          }}>
            <span style={{ fontSize: '20px', display: 'flex', alignItems: 'center' }}>⚡</span>
            <input 
              type="text"
              placeholder="@Operator command / directives..."
              value={operatorCmd}
              onChange={e => setOperatorCmd(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendOperatorCmd()}
              disabled={isExecutingCmd && !operatorCmd.toLowerCase().startsWith('@operator') && !operatorCmd.toLowerCase().startsWith('operator')}
              style={{
                  flex: 1, background: '#1e293b', border: '1px solid #475569',
                  color: '#f8fafc', padding: '12px 16px', borderRadius: '8px',
                  fontSize: '14px', fontFamily: 'JetBrains Mono, monospace'
              }}
            />
            <button 
              onClick={sendOperatorCmd}
              disabled={(!operatorCmd.trim() || isSendingCmd) || (isExecutingCmd && !operatorCmd.toLowerCase().startsWith('@operator') && !operatorCmd.toLowerCase().startsWith('operator'))}
              style={{
                background: operatorCmd.trim() ? 'linear-gradient(135deg, #10b981, #059669)' : '#334155',
                color: 'white', border: 'none', padding: '0 24px', borderRadius: '8px',
                fontWeight: 'bold', cursor: operatorCmd.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              {isSendingCmd ? '...' : 'DISPATCH'}
            </button>
          </div>
        </div>

        {/* ── Right: Controls ── */}
        <div style={styles.controlPanel}>
          {/* Persuasion Meter */}
          <div style={styles.meterCard}>
            <h3 style={styles.meterTitle}>Persuasion Meter</h3>
            <p style={styles.meterSub}>Critic's Agreement Level</p>

            <div style={styles.meterGauge}>
              <div style={styles.meterTrack}>
                <div style={{
                  ...styles.meterFill,
                  width: `${(persuasion / 10) * 100}%`,
                  background: `linear-gradient(90deg, #ef4444, ${getMeterColor(persuasion)})`,
                  boxShadow: `0 0 12px ${getMeterColor(persuasion)}40`,
                }} />
                {/* Threshold marker at 9.5 */}
                <div style={styles.thresholdMarker} title="Threshold: 9.5/10" />
              </div>
              <div style={styles.meterLabels}>
                {[1,2,3,4,5,6,7,8,9,10].map(n => (
                  <span key={n} style={{
                    ...styles.meterTick,
                    color: n <= persuasion ? getMeterColor(persuasion) : '#334155',
                    fontWeight: n === persuasion ? 700 : 400,
                  }}>{n}</span>
                ))}
              </div>
            </div>

            <div style={styles.meterScore}>
              <span style={{ fontSize: '42px', fontWeight: 800, color: getMeterColor(persuasion) }}>{persuasion}</span>
              <span style={{ fontSize: '18px', color: '#64748b' }}>/10</span>
            </div>
            <span style={{ ...styles.meterStatus, color: getMeterColor(persuasion) }}>
              {getMeterLabel(persuasion)}
            </span>
            <div style={{ fontSize: '10px', color: '#475569', marginTop: '6px' }}>
              Threshold: 9.5 | {persuasion >= 9.5 ? '✅ Approved' : `Gap: ${(9.5 - persuasion).toFixed(1)}`}
            </div>
          </div>

          {/* Active Challenge Card (Phase 3) */}
          {activeChallenge && (
            <div style={styles.challengeCard}>
              <div style={styles.challengeHeader}>
                <span style={{ fontSize: '16px' }}>🛑</span>
                <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '12px', letterSpacing: '0.5px' }}>STRATEGIC PAUSE</span>
                <span style={styles.challengeId}>{activeChallenge.challenge_id}</span>
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8', margin: '8px 0' }}>
                Score: {activeChallenge.score}/{activeChallenge.threshold} (Gap: {activeChallenge.gap})
              </div>
              {activeChallenge.weaknesses && activeChallenge.weaknesses.map((w, i) => (
                <div key={i} style={styles.weaknessItem}>
                  <div style={styles.weaknessHeader}>
                    <span style={{
                      ...styles.severityBadge,
                      background: `${SEVERITY_COLORS[w.severity] || '#eab308'}20`,
                      color: SEVERITY_COLORS[w.severity] || '#eab308',
                    }}>{w.severity}</span>
                    <span style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 600 }}>{w.category}</span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: '#94a3b8', lineHeight: 1.5 }}>{w.challenge}</p>
                </div>
              ))}
              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '8px', fontStyle: 'italic' }}>
                Address these weaknesses below or Force Proceed.
              </div>
            </div>
          )}

          {/* ── Agent Progress Tracker ── */}
          {(workingAgents.length > 0 || consensusIteration) && (
            <div style={styles.agentTrackerContainer}>
              {/* Consensus Iteration Badge */}
              {consensusIteration && (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 14px', marginBottom: '8px', borderRadius: '10px',
                  background: consensusIteration.status === 'CONSENSUS'
                    ? 'rgba(16,185,129,0.15)'
                    : consensusIteration.status === 'MAX_REACHED'
                      ? 'rgba(239,68,68,0.15)'
                      : 'rgba(99,102,241,0.12)',
                  border: `1px solid ${
                    consensusIteration.status === 'CONSENSUS' ? 'rgba(16,185,129,0.3)'
                    : consensusIteration.status === 'MAX_REACHED' ? 'rgba(239,68,68,0.3)'
                    : 'rgba(99,102,241,0.25)'
                  }`,
                }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '0.5px' }}>
                    {consensusIteration.status === 'CONSENSUS' ? '✅ CONSENSUS' :
                     consensusIteration.status === 'MAX_REACHED' ? '🛑 MAX REACHED' :
                     '🔄 DELIBERATION'}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {Array.from({ length: consensusIteration.maxIterations }, (_, i) => (
                      <div key={i} style={{
                        width: '18px', height: '18px', borderRadius: '50%',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '9px', fontWeight: 700,
                        background: i < consensusIteration.iteration
                          ? (consensusIteration.status === 'CONSENSUS' ? '#10b981' : '#6366f1')
                          : 'rgba(255,255,255,0.06)',
                        color: i < consensusIteration.iteration ? '#fff' : '#475569',
                        border: i === consensusIteration.iteration - 1
                          ? '2px solid #f1f5f9'
                          : '1px solid rgba(100,116,139,0.15)',
                        transition: 'all 0.3s ease',
                      }}>{i + 1}</div>
                    ))}
                  </div>
                  <span style={{
                    fontSize: '11px', fontWeight: 600,
                    color: consensusIteration.status === 'CONSENSUS' ? '#10b981'
                      : consensusIteration.status === 'MAX_REACHED' ? '#ef4444' : '#a5b4fc'
                  }}>
                    {consensusIteration.iteration}/{consensusIteration.maxIterations}
                  </span>
                </div>
              )}
              {workingAgents.map((wa, idx) => {
                const style = AGENT_STYLES[wa.agent] || AGENT_STYLES['SYSTEM'];
                return (
                  <div key={idx} style={styles.agentTrackerCard}>
                    <div style={styles.agentTrackerHeader}>
                      <span style={{ fontSize: '16px', animation: 'agent-pulse-glow 1.5s infinite' }}>{style.icon}</span>
                      <span style={{ color: style.color, fontSize: '12px', fontWeight: 700, letterSpacing: '0.5px' }}>
                        {wa.agent} is executing task...
                      </span>
                    </div>
                    <div style={styles.agentTrackerBarBg}>
                      <div className="agent-progress-fill" style={{
                        ...styles.agentTrackerBarFill,
                        background: `linear-gradient(90deg, ${style.color}40, ${style.color})`,
                        boxShadow: `0 0 10px ${style.color}60`
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Intervention Box */}
          <div style={styles.interventionCard}>
            <h3 style={styles.interventionTitle}>
              {convinceMode ? '🏛️ Convince the Critic' : '⚡ Commander Intervention'}
            </h3>
            <p style={styles.interventionSub}>
              {convinceMode
                ? 'Present data & evidence to address the weaknesses above'
                : 'Convince the board or issue a Hard Override'}
            </p>
            <textarea
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendIntervention(); } }}
              placeholder={convinceMode
                ? 'Present your evidence: data, metrics, validated research...'
                : 'Present your argument to the board...'}
              style={{
                ...styles.interventionInput,
                ...(convinceMode ? { borderColor: 'rgba(239,68,68,0.4)', minHeight: '100px' } : {}),
              }}
              rows={convinceMode ? 5 : 4}
            />
            <div style={styles.interventionActions}>
              <button onClick={() => { if(inputText.trim()) setShowDispatchModal(true); }} style={{
                ...styles.btnPersuade,
                ...(convinceMode ? { background: 'linear-gradient(135deg, #22c55e, #16a34a)' } : {}),
              }} disabled={!inputText.trim()}>
                {convinceMode ? '✅ Submit Evidence' : '💬 Persuade'}
              </button>
              <button onClick={sendOverride} style={styles.btnOverride}>
                🚨 {convinceMode ? 'Force Proceed' : 'Hard Override'}
              </button>
            </div>
            {convinceMode && (
              <p style={{ fontSize: '10px', color: '#64748b', marginTop: '8px' }}>
                💡 Tip: Use data-driven language — "metrics show", "validated by", "A/B test results"
              </p>
            )}

            {/* UPGRADE V3.3: Phase Tracker & Handoff */}
            {ventureMode && eosState && (
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '16px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                  📈 Venture Progress
                </div>
                
                {['market', 'brand', 'legal', 'business_plan', 'financials', 'funding', 'pitch'].map(phase => {
                  const status = eosState.phase_status?.[phase] || 'pending';
                  const isLocked = status === 'locked';
                  return (
                    <div key={phase} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px', padding: '4px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                      <span style={{ textTransform: 'capitalize', color: '#cbd5e1' }}>{phase.replace('_', ' ')}</span>
                      <span style={{ 
                        color: isLocked ? '#10b981' : status === 'iterating' ? '#eab308' : status === 'deadlocked' ? '#ef4444' : '#64748b',
                        fontWeight: isLocked ? 700 : 400 
                      }}>
                        {isLocked ? '✅ Locked' : status === 'iterating' ? '🔄 Iterating' : status === 'deadlocked' ? '🚨 Deadlocked' : '⏳ Pending'}
                      </span>
                    </div>
                  );
                })}

                {eosState.phase_status?.market === 'locked' && 
                 eosState.phase_status?.brand === 'locked' && 
                 eosState.phase_status?.legal === 'locked' && 
                 eosState.phase_status?.business_plan === 'locked' && 
                 eosState.phase_status?.financials === 'locked' && (
                  <button 
                    onClick={() => onHandoff?.(eosState)}
                    style={{
                      width: '100%', padding: '12px', marginTop: '12px', borderRadius: '8px', border: 'none',
                      background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: 'white',
                      fontSize: '13px', fontWeight: 700, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                      boxShadow: '0 4px 14px rgba(34,197,94,0.3)', animation: 'pulse 2s infinite'
                    }}>
                    🚀 APPROVE PLAN & SEND TO BUILDER
                  </button>
                )}
              </div>
            )}

            {ventureMode && !convinceMode && (
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(100,116,139,0.15)', paddingTop: '16px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                  🚀 Venture Architect Commands
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <button onClick={() => triggerEosAction('/market')} style={styles.btnEos}>1. Market Intel</button>
                  <button onClick={() => triggerEosAction('/brand')} style={styles.btnEos}>2. Brand DNA</button>
                  <button onClick={() => triggerEosAction('/legal')} style={styles.btnEos}>3. Legal & IP</button>
                  <button onClick={() => triggerEosAction('/financials')} style={styles.btnEos}>4. Financials</button>
                  <button onClick={() => triggerEosAction('/business-plan')} style={styles.btnEos}>5. Business Plan</button>
                  <button onClick={() => triggerEosAction('/funding')} style={styles.btnEos}>6. Funding Strat</button>
                  <button onClick={() => triggerEosAction('/pitch')} style={{ ...styles.btnEos, gridColumn: 'span 2', background: 'rgba(244,63,94,0.1)', color: '#f43f5e', borderColor: 'rgba(244,63,94,0.3)' }}>
                    7. Validate & Export Start-Up Decks
                  </button>
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', marginTop: '8px', fontStyle: 'italic', lineHeight: 1.4 }}>
                  Click to execute EOS workstreams. Tell the CEO your company name and industry first.
                </div>
              </div>
            )}
          </div>

          {/* Active Agents */}
          <div style={styles.agentList}>
            <h4 style={styles.agentListTitle}>Board Members</h4>
            {Object.entries(AGENT_STYLES).filter(([k]) => k !== 'COMMANDER' && k !== 'SYSTEM').map(([name, s]) => (
              <div key={name} style={styles.agentItem}>
                <span style={{ fontSize: '18px' }}>{s.icon}</span>
                <span style={{ color: s.color, fontWeight: 600, fontSize: '13px' }}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Outcome Decision Modal ── */}
      {outcomeProposal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={{ fontSize: '48px', textAlign: 'center', marginBottom: '16px' }}>🎯</div>
            <h2 style={{ color: '#22c55e', margin: '0 0 8px', fontSize: '20px', textAlign: 'center' }}>CONSENSUS REACHED</h2>
            <p style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'center', marginBottom: '20px' }}>
              The board finalized <strong style={{ color: '#e2e8f0' }}>{outcomeProposal.summary?.deliverables_count || 0}</strong> deliverables
              for <strong style={{ color: '#e2e8f0' }}>{outcomeProposal.summary?.company_name}</strong>
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button onClick={() => handleOutcomeChoice('update')} style={{ ...styles.outcomeBtn, background: 'linear-gradient(135deg, #3b82f6, #6366f1)' }}>
                🔄 Update Existing Product
                <span style={{ display: 'block', fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>Merge deliverables into the current codebase</span>
              </button>
              <button onClick={() => handleOutcomeChoice('new')} style={{ ...styles.outcomeBtn, background: 'linear-gradient(135deg, #22c55e, #16a34a)' }}>
                🆕 Create New Product
                <span style={{ display: 'block', fontSize: '11px', opacity: 0.7, marginTop: '4px' }}>Spin up a fresh build from these deliverables</span>
              </button>
              <button onClick={() => handleOutcomeChoice('dismiss')} style={{ ...styles.outcomeBtn, background: 'rgba(100,116,139,0.2)', border: '1px solid rgba(100,116,139,0.3)' }}>
                📦 Dismiss — Archive for Later
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Implementation Plan Viewer ── */}
      {implementationPlan && (
        <div style={styles.modalOverlay}>
          <div style={{ ...styles.modalContent, maxWidth: '700px', maxHeight: '80vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ color: '#6366f1', margin: 0, fontSize: '18px' }}>📋 Implementation Plan ({implementationPlan.outcome_type?.toUpperCase()})</h2>
              <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}>{implementationPlan.project_name}</span>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '10px', padding: '16px', fontSize: '13px', color: '#cbd5e1', lineHeight: 1.7, whiteSpace: 'pre-wrap', fontFamily: 'Inter, sans-serif', maxHeight: '50vh', overflow: 'auto' }}>
              {implementationPlan.plan}
            </div>
            <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'center' }}>
              <button onClick={approvePlan} style={{ padding: '12px 32px', borderRadius: '10px', border: 'none', background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: 'white', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                ✅ Approve & Execute
              </button>
              <button onClick={rejectPlan} style={{ padding: '12px 32px', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.1)', color: '#ef4444', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                ❌ Reject & Revise
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Generating Plan Spinner ── */}
      {generatingPlan && (
        <div style={styles.modalOverlay}>
          <div style={{ ...styles.modalContent, textAlign: 'center', maxWidth: '400px' }}>
            <div style={{ fontSize: '48px', animation: 'pulse 2s infinite' }}>🧠</div>
            <h3 style={{ color: '#e2e8f0', margin: '12px 0 4px' }}>Generating Implementation Plan...</h3>
            <p style={{ color: '#64748b', fontSize: '12px' }}>Claude is analyzing the deliverables and structuring the plan.</p>
          </div>
        </div>
      )}
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
          <span style={{ fontSize: '48px', marginBottom: '16px' }}>⚡</span>
          <h3>Awaiting Project Context</h3>
          <p style={{ fontSize: '14px', maxWidth: '400px', textAlign: 'center' }}>
            To initialize the War Room dialogue, please select an active CMO campaign project from the dropdown.
          </p>
        </div>
      )}

      {/* ── DISPATCH MODAL ── */}
      {showDispatchModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '24px', width: '400px', fontFamily: 'Inter, sans-serif' }}>
            <h2 style={{ margin: '0 0 16px', color: '#f8fafc', fontSize: '18px' }}>🚀 Strategic Dispatch</h2>
            
            <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '8px' }}>Philosophy Intent:</p>
            <select 
              value={strategyMode} 
              onChange={e => setStrategyMode(e.target.value)}
              style={{ width: '100%', padding: '10px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', marginBottom: '16px' }}
            >
              <option value="balanced">⚖️ Balanced (Standard 7.0)</option>
              <option value="aggressive_growth">🚀 Aggressive Growth (Lowers gates to 6.0)</option>
              <option value="lean_mvp">🔬 Lean MVP (Raises gates to 8.0)</option>
              <option value="custom">✏️ Custom Directive</option>
            </select>
            
            {strategyMode === 'custom' && (
              <textarea 
                value={customDirective}
                onChange={e => setCustomDirective(e.target.value)}
                placeholder="Custom steering directive..."
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155', borderRadius: '6px', marginBottom: '16px', height: '60px' }}
              />
            )}
            
            <div style={{ background: stressTest ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.05)', border: `1px solid ${stressTest ? '#ef4444' : '#334155'}`, padding: '12px', borderRadius: '8px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => setStressTest(!stressTest)}>
              <div style={{ width: '20px', height: '20px', borderRadius: '4px', border: `2px solid ${stressTest ? '#ef4444' : '#64748b'}`, background: stressTest ? '#ef4444' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {stressTest && <span style={{ color: '#fff', fontSize: '14px' }}>✓</span>}
              </div>
              <div>
                <div style={{ color: stressTest ? '#ef4444' : '#f8fafc', fontWeight: 'bold', fontSize: '14px' }}>Execute Red Team Chaos Drill</div>
                <div style={{ color: '#64748b', fontSize: '11px' }}>Simulate a crisis scenario post-pipeline.</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '12px' }}>
              <button onClick={() => setShowDispatchModal(false)} style={{ flex: 1, padding: '12px', background: 'transparent', border: '1px solid #334155', color: '#cbd5e1', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold' }}>Cancel</button>
              <button onClick={executeDispatch} style={{ flex: 2, padding: '12px', background: stressTest ? 'linear-gradient(90deg, #ef4444, #dc2626)' : 'linear-gradient(90deg, #3b82f6, #2563eb)', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer', fontWeight: 'bold', animation: stressTest ? 'pulsePhase 1.5s infinite' : 'none' }}>
                {stressTest ? 'LAUNCH DRILL 🔴' : 'AUTHORIZE DISPATCH 🚀'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── WISDOM VAULT SIDEBAR ── */}
      {showWisdomVault && (
        <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: '450px', background: '#0a0e17', borderLeft: '1px solid #1e293b', zIndex: 9999, display: 'flex', flexDirection: 'column', fontFamily: 'Inter, sans-serifOuter', boxShadow: '-10px 0 30px rgba(0,0,0,0.5)' }}>
          <div style={{ padding: '20px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ margin: 0, color: '#f8fafc', fontSize: '18px' }}>💡 Wisdom Vault</h2>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>Cross-Project Intelligence Memory</span>
            </div>
            <button onClick={() => setShowWisdomVault(false)} style={{ background: 'transparent', border: 'none', color: '#ef4444', fontSize: '24px', cursor: 'pointer' }}>×</button>
          </div>
          
          <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
            <h3 style={{ color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #334155', paddingBottom: '8px', marginBottom: '16px' }}>PENDING PROPOSALS ({pendingStandards.length})</h3>
            {wisdomLoading ? <div style={{ color: '#64748b' }}>Refreshing Vault...</div> : null}
            
            {pendingStandards.map(std => (
              <div key={std.standard_id} style={{ background: '#1e293b', border: '1px solid #3b82f6', borderRadius: '8px', padding: '14px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ background: '#3b82f620', color: '#60a5fa', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{std.domain.toUpperCase()}</span>
                  <span style={{ background: '#10b98120', color: '#34d399', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{(std.confidence * 100).toFixed(0)}% CONFIDENCE</span>
                </div>
                <h4 style={{ margin: '0 0 8px', color: '#f8fafc', fontSize: '14px' }}>{std.title}</h4>
                <p style={{ margin: '0 0 12px', color: '#cbd5e1', fontSize: '12px', lineHeight: 1.4 }}>{std.insight}</p>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => approveStandard(std.standard_id)} style={{ flex: 1, padding: '8px', background: '#22c55e', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>APPROVE AS LAW</button>
                  <button onClick={() => rejectStandard(std.standard_id)} style={{ flex: 1, padding: '8px', background: '#ef4444', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>REJECT</button>
                </div>
              </div>
            ))}
            {pendingStandards.length === 0 && !wisdomLoading && <div style={{ color: '#64748b', fontSize: '12px', marginBottom: '24px' }}>No new proposals from the C-Suite.</div>}

            <h3 style={{ color: '#e2e8f0', fontSize: '14px', borderBottom: '1px solid #334155', paddingBottom: '8px', marginTop: '32px', marginBottom: '16px' }}>ACTIVE CORPORATE STANDARDS ({activeStandards.length})</h3>
            {activeStandards.map(std => (
              <div key={std.standard_id} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '14px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ background: 'rgba(255,255,255,0.05)', color: '#94a3b8', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>{std.domain.toUpperCase()}</span>
                </div>
                <h4 style={{ margin: '0 0 8px', color: '#cbd5e1', fontSize: '13px' }}>{std.title}</h4>
                <p style={{ margin: 0, color: '#64748b', fontSize: '11px', lineHeight: 1.4 }}>{std.insight}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  STYLES
// ═══════════════════════════════════════════════════════════
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 140px)',
    borderRadius: '14px',
    overflow: 'hidden',
    background: 'rgba(10, 14, 23, 0.6)',
    border: '1px solid rgba(100,116,139,0.15)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.06))',
    borderBottom: '1px solid rgba(100,116,139,0.15)',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: '12px' },
  headerIcon: { fontSize: '28px' },
  headerTitle: { margin: 0, fontSize: '18px', fontWeight: 700, color: '#f1f5f9', letterSpacing: '-0.3px' },
  headerSub: { fontSize: '12px', color: '#64748b' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '8px' },
  statusDot: { width: '8px', height: '8px', borderRadius: '50%' },
  statusText: { fontSize: '11px', fontWeight: 600, letterSpacing: '1px', color: '#94a3b8' },
  pauseBadge: {
    padding: '3px 10px', borderRadius: '6px', fontSize: '10px', fontWeight: 700,
    background: 'rgba(239,68,68,0.15)', color: '#ef4444', letterSpacing: '0.5px',
    animation: 'pulse 2s infinite',
  },

  body: { display: 'flex', flex: 1, overflow: 'hidden' },

  // ── Feed Panel ──
  feedPanel: { flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(100,116,139,0.12)' },
  topicBar: {
    display: 'flex', gap: '8px', padding: '12px 16px',
    borderBottom: '1px solid rgba(100,116,139,0.1)',
    background: 'rgba(15,23,42,0.4)',
    flexWrap: 'wrap',
  },
  topicInput: {
    flex: 1, padding: '8px 14px', borderRadius: '8px',
    border: '1px solid rgba(100,116,139,0.2)', background: 'rgba(0,0,0,0.3)',
    color: '#e2e8f0', fontSize: '13px', outline: 'none',
    fontFamily: 'Inter, sans-serif',
  },
  topicBtn: {
    padding: '8px 16px', borderRadius: '8px', border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', color: 'white',
    fontSize: '12px', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
    fontFamily: 'Inter, sans-serif',
  },
  feed: {
    flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px',
    display: 'flex', flexDirection: 'column', gap: '8px',
  },
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', textAlign: 'center',
  },

  // ── Messages ──
  message: {
    padding: '12px 16px', borderRadius: '10px',
    transition: 'all 0.2s',
  },
  msgHeader: {
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px',
  },
  msgIcon: { fontSize: '16px' },
  msgAgent: { fontWeight: 700, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' },
  msgTime: { fontSize: '10px', color: '#475569', marginLeft: 'auto' },
  userBadge: {
    padding: '1px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: 700,
    background: 'rgba(249,115,22,0.2)', color: '#f97316', letterSpacing: '0.5px',
  },
  msgText: { margin: 0, fontSize: '13.5px', lineHeight: 1.6, color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' },

  // ── Control Panel ──
  controlPanel: {
    width: '320px', display: 'flex', flexDirection: 'column', gap: '0',
    background: 'rgba(15,23,42,0.3)', overflowY: 'auto',
  },

  // ── Meter ──
  meterCard: {
    padding: '24px 20px', textAlign: 'center',
    borderBottom: '1px solid rgba(100,116,139,0.12)',
  },
  meterTitle: { margin: 0, fontSize: '15px', fontWeight: 700, color: '#f1f5f9' },
  meterSub: { margin: '4px 0 20px', fontSize: '11px', color: '#64748b' },
  meterGauge: { marginBottom: '12px' },
  meterTrack: {
    height: '8px', borderRadius: '4px', background: 'rgba(100,116,139,0.15)',
    overflow: 'visible', marginBottom: '8px', position: 'relative',
  },
  meterFill: {
    height: '100%', borderRadius: '4px', transition: 'width 0.6s ease, background 0.6s ease',
  },
  thresholdMarker: {
    position: 'absolute', top: '-3px', left: '95%',
    width: '2px', height: '14px', background: '#f1f5f9',
    borderRadius: '1px', opacity: 0.6,
  },
  meterLabels: { display: 'flex', justifyContent: 'space-between', padding: '0 2px' },
  meterTick: { fontSize: '10px', fontFamily: 'JetBrains Mono, monospace', transition: 'color 0.3s' },
  meterScore: { display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: '2px', margin: '8px 0 4px' },
  meterStatus: { fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1.5px' },

  // ── Challenge Card (Phase 3) ──
  challengeCard: {
    margin: '0', padding: '16px 20px',
    background: 'rgba(239,68,68,0.05)',
    borderBottom: '1px solid rgba(239,68,68,0.15)',
    borderTop: '1px solid rgba(239,68,68,0.15)',
  },
  challengeHeader: {
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px',
  },
  challengeId: {
    marginLeft: 'auto', fontSize: '10px', fontFamily: 'JetBrains Mono, monospace',
    color: '#475569', background: 'rgba(0,0,0,0.2)', padding: '2px 6px', borderRadius: '4px',
  },
  weaknessItem: {
    padding: '8px 10px', marginTop: '6px', borderRadius: '8px',
    background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(100,116,139,0.1)',
  },
  weaknessHeader: {
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  severityBadge: {
    padding: '1px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: 700,
    letterSpacing: '0.5px',
  },

  // ── Intervention ──
  interventionCard: {
    padding: '20px',
    borderBottom: '1px solid rgba(100,116,139,0.12)',
  },
  interventionTitle: { margin: 0, fontSize: '14px', fontWeight: 700, color: '#f1f5f9' },
  interventionSub: { margin: '4px 0 12px', fontSize: '11px', color: '#64748b' },
  interventionInput: {
    width: '100%', padding: '10px 14px', borderRadius: '10px',
    border: '1px solid rgba(100,116,139,0.2)', background: 'rgba(0,0,0,0.3)',
    color: '#e2e8f0', fontSize: '13px', resize: 'none', outline: 'none',
    fontFamily: 'Inter, sans-serif', lineHeight: 1.5, boxSizing: 'border-box',
  },
  interventionActions: { display: 'flex', gap: '8px', marginTop: '10px' },
  btnPersuade: {
    flex: 1, padding: '10px', borderRadius: '8px', border: 'none',
    background: 'linear-gradient(135deg, #3b82f6, #6366f1)', color: 'white',
    fontSize: '13px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif',
    opacity: 1, transition: 'opacity 0.2s',
  },
  btnOverride: {
    padding: '10px 16px', borderRadius: '8px',
    border: '1px solid rgba(239,68,68,0.4)', background: 'rgba(239,68,68,0.1)',
    color: '#ef4444', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif',
  },

  // ── Agent List ──
  agentList: { padding: '16px 20px' },
  agentListTitle: { margin: '0 0 10px', fontSize: '12px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' },
  agentItem: {
    display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0',
  },

  // ── Agent Progress Tracker ──
  agentTrackerContainer: {
    padding: '16px 20px',
    borderBottom: '1px solid rgba(100,116,139,0.12)',
    background: 'rgba(15, 23, 42, 0.4)',
    display: 'flex', flexDirection: 'column', gap: '12px'
  },
  agentTrackerCard: {
    display: 'flex', flexDirection: 'column', gap: '8px',
    background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '10px',
    border: '1px solid rgba(100,116,139,0.15)',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
  },
  agentTrackerHeader: {
    display: 'flex', alignItems: 'center', gap: '8px'
  },
  agentTrackerBarBg: {
    height: '4px', width: '100%', background: 'rgba(255,255,255,0.05)',
    borderRadius: '2px', overflow: 'hidden'
  },
  agentTrackerBarFill: {
    height: '100%', borderRadius: '2px',
  },

  // ── EOS Buttons ──
  btnEos: {
    padding: '8px', borderRadius: '6px',
    border: '1px solid rgba(148,163,184,0.2)', background: 'rgba(0,0,0,0.2)',
    color: '#cbd5e1', fontSize: '11px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', textAlign: 'center',
    transition: 'all 0.2s',
  },

  // ── Modals ──
  modalOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
    backdropFilter: 'blur(8px)',
  },
  modalContent: {
    background: 'linear-gradient(135deg, #1e1b3a, #0f172a)',
    border: '1px solid rgba(99,102,241,0.3)', borderRadius: '16px',
    padding: '32px', maxWidth: '480px', width: '90%',
  },
  outcomeBtn: {
    width: '100%', padding: '14px 20px', borderRadius: '10px', border: 'none',
    color: 'white', fontSize: '14px', fontWeight: 600, cursor: 'pointer',
    fontFamily: 'Inter, sans-serif', textAlign: 'center',
  },
};
