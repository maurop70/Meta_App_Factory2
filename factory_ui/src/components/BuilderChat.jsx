import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ClaudeAYStatus from './ClaudeAYStatus';

// --- ARCHITECTURAL INJECTION: INTELLIGENCE PARSER ---
const EvaluationScorecard = ({ data }) => {
  if (!data || !data.verdict || !data.gate) return <div className="text-gray-400">Malformed intelligence payload.</div>;

  const { verdict, gate } = data;
  const isChallenged = gate.gate_result === 'CHALLENGED';
  
  return (
    <div className="flex flex-col space-y-4 w-full mt-3">
      <div className={`grid grid-cols-2 gap-4 p-4 border rounded-xl shadow-lg transition-all ${isChallenged ? 'bg-red-950/20 border-red-500/40' : 'bg-emerald-950/20 border-emerald-500/40'}`}>
        <div className="flex flex-col">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Gate Threshold Status</span>
          <span className={`text-xl font-bold tracking-wide mt-1 ${isChallenged ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`}>
            {gate.gate_result} [{gate.status}]
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Composite Matrix Score</span>
          <span className={`text-3xl font-bold mt-1 ${verdict.composite_score < 80 ? 'text-orange-400' : 'text-emerald-400'}`}>
            {verdict.composite_score}/100
          </span>
        </div>
      </div>

      {gate.weaknesses && gate.weaknesses.length > 0 && (
        <div className="flex flex-col space-y-3 mt-4">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400 border-b border-slate-700 pb-1">Identified Structural Vulnerabilities</span>
          {gate.weaknesses.map((weakness, idx) => (
            <div key={idx} className="p-4 bg-slate-900/90 border border-slate-700 hover:border-orange-500/50 rounded-lg transition-all shadow-md">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-bold text-orange-400 tracking-wide">{weakness.category}</span>
                <span className="text-[10px] font-mono px-2 py-1 bg-orange-950/50 text-orange-300 rounded border border-orange-800/50 uppercase">{weakness.severity}</span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed font-mono">{weakness.challenge}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default function BuilderChat() {
  const [chatHistory, setChatHistory] = useState(() => {
    try {
      const stored = sessionStorage.getItem('ma_chat_history');
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      return [];
    }
  });
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [cachedDocumentIds, setCachedDocumentIds] = useState(() => {
    try {
      const stored = sessionStorage.getItem('ma_cached_document_ids');
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      return [];
    }
  });
  const [isUploading, setIsUploading] = useState(false);
  const [socraticChallenge, setSocraticChallenge] = useState(null);
  const [evidenceText, setEvidenceText] = useState('');
  const [isSocraticSubmitting, setIsSocraticSubmitting] = useState(false);
  const [lastPrompt, setLastPrompt] = useState("");
  const [isMaximized, setIsMaximized] = useState(false);
  const [swarmOpen, setSwarmOpen] = useState(false);
  const [systemAgents, setSystemAgents] = useState([]);

  const fetchSystemRegistry = async () => {
    try {
      const res = await fetch('/api/system/registry');
      if (res.ok) {
        const data = await res.json();
        setSystemAgents(data.agents || []);
      }
    } catch (e) {
      console.error("Failed to load system registry:", e);
    }
  };

  useEffect(() => {
    fetchSystemRegistry();
    const interval = setInterval(fetchSystemRegistry, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const es = new EventSource('/api/bridge/stream');

    es.onopen = () => {
      console.log("IPC Bridge EventSource stream connection successfully opened.");
    };

    es.onerror = (err) => {
      console.warn("IPC Bridge EventSource error:", err);
    };

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'strategic_pause') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `⚠️ [STRATEGIC PAUSE] Operator review required.`,
            blueprint_file: data.blueprint_file,
            is_pause_actionable: true,
            agent: 'UNKNOWN'
          }]);
        } else if (data.type === 'strategic_approval') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `✅ [STRATEGIC APPROVAL] Blueprint approved. Actuating execution: ${data.blueprint_file}`,
            agent: 'UNKNOWN'
          }]);
        } else if (data.type === 'strategic_rejection') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `❌ [STRATEGIC REJECTION] Blueprint execution rejected and deleted: ${data.blueprint_file}`,
            agent: 'UNKNOWN'
          }]);
        } else if (data.type === 'execution_start') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `⚙️ [IPC BRIDGE] Actuating execution for: ${data.blueprint_file}\n`,
            agent: 'IPC_BRIDGE_SYSTEM'
          }]);
        } else if (data.type === 'agent_stream' && (data.emitter === 'IPC_BRIDGE_STDOUT' || data.emitter === 'IPC_BRIDGE_STDERR')) {
          setChatHistory(prev => {
            const newHistory = [...prev];
            const lastMsg = newHistory[newHistory.length - 1];
            if (lastMsg && lastMsg.agent === 'IPC_BRIDGE_SYSTEM') {
              lastMsg.content += data.content;
            } else {
              newHistory.push({
                role: 'system',
                content: data.content,
                agent: 'IPC_BRIDGE_SYSTEM'
              });
            }
            return newHistory;
          });
        } else if (data.type === 'circuit_breaker') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `🚨 [CIRCUIT BREAKER TRIGGERED] Execution halted for: ${data.blueprint_file}\n\nError:\n${data.error}`,
            agent: 'UNKNOWN'
          }]);
        } else if (data.type === 'execution_success') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `✅ [EXECUTION SUCCESS] Subprocess completed successfully: ${data.blueprint_file}`,
            agent: 'UNKNOWN'
          }]);
        }
      } catch (e) {
        console.error("Error parsing IPC Bridge stream event:", e);
      }
    };

    return () => {
      es.close();
    };
  }, []);

  useEffect(() => {
    const telemetryEs = new EventSource('/api/telemetry/stream');

    telemetryEs.onopen = () => {
      console.log("Telemetry EventSource stream connection successfully opened.");
    };

    telemetryEs.onerror = (err) => {
      console.warn("Telemetry EventSource error:", err);
    };

    telemetryEs.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.status === 'executing') {
          setChatHistory(prev => [...prev, { role: 'system', content: `⚙️ [AY2 DAEMON] Ingesting patch blueprint for '${data.file}'...`, agent: 'UNKNOWN' }]);
        } else if (data.status === 'success') {
          setChatHistory(prev => [...prev, { role: 'system', content: `✅ [AY2 DAEMON SUCCESS] Successfully applied AST splice to '${data.file}'`, agent: 'UNKNOWN' }]);
        } else if (data.status === 'failed') {
          setChatHistory(prev => [...prev, { role: 'system', content: `❌ [AY2 DAEMON FAILED] Validation failed for '${data.file}'. Changes rolled back.`, agent: 'UNKNOWN' }]);
        } else if (data.type === 'claudeay_fix_proposal') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: JSON.stringify({
              fix_id: data.fix_id,
              diagnosis: data.diagnosis,
              error_count: data.error_count,
            }),
            agent: 'CLAUDEAY_PROPOSAL',
            is_claudeay_proposal: true,
          }]);
        } else if (data.type === 'claudeay_fix_executing') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `⚙️ [CLAUDEAY] Executing approved fix ${data.fix_id}...`,
            agent: 'UNKNOWN'
          }]);
        } else if (data.type === 'claudeay_fix_dismissed') {
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `🚫 [CLAUDEAY] Fix proposal ${data.fix_id} dismissed.`,
            agent: 'UNKNOWN'
          }]);
        }
      } catch (e) {
        console.error("Telemetry parse failed:", e);
      }
    };

    return () => {
      telemetryEs.close();
    };
  }, []);

  useEffect(() => {
    if (!swarmOpen) return;
    const close = (e) => {
      if (!e.target.closest('.swarm-pill-wrapper')) setSwarmOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [swarmOpen]);

  const abortControllerRef = useRef(null);

  const handleNewThread = () => {
    setChatHistory([]);
    setAttachments([]);
    setCachedDocumentIds([]);
    setInput('');
    setSocraticChallenge(null);
    setEvidenceText('');
    sessionStorage.clear();
    setChatHistory([{
      role: 'system',
      content: '> TERMINAL RESET: Context flushed. Ready for new architectural directives.',
      document_ids: [],
      agent: 'UNKNOWN'
    }]);
  };

  const handleHalt = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
      setChatHistory(prev => [...prev, {
        role: 'system',
        content: '🛑 [HALT & INTERVENE] Stream severed by Commander command. Secure input unlocked.',
        document_ids: []
      }]);
    }
  };

  const submitSocraticEvidence = async (challengeId, evidenceText) => {
    if (!evidenceText.trim()) return;
    setIsSocraticSubmitting(true);
    try {
      const res = await fetch('/api/challenge/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: challengeId,
          evidence: evidenceText
        })
      });
      if (!res.ok) throw new Error("Evaluation endpoint failed");
      const data = await res.json();
      
      setChatHistory(prev => [...prev, {
        role: 'system',
        content: `⚖️ [Critic Verdict] Verdict: ${data.verdict} | Combined Score: ${data.combined_score}/10.0\n${data.message}`,
        document_ids: []
      }]);
      
      if (data.verdict === 'CONVINCED') {
        setSocraticChallenge(null);
        setEvidenceText('');
      }
    } catch (e) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[CRITIC ERROR] ${e.message}`, document_ids: [] }]);
    } finally {
      setIsSocraticSubmitting(false);
    }
  };

  const submitSocraticOverride = async (challengeId) => {
    setIsSocraticSubmitting(true);
    const overrideReason = prompt("Enter override authorization code or justification:") || "Commander Override";
    
    if (!lastPrompt || !lastPrompt.trim()) {
      alert("Commander Error: No original mandate found to override. Aborting.");
      setIsSocraticSubmitting(false);
      return;
    }

    try {
      const res = await fetch('/api/challenge/override', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_id: challengeId,
          reason: overrideReason,
          original_mandate: lastPrompt
        })
      });
      
      if (res.ok || res.status === 404) {
        if (res.status === 404) {
          console.warn("[COMMANDER OVERRIDE ANOMALY] Backend challenge state not found or corrupted (404). Forcefully unlocking viewport.");
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `🚨 [COMMANDER OVERRIDE ANOMALY] Backend challenge state not found or corrupted (404). Forcefully unlocking viewport. Justification: ${overrideReason}`,
            document_ids: []
          }]);
        } else {
          const data = await res.json();
          setChatHistory(prev => [...prev, {
            role: 'system',
            content: `🚨 [COMMANDER OVERRIDE] Risk level: ${data.risk_level.toUpperCase()}\n${data.risk_description}\nJustification: ${overrideReason}`,
            document_ids: []
          }]);
        }
        setSocraticChallenge(null);
        setEvidenceText('');
      } else {
        throw new Error(`Override request failed with status ${res.status}`);
      }
    } catch (e) {
      console.error("[COMMANDER OVERRIDE ERROR]", e);
      // Forcefully unlock in case of exception to ensure viewport is never bricked
      setSocraticChallenge(null);
      setEvidenceText('');
      setChatHistory(prev => [...prev, { role: 'system', content: `[OVERRIDE WARNING] ${e.message}. Viewport forcefully unlocked.`, document_ids: [] }]);
    } finally {
      setIsSocraticSubmitting(false);
    }
  };

  useEffect(() => {
    try {
      sessionStorage.setItem('ma_chat_history', JSON.stringify(chatHistory));
    } catch (e) {
      console.error("Error setting sessionStorage for chatHistory", e);
    }
  }, [chatHistory]);

  useEffect(() => {
    try {
      sessionStorage.setItem('ma_cached_document_ids', JSON.stringify(cachedDocumentIds));
    } catch (e) {
      console.error("Error setting sessionStorage for cachedDocumentIds", e);
    }
  }, [cachedDocumentIds]);

  const handleBridgeApprove = async (blueprintFile, msgIndex) => {
    try {
      const res = await fetch('/api/bridge/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blueprint_file: blueprintFile })
      });
      if (res.ok) {
        setChatHistory(prev => {
          const newHistory = [...prev];
          if (newHistory[msgIndex]) {
            newHistory[msgIndex].is_pause_actionable = false;
            newHistory[msgIndex].content += " (APPROVED)";
          }
          return newHistory;
        });
      } else {
        const errorData = await res.json();
        alert(`Approval failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Approval connection failed: ${e.message}`);
    }
  };

  const handleBridgeReject = async (blueprintFile, msgIndex) => {
    try {
      const res = await fetch('/api/bridge/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blueprint_file: blueprintFile })
      });
      if (res.ok) {
        setChatHistory(prev => {
          const newHistory = [...prev];
          if (newHistory[msgIndex]) {
            newHistory[msgIndex].is_pause_actionable = false;
            newHistory[msgIndex].content += " (REJECTED)";
          }
          return newHistory;
        });
      } else {
        const errorData = await res.json();
        alert(`Rejection failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Rejection connection failed: ${e.message}`);
    }
  };
  
  const terminalEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleFileUpload = async (e) => {
    // STRICT BINARY EXTRACTION: Isolate the single file from the array
    const uploadedFile = e.target.files[0];
    if (!uploadedFile) return;

    setIsUploading(true);
    const formData = new FormData();
    
    // DO NOT APPEND e.target.files. Append strictly the isolated 'uploadedFile'
    formData.append('file', uploadedFile);

    try {
      const res = await fetch('/api/ingest/document', {
        method: 'POST',
        body: formData
      });
      
      if (!res.ok) {
        let rawException = "Unknown backend fracture";
        try {
            const errorData = await res.json();
            rawException = JSON.stringify(errorData);
        } catch (parseError) {
            rawException = await res.text() || res.statusText;
        }
        throw new Error(`HTTP ${res.status} | PAYLOAD: ${rawException}`);
      }
      
      const data = await res.json();
      setAttachments(prev => [...prev, data]);
      setCachedDocumentIds(prev => Array.from(new Set([...prev, data.document_id])));
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[INGESTION FRACTURE] ${error.message}` }]);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = null;
    }
  };

  const removeAttachment = (idToRemove) => {
    setAttachments(prev => prev.filter(att => att.document_id !== idToRemove));
    setCachedDocumentIds(prev => prev.filter(id => id !== idToRemove));
  };

  const handleSynthesize = async () => {
    if ((!input.trim() && attachments.length === 0) || isStreaming) return;
    
    setLastPrompt(input);
    const userMsg = input;
    const currentAttachments = [...attachments];
    const newDocIds = currentAttachments.map(a => a.document_id);
    const updatedCachedDocIds = Array.from(new Set([...cachedDocumentIds, ...newDocIds]));
    
    // Construct serialized history payload tracking document_ids associated with specific turns
    const serializedHistory = chatHistory
      .filter(msg => msg.content && !msg.content.startsWith('[INGESTION FRACTURE]') && !msg.content.startsWith('[STREAM FRACTURE]'))
      .map(msg => ({
        role: msg.role === 'user' ? 'user' : 'model',
        content: msg.content,
        document_ids: msg.document_ids || []
      }));

    setChatHistory(prev => [...prev, { role: 'user', content: userMsg || '[ATTACHED PAYLOAD TRANSMITTED]', document_ids: newDocIds }]);
    setInput('');
    setAttachments([]);
    setCachedDocumentIds(updatedCachedDocIds);
    setIsStreaming(true);
    
    const controller = new AbortController();
    abortControllerRef.current = controller;
    
    try {
      const response = await fetch('/api/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({ 
          description: userMsg || "Evaluate attached documents.", 
          prompt: userMsg || "Evaluate attached documents.",
          document_ids: updatedCachedDocIds,
          history: serializedHistory
        })
      });
      
      if (!response.body) throw new Error("No readable stream");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      setChatHistory(prev => [...prev, { role: 'system', content: '', document_ids: [], agent: 'UNKNOWN' }]);
      
      let agentType = 'UNKNOWN';
      let streamBuffer = '';
      let localBlocks = [];

      while (true) {
        const { done, value } = await reader.read();
        if (value) {
          streamBuffer += decoder.decode(value, { stream: true });
        }
        
        let lastNewlineIdx = streamBuffer.lastIndexOf('\n');
        if (lastNewlineIdx !== -1) {
          const completeLines = streamBuffer.slice(0, lastNewlineIdx);
          streamBuffer = streamBuffer.slice(lastNewlineIdx + 1);
          
          const lines = completeLines.split('\n');
          for (const line of lines) {
            if (!line.trim()) continue;
            
            let cleanLine = line;
            if (cleanLine.startsWith('data: ')) {
              cleanLine = cleanLine.slice(6);
            }
            
            try {
              const parsed = JSON.parse(cleanLine.trim());
              
              if (parsed.event === 'compile_success' || parsed.event === 'ontology_ready') {
                fetchSystemRegistry();
              }

              if (parsed.type === 'agent_identity' && parsed.agent) {
                agentType = parsed.agent;
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  newHistory[newHistory.length - 1].agent = parsed.agent;
                  return newHistory;
                });
              } else if (parsed.type === 'agent_stream') {
                const { emitter, content: token } = parsed;
                if (agentType === 'EXECUTIVE_ARCHITECT') {
                  setChatHistory(prev => {
                    const newHistory = [...prev];
                    newHistory[newHistory.length - 1].content += token;
                    return newHistory;
                  });
                } else {
                  if (localBlocks.length > 0 && localBlocks[localBlocks.length - 1].emitter === emitter) {
                    localBlocks[localBlocks.length - 1].content += token;
                  } else {
                    localBlocks.push({ emitter, content: token });
                  }
                  
                  setChatHistory(prev => {
                    const newHistory = [...prev];
                    const lastMsg = newHistory[newHistory.length - 1];
                    let blocks = [];
                    try {
                      blocks = JSON.parse(lastMsg.content);
                      if (!Array.isArray(blocks)) blocks = [];
                    } catch (e) {
                      blocks = [];
                    }
                    if (blocks.length > 0 && blocks[blocks.length - 1].emitter === emitter) {
                      blocks[blocks.length - 1].content += token;
                    } else {
                      blocks.push({ emitter, content: token });
                    }
                    lastMsg.content = JSON.stringify(blocks);
                    return newHistory;
                  });
                }
              } else if (parsed.type === 'socratic_pause') {
                setSocraticChallenge(parsed);
              }
            } catch (e) {
              if (agentType === 'EXECUTIVE_ARCHITECT') {
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  newHistory[newHistory.length - 1].content += line;
                  return newHistory;
                });
              } else {
                console.error("[SSE FRACTURE] Failed to parse line:", line, e);
              }
            }
          }
        }
        if (done) break;
      }
      
      // Flush remaining stream buffer
      if (streamBuffer.trim()) {
        let cleanLine = streamBuffer.trim();
        if (cleanLine.startsWith('data: ')) {
          cleanLine = cleanLine.slice(6);
        }
        try {
          const parsed = JSON.parse(cleanLine);
          if (parsed.type === 'agent_stream') {
            const { emitter, content: token } = parsed;
            if (agentType === 'EXECUTIVE_ARCHITECT') {
              setChatHistory(prev => {
                const newHistory = [...prev];
                newHistory[newHistory.length - 1].content += token;
                return newHistory;
              });
            } else {
              if (localBlocks.length > 0 && localBlocks[localBlocks.length - 1].emitter === emitter) {
                localBlocks[localBlocks.length - 1].content += token;
              } else {
                localBlocks.push({ emitter, content: token });
              }
              setChatHistory(prev => {
                const newHistory = [...prev];
                const lastMsg = newHistory[newHistory.length - 1];
                let blocks = [];
                try {
                  blocks = JSON.parse(lastMsg.content);
                  if (!Array.isArray(blocks)) blocks = [];
                } catch (e) {
                  blocks = [];
                }
                if (blocks.length > 0 && blocks[blocks.length - 1].emitter === emitter) {
                  blocks[blocks.length - 1].content += token;
                } else {
                  blocks.push({ emitter, content: token });
                }
                lastMsg.content = JSON.stringify(blocks);
                return newHistory;
              });
            }
          }
        } catch (e) {
          if (agentType === 'EXECUTIVE_ARCHITECT') {
            setChatHistory(prev => {
              const newHistory = [...prev];
              newHistory[newHistory.length - 1].content += streamBuffer;
              return newHistory;
            });
          } else {
            console.error("[SSE FRACTURE] Failed to parse remaining buffer:", streamBuffer, e);
          }
        }
      }

      // Check for physical software blueprint handoff trigger (using stable localBlocks)
      if (agentType === 'VENTURE_ARCHITECT') {
        const fullText = localBlocks.map(b => b.content).join('\n');
        const blueprintJson = extractBlueprint(fullText);
        if (blueprintJson) {
          setTimeout(() => {
            triggerHandoff(blueprintJson);
          }, 1500);
        }
      }

    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[STREAM FRACTURE] ${error.message}`, document_ids: [], agent: 'UNKNOWN' }]);
    } finally {
      setIsStreaming(false);
    }
  };

  const extractBlueprint = (text) => {
    if (!text) return null;
    const startIdx = text.indexOf('{');
    if (startIdx === -1) return null;
    
    for (let i = text.length; i > startIdx; i--) {
      const candidate = text.slice(startIdx, i);
      if (candidate.includes('"nodes"') && candidate.includes('"version"')) {
        try {
          const parsed = JSON.parse(candidate);
          if (parsed.nodes && Array.isArray(parsed.nodes)) {
            return candidate;
          }
        } catch (e) {}
      }
    }
    return null;
  };

  const triggerHandoff = async (blueprintJson) => {
    setChatHistory(prev => [...prev, { role: 'system', content: `⚙️ [BLUEPRINT HANDOFF INTERCEPTED] Routing blueprint to Executive Architect for physical synthesis...`, document_ids: [] }]);
    
    setIsStreaming(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    
    try {
      const response = await fetch('/api/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({ 
          description: blueprintJson, 
          prompt: blueprintJson,
          document_ids: cachedDocumentIds,
          history: [] // Clean history for strict alternating sequence
        })
      });
      
      if (!response.body) throw new Error("No readable stream");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      setChatHistory(prev => [...prev, { role: 'system', content: '', document_ids: [], agent: 'UNKNOWN' }]);
      
      let agentType = 'UNKNOWN';
      let streamBuffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (value) {
          streamBuffer += decoder.decode(value, { stream: true });
        }
        
        let lastNewlineIdx = streamBuffer.lastIndexOf('\n');
        if (lastNewlineIdx !== -1) {
          const completeLines = streamBuffer.slice(0, lastNewlineIdx);
          streamBuffer = streamBuffer.slice(lastNewlineIdx + 1);
          
          const lines = completeLines.split('\n');
          for (const line of lines) {
            if (!line.trim()) continue;
            
            let cleanLine = line;
            if (cleanLine.startsWith('data: ')) {
              cleanLine = cleanLine.slice(6);
            }
            
            try {
              const parsed = JSON.parse(cleanLine.trim());
              
              if (parsed.event === 'compile_success' || parsed.event === 'ontology_ready') {
                fetchSystemRegistry();
              }

              if (parsed.type === 'agent_identity' && parsed.agent) {
                agentType = parsed.agent;
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  newHistory[newHistory.length - 1].agent = parsed.agent;
                  return newHistory;
                });
              } else if (parsed.type === 'agent_stream' && parsed.content) {
                setChatHistory(prev => {
                  const newHistory = [...prev];
                  newHistory[newHistory.length - 1].content += parsed.content;
                  return newHistory;
                });
              } else if (parsed.type === 'socratic_pause') {
                setSocraticChallenge(parsed);
              }
            } catch (e) {
              setChatHistory(prev => {
                const newHistory = [...prev];
                newHistory[newHistory.length - 1].content += line;
                return newHistory;
              });
            }
          }
        }
        if (done) break;
      }
      
      // Flush remaining stream buffer
      if (streamBuffer.trim()) {
        let cleanLine = streamBuffer.trim();
        if (cleanLine.startsWith('data: ')) {
          cleanLine = cleanLine.slice(6);
        }
        try {
          const parsed = JSON.parse(cleanLine);
          if (parsed.type === 'agent_stream' && parsed.content) {
            setChatHistory(prev => {
              const newHistory = [...prev];
              newHistory[newHistory.length - 1].content += parsed.content;
              return newHistory;
            });
          }
        } catch (e) {
          setChatHistory(prev => {
            const newHistory = [...prev];
            newHistory[newHistory.length - 1].content += streamBuffer;
            return newHistory;
          });
        }
      }
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[STREAM FRACTURE] ${error.message}`, document_ids: [], agent: 'UNKNOWN' }]);
    } finally {
      setIsStreaming(false);
    }
  };

  const renderMessageContent = (msg) => {
    const { content, agent } = msg;

    if (agent === 'CLAUDEAY_PROPOSAL') {
      let proposal = {};
      try { proposal = JSON.parse(content); } catch (_) {}
      return (
        <div className="claudeay-proposal-card">
          <div className="claudeay-proposal-header">
            <span className="claudeay-proposal-badge">
              🔵 CLAUDEAY AUTO-DIAGNOSIS
            </span>
            <span className="claudeay-proposal-count">
              {proposal.error_count} error{proposal.error_count !== 1 ? 's' : ''} detected
            </span>
          </div>
          <div className="claudeay-proposal-diagnosis">
            {proposal.diagnosis}
          </div>
          <div className="claudeay-proposal-actions">
            <button
              type="button"
              className="claudeay-approve-btn"
              onClick={async () => {
                await fetch('/api/claudeay/approve', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ fix_id: proposal.fix_id, action: 'approve' })
                });
              }}
            >
              ✅ Approve & Execute Fix
            </button>
            <button
              type="button"
              className="claudeay-dismiss-btn"
              onClick={async () => {
                await fetch('/api/claudeay/approve', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ fix_id: proposal.fix_id, action: 'dismiss' })
                });
              }}
            >
              🚫 Dismiss
            </button>
          </div>
        </div>
      );
    }

    // Claude Architect response rendering
    if (agent === 'CLAUDE_ARCHITECT') {
      const formattedContent = typeof content === 'string'
        ? content.replace(/\\n/g, '\n')
        : content;
      return (
        <div className="claude-architect-response">
          <div className="claude-architect-badge">
            🔵 CLAUDE ARCHITECT
          </div>
          <div className="whitespace-pre-wrap leading-relaxed font-mono text-sm text-slate-200">
            {formattedContent}
          </div>
        </div>
      );
    }
    
    // Check if it is a Venture Swarm response
    if (agent === 'VENTURE_ARCHITECT') {
      try {
        const blocks = JSON.parse(content);
        if (Array.isArray(blocks)) {
          return (
            <div className="flex flex-col space-y-4 w-full mt-2">
              {blocks.map((block, idx) => {
                const emitter = block.emitter;
                let emitterColor = 'border-slate-700 bg-slate-900/40 text-slate-300';
                let tagColor = 'bg-slate-800 text-slate-400';
                
                if (emitter === 'CEO') {
                  emitterColor = 'border-indigo-500/30 bg-indigo-950/10 hover:border-indigo-500/50';
                  tagColor = 'bg-indigo-900/50 text-indigo-300 border border-indigo-700/50';
                } else if (emitter === 'CMO') {
                  emitterColor = 'border-purple-500/30 bg-purple-950/10 hover:border-purple-500/50';
                  tagColor = 'bg-purple-900/50 text-purple-300 border border-purple-700/50';
                } else if (emitter === 'CFO') {
                  emitterColor = 'border-emerald-500/30 bg-emerald-950/10 hover:border-emerald-500/50';
                  tagColor = 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50';
                } else if (emitter === 'CTO') {
                  emitterColor = 'border-cyan-500/30 bg-cyan-950/10 hover:border-cyan-500/50';
                  tagColor = 'bg-cyan-900/50 text-cyan-300 border border-cyan-700/50';
                } else if (emitter === 'CIO') {
                  emitterColor = 'border-blue-500/30 bg-blue-950/10 hover:border-blue-500/50';
                  tagColor = 'bg-blue-900/50 text-blue-300 border border-blue-700/50';
                }
                
                const formattedBlockContent = typeof block.content === 'string' ? block.content.replace(/\\n/g, '\n') : block.content;
                
                return (
                  <div key={idx} className={`p-4 border rounded-xl shadow-md backdrop-blur-md transition-all duration-300 ${emitterColor}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-[10px] font-mono font-bold px-2 py-1 rounded tracking-widest uppercase ${tagColor}`}>
                        💼 C-SUITE: {emitter}
                      </span>
                    </div>
                    <div className="text-sm font-mono whitespace-pre-wrap leading-relaxed agent-card-text">
                      {formattedBlockContent}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }
      } catch (e) {
        // Fallback
      }
    }
    
    // IPC Bridge custom components rendering
    if (msg.is_pause_actionable) {
      return (
        <div className="flex flex-col space-y-4 w-full mt-3">
          <div className="p-4 bg-slate-900/80 border border-amber-500/40 rounded-xl shadow-lg backdrop-blur-md">
            <div className="flex justify-between items-center mb-3">
              <span className="text-xs font-mono font-bold text-amber-400 tracking-wider">
                ⚠️ STRATEGIC PAUSE ACTIVE
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-amber-950/50 text-amber-300 rounded border border-amber-800/50 uppercase">
                Awaiting Authorization
              </span>
            </div>
            <p className="text-sm text-slate-300 font-mono leading-relaxed mb-4">
              The system has spooled the blueprint to disk and engaged a biological circuit breaker. Review the spooled target:
              <br />
              <span className="text-cyan-400 mt-1 block select-all font-bold">{msg.blueprint_file}</span>
            </p>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={() => handleBridgeApprove(msg.blueprint_file, chatHistory.indexOf(msg))}
                className="flex-1 px-4 py-2 bg-emerald-800 hover:bg-emerald-700 text-xs font-mono font-bold text-slate-100 rounded-lg border border-emerald-600 transition-all hover:shadow-lg active:scale-95 cursor-pointer"
              >
                Approve Execution
              </button>
              <button
                type="button"
                onClick={() => handleBridgeReject(msg.blueprint_file, chatHistory.indexOf(msg))}
                className="px-4 py-2 bg-rose-950 hover:bg-rose-900 text-xs font-mono font-bold text-rose-400 rounded-lg border border-rose-800 transition-all hover:shadow-lg active:scale-95 cursor-pointer"
              >
                Reject & Delete
              </button>
            </div>
          </div>
        </div>
      );
    }

    if (agent === 'IPC_BRIDGE_SYSTEM') {
      return (
        <div className="flex flex-col space-y-2 w-full mt-2">
          <div className="p-4 bg-black/90 border border-slate-700/60 rounded-xl shadow-lg font-mono text-[11px] text-cyan-400 max-h-[300px] overflow-y-auto leading-relaxed custom-scrollbar whitespace-pre-wrap select-all">
            {content}
          </div>
        </div>
      );
    }
    
    // Normal / Executive Architect scorecard rendering or plain text
    try {
      const parsed = JSON.parse(content);
      if (parsed.verdict && parsed.gate) return <EvaluationScorecard data={parsed} />;
    } catch (e) {}
    
    const formattedContent = typeof content === 'string' ? content.replace(/\\n/g, '\n') : content;
    return <div className="whitespace-pre-wrap leading-relaxed">{formattedContent}</div>;
  };

  const challenge = socraticChallenge ? { ...socraticChallenge, id: socraticChallenge.challenge_id } : null;

  return (
    <div className={`builder-chat ${isMaximized ? 'terminal-maximized' : ''}`}>
      <div className="chat-header">
        <h2>
          🌐 Omni-Router Gateway (Phase 12 Active)
          <span className="stream-badge" style={{ background: 'linear-gradient(135deg, #6366f1, #a78bfa)' }}>OMNI-ROUTER ACTIVE</span>
        </h2>
        <div className="flex items-center space-x-3">
          <div className="swarm-pill-wrapper">
            <button
              className="swarm-pill"
              onClick={() => setSwarmOpen(o => !o)}
            >
              <span className="swarm-pill-dot" />
              Active Swarm
              <span className="swarm-pill-count">{systemAgents.length}</span>
            </button>
            {swarmOpen && (
              <div className="swarm-dropdown">
                {systemAgents.length === 0 && (
                  <div className="swarm-empty">No agents online</div>
                )}
                {systemAgents.map(agent => (
                  <div key={agent.id} className="swarm-agent-row">
                    <span className={`swarm-agent-dot ${agent.status === 'ACTIVE' ? 'dot-live' : 'dot-off'}`} />
                    <span className="swarm-agent-name">{agent.name}</span>
                    <span className="swarm-agent-port">:{agent.port}</span>
                    <span className={`swarm-agent-status ${agent.status === 'ACTIVE' ? 'status-active' : 'status-idle'}`}>
                      {agent.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="header-btn header-btn-primary"
            title={isMaximized ? "Restore panel to standard view" : "Maximize panel to fullscreen"}
          >
            {isMaximized ? '🗗 Restore' : '⛶ Maximize'}
          </button>
          <button
            onClick={handleNewThread}
            className="header-btn header-btn-danger"
            title="Flush chat history, sessionStorage, and cached document IDs"
          >
            ➕ New Thread
          </button>
          <span className="text-xs font-mono tracking-wider text-cyan-400">BUILDER PULSE: ACTIVE</span>
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-cyan-500"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
          </span>
        </div>
      </div>
      <ClaudeAYStatus />

      <div className="chat-messages font-mono text-sm custom-scrollbar">
        <div className="text-teal-500 font-semibold opacity-90">&gt; TERMINAL BOOT COMPLETED SUCCESSFULLY</div>
        {chatHistory.length === 0 && <div className="text-cyan-600 animate-pulse mt-4">&gt; AWAITING INGESTION DIRECTIVES...</div>}
        
        {chatHistory.map((msg, idx) => (
          <div key={idx} className={`msg ${msg.role === 'user' ? 'user' : 'assistant'}`}>
             <strong className={`block mb-2 text-xs uppercase tracking-wider ${msg.role === 'user' ? 'text-cyan-400' : msg.agent === 'VENTURE_ARCHITECT' ? 'text-purple-400' : 'text-teal-400'}`}>
                {msg.role === 'user' ? 'CO-PILOT' : msg.agent === 'VENTURE_ARCHITECT' ? '🤖 VENTURE ARCHITECT' : msg.agent === 'EXECUTIVE_ARCHITECT' ? '🏗️ EXECUTIVE ARCHITECT' : msg.agent === 'CLAUDE_ARCHITECT' ? '🔵 CLAUDE ARCHITECT' : 'MAF ORCHESTRATOR'}
             </strong>
             {renderMessageContent(msg)}
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>

      {/* Socratic Challenge Form Lock */}
      {socraticChallenge && createPortal(
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[99999] flex items-center justify-center p-4" style={{ pointerEvents: 'auto' }}>
          <div className="socratic-panel p-6 bg-slate-950 border border-orange-500/50 rounded-xl shadow-2xl w-full max-w-[500px] backdrop-blur-lg flex flex-col space-y-4 m-0">
            <div className="flex justify-between items-center border-b border-orange-500/30 pb-2">
              <span className="text-sm font-mono font-bold text-orange-400 tracking-wider">
                🏛️ ADVERSARIAL CHALLENGE: {socraticChallenge.challenge_id}
              </span>
              <span className="text-[10px] font-mono px-2 py-1 bg-red-950 text-red-300 border border-red-800 rounded uppercase font-bold animate-pulse">
                Input Locked
              </span>
            </div>
            
            <div className="text-xs text-slate-300 font-mono space-y-2">
              <p>The Critic has flagged significant strategic gaps. You must provide data-driven evidence or click Hard Override to proceed.</p>
              <div className="flex flex-col space-y-2 mt-2">
                {socraticChallenge.weaknesses.map((w, idx) => (
                  <div key={idx} className="p-3 bg-slate-900/80 border border-slate-800 rounded">
                    <div className="flex justify-between text-[11px] font-bold text-orange-400 mb-1">
                      <span>{w.category} ({w.severity})</span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-slate-400">{w.challenge}</p>
                    <p className="text-[10px] text-cyan-400 mt-1">→ {w.required_evidence}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-col space-y-2">
              <textarea
                value={evidenceText}
                onChange={(e) => setEvidenceText(e.target.value)}
                placeholder="___Provide data-driven evidence (e.g. pilot conversions, TAM study, benchmark statistics)___"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs font-mono text-slate-200 focus:border-cyan-500 outline-none"
                rows={3}
              />
              <div className="flex space-x-2">
                <button
                  type="button"
                  onClick={() => submitSocraticEvidence(challenge.id, evidenceText)}
                  disabled={isSocraticSubmitting || !evidenceText.trim()}
                  className="flex-1 px-4 py-2 bg-emerald-800 hover:bg-emerald-700 text-xs font-mono font-bold text-slate-100 rounded-lg border border-emerald-600 transition-colors"
                >
                  {isSocraticSubmitting ? 'Evaluating...' : 'Submit Evidence'}
                </button>
                <button
                  type="button"
                  onClick={() => submitSocraticOverride(challenge.id)}
                  disabled={isSocraticSubmitting}
                  className="px-4 py-2 bg-rose-950 hover:bg-rose-900 text-xs font-mono font-bold text-rose-400 rounded-lg border border-rose-800 transition-colors"
                >
                  Hard Override
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Document Staging Deck */}
      {attachments.length > 0 && (
        <div className="px-4 py-2 bg-slate-900/60 border-t border-cyan-500/10 flex flex-wrap gap-2">
          {attachments.map(att => (
            <div key={att.document_id} className="flex items-center space-x-2 bg-slate-800 border border-cyan-500/50 rounded-full px-3 py-1">
              <span className="text-xs text-cyan-300 truncate max-w-[150px]">{att.original_name}</span>
              <button onClick={() => removeAttachment(att.document_id)} className="text-slate-400 hover:text-red-400" disabled={socraticChallenge !== null}>✕</button>
            </div>
          ))}
        </div>
      )}

      {lastPrompt !== "" && (
        <div className="px-4 py-1 flex justify-start">
          <button
            type="button"
            onClick={() => setInput(lastPrompt)}
            className="recall-btn px-3 py-1 font-mono tracking-wider flex items-center space-x-1"
            title="Recall last submitted prompt"
          >
            <span>⟲ Recall</span>
          </button>
        </div>
      )}

      <div className="chat-input-bar glowing-capsule-input">
        {isStreaming && (
          <button
            type="button"
            onClick={handleHalt}
            className="absolute left-1/2 -translate-x-1/2 -top-12 px-4 py-2 bg-rose-950/90 hover:bg-rose-900 border border-rose-500/50 hover:border-rose-500 text-rose-300 hover:text-rose-200 text-xs font-mono font-bold tracking-wider rounded-full transition-all shadow-lg flex items-center space-x-2 animate-bounce z-20"
          >
            <span>🛑 HALT & INTERVENE</span>
          </button>
        )}
        <input 
          type="file" 
          className="hidden" 
          ref={fileInputRef} 
          onChange={handleFileUpload}
          accept=".pdf,.xlsx,.csv,.docx,.txt,.md,.json"
        />
        <button 
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading || isStreaming || socraticChallenge !== null}
          className="px-4 h-[40px] bg-slate-800 border border-slate-700 hover:border-cyan-500 text-cyan-400 rounded-lg outline-none font-mono text-sm transition-colors flex items-center justify-center mr-1"
          title="Ingest Enterprise Document"
        >
          {isUploading ? '...' : '[+]'}
        </button>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowUp' && input === "") {
              setInput(lastPrompt);
              e.preventDefault();
            } else if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSynthesize();
            }
          }}
          className="flex-1" 
          rows={2}
          placeholder={socraticChallenge ? "___Standard input locked. Resolve challenge above___" : "___Enter system architectural brief or attach payload___"}
          disabled={isStreaming || socraticChallenge !== null}
        />
        <button 
          type="button"
          onClick={handleSynthesize}
          disabled={isStreaming || socraticChallenge !== null || (!input.trim() && attachments.length === 0)}
          className="send-btn ml-1"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
