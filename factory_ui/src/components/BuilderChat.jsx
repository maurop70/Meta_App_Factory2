import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function BuilderChat() {
  const [fileTree, setFileTree] = useState([]);
  const [selectedPath, setSelectedPath] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [chatLog, setChatLog] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    const poisonCheck = localStorage.getItem('mode_a_target_matrix');
    if (poisonCheck === "Unknown/Manual Selection Required" || poisonCheck === "undefined") {
      localStorage.removeItem('mode_a_target_matrix');
      localStorage.removeItem('mode_a_handoff_prompt');
      console.log("[AUTO-PURGE] Poisoned memory bridge severed.");
    }
  }, []);

  useEffect(() => {
    // OVERRIDE: Re-route the Atomizer scanner to the absolute CFO Agent path
    const targetPath = encodeURIComponent('c:\\Dev\\Antigravity_AI_Agents\\Meta_App_Factory\\CFO_Agent');
    axios.get(`/api/v1/atomizer/map?target_directory=${targetPath}`)
      .then(res => setFileTree(res.data.tree))
      .catch(err => console.error("[ATOMIZER] Map fracture:", err));
  }, []);

  useEffect(() => {
    // Mode C Handoff Interception
    const handoffPrompt = localStorage.getItem('mode_a_handoff_prompt');
    const handoffTarget = localStorage.getItem('mode_a_target_matrix');
    
    if (handoffPrompt) {
        setPrompt(handoffPrompt);
        localStorage.removeItem('mode_a_handoff_prompt'); 
    }
    
    if (handoffTarget) {
        setSelectedPath(handoffTarget); // Automatically lock the UI to the deduced file
        localStorage.removeItem('mode_a_target_matrix');
        console.log(`[BUILDER CHAT] Target Matrix auto-locked to: ${handoffTarget}`);
    }
  }, []);

  const renderTree = (nodes) => {
    return nodes.map((node, idx) => (
      <div key={idx} style={{ paddingLeft: '15px', marginTop: '5px' }}>
        {node.type === 'directory' ? (
          <details>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#818cf8' }}>📁 {node.name}</summary>
            {renderTree(node.children)}
          </details>
        ) : (
          <div 
            style={{ 
              cursor: 'pointer', fontSize: '0.9em', 
              color: selectedPath === node.path ? '#10b981' : '#cbd5e1',
              fontWeight: selectedPath === node.path ? 'bold' : 'normal'
            }}
            onClick={() => setSelectedPath(node.path)}
          >
            📄 {node.name}
          </div>
        )}
      </div>
    ));
  };

  const commitPayload = async (path, rawContent) => {
    // Strip markdown code fences for the raw payload robustly
    const cleanContent = rawContent.trim().replace(/^```[^\n]*\r?\n/, '').replace(/\r?\n```$/, '').trim();
    
    try {
        // Phase 7: The Phantom QA Pre-Flight
        const qaRes = await axios.post('/api/v1/qa/engine/pre-flight', { target_path: path, content: cleanContent });
        
        if (qaRes.data.status === 'REJECTED') {
            alert("[SECURITY FATAL] Phantom QA rejected the payload:\n\n" + qaRes.data.violations.join("\n"));
            return;
        }

        // Phase 6: The Atomizer Autonomous Write
        const writeRes = await axios.post('/api/v1/atomizer/mutate', { relative_path: path, content: cleanContent });
        alert(`[ATOMIZER SUCCESS] Matrix mutated. ${writeRes.data.bytes_written} bytes physically written to disk.`);
    } catch (err) {
        console.error("[ACTUATION FRACTURE]", err);
        alert(`Fatal I/O Exception during commit sequence:\n${err.response?.data?.detail || err.message}`);
    }
  };

  const executeTriad = async () => {
    if (!prompt || prompt.trim() === '') { console.warn("Execution Denied: Empty Payload"); return; }
    setIsGenerating(true);
    
    const fullPrompt = `TARGET MATRIX: ${selectedPath || 'UNKNOWN'}\n\nBIOLOGICAL DIRECTIVE:\n${prompt}`;
    setChatLog(prev => [...prev, { agent: 'OPERATOR', text: fullPrompt }]);
    
    try {
        // Corrected Schema: Matching the FastAPI Pydantic model ({ prompt: ... })
        const initRes = await axios.post('/api/v1/builder/initiate-stream', { prompt: fullPrompt });
        const sessionId = initRes.data.session_id;
        
        const response = await fetch(`/api/v1/builder/stream?session_id=${sessionId}`, {
            method: 'GET',
            headers: { 'Accept': 'text/event-stream' }
        });

        if (!response.body) throw new Error("ReadableStream not supported by browser.");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let streamBuffer = "";
        let currentArchitectMessage = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                setIsGenerating(false);
                break;
            }
            
            streamBuffer += decoder.decode(value, { stream: true });
            const lines = streamBuffer.split('\n');
            streamBuffer = lines.pop(); // Keep the incomplete line in the buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.replace('data: ', '').trim();
                    if (dataStr === '[DONE]') {
                        console.log("[STREAM COMPLETE]");
                        setIsGenerating(false);
                        return; // Graceful exit
                    }
                    try {
                        const parsed = JSON.parse(dataStr);
                        if (parsed.status === 'AST_COMPLETE' || parsed.status === 'FATAL' || parsed.status === 'COMPLETE') {
                            console.log("[STREAM COMPLETE]");
                            setIsGenerating(false);
                            return; // Graceful exit
                        }
                        const newText = parsed.payload || parsed.chunk || parsed.text;
                        if (newText) {
                            currentArchitectMessage += newText;

                            // ---- PHASE 2: AUTONOMOUS TARGET INTERCEPTION (PATCHED) ----
                            const targetMatch = currentArchitectMessage.match(/\*\*TARGET MATRIX:\s*(.+?)\*\*/i);
                            if (targetMatch && targetMatch[1]) {
                                setSelectedPath(targetMatch[1].trim());
                            }

                            setChatLog((prevLog) => {
                                if (prevLog.length === 0) return [{ agent: 'ARCHITECT', text: newText }];
                                
                                const updatedLog = [...prevLog];
                                const lastIndex = updatedLog.length - 1;
                                
                                if (updatedLog[lastIndex].agent === 'ARCHITECT') {
                                    // Create a new object reference for the mutated message
                                    updatedLog[lastIndex] = {
                                        ...updatedLog[lastIndex],
                                        text: updatedLog[lastIndex].text + newText
                                    };
                                } else {
                                    updatedLog.push({ agent: 'ARCHITECT', text: newText });
                                }
                                
                                return updatedLog;
                            });
                        }
                    } catch (parseError) {
                        console.warn("[SSE PARSE SKIP] Fragmented JSON chunk:", dataStr);
                    }
                }
            }
        }
    } catch (error) {
        console.error("[SSE FRACTURE] Stream consumed violently:", error);
        setIsGenerating(false);
    }
    setPrompt("");
  };

  const renderMessage = (log) => {
    // Automatically isolate markdown code blocks to expose the Actuator button
    const safeContent = log?.text || "";
    const codeBlockRegex = /(```[\w]*\n[\s\S]*?```)/g;
    const parts = safeContent.split(codeBlockRegex);

    return parts.map((part, idx) => {
        if (part.startsWith('```')) {
            // Only render the commit button when streaming is physically complete
            return (
                <div key={idx} style={{ backgroundColor: '#0f172a', padding: '15px', borderRadius: '4px', marginTop: '10px', border: '1px solid #3b82f6' }}>
                    <pre style={{ margin: 0, color: '#38bdf8', overflowX: 'auto' }}>{part}</pre>
                    {!isGenerating && log.agent === 'ARCHITECT' && (
                        <button 
                            onClick={() => commitPayload(selectedPath, part)}
                            style={{ marginTop: '15px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                        >
                            💾 EXECUTE WRITE TO {selectedPath.split('/').pop()}
                        </button>
                    )}
                </div>
            );
        }
        return <span key={idx}>{part}</span>;
    });
  };

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: '80vh', backgroundColor: '#0f172a', color: '#f8fafc', borderRadius: '8px', overflow: 'hidden' }}>
        <div style={{ width: '300px', borderRight: '1px solid #334155', padding: '15px', overflowY: 'auto', backgroundColor: '#1e293b' }}>
            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', fontSize: '1rem', color: '#e2e8f0' }}>ATOMIZER MAP</h3>
            <div style={{ fontSize: '0.9em', marginTop: '10px' }}>{renderTree(fileTree)}</div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '20px' }}>
            <div style={{ flex: 1, overflowY: 'auto', marginBottom: '20px', backgroundColor: '#1e293b', padding: '20px', borderRadius: '8px', border: '1px solid #334155' }}>
                {chatLog.map((log, idx) => (
                    <div key={idx} style={{ marginBottom: '15px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
                        <strong style={{ color: log.agent === 'OPERATOR' ? '#10b981' : '#a855f7' }}>[{log.agent}]</strong>
                        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', marginTop: '5px', color: '#e2e8f0' }}>
                            {renderMessage(log)}
                        </pre>
                    </div>
                ))}
            </div>
            <div style={{ paddingBottom: '10px' }}>
                <input 
                    type="text" 
                    value={selectedPath || ''} 
                    onChange={e => setSelectedPath(e.target.value)} 
                    placeholder="Override target path manually..." 
                    style={{ width: '100%', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #475569', color: '#10b981', borderRadius: '4px', fontWeight: 'bold' }} 
                />
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
                <input 
                    style={{ flex: 1, padding: '12px', backgroundColor: '#334155', border: '1px solid #475569', color: 'white', borderRadius: '4px' }}
                    value={prompt} onChange={e => setPrompt(e.target.value)}
                    onKeyDown={(e) => { 
                        if (e.key === 'Enter' && !isGenerating) { 
                            executeTriad(); 
                        } 
                    }}
                    placeholder={selectedPath ? `Execute directive against ${selectedPath}...` : "Execute global directive..."}
                    disabled={isGenerating}
                />
                <button 
                    style={{ padding: '12px 24px', backgroundColor: isGenerating ? '#475569' : '#10b981', color: 'white', border: 'none', borderRadius: '4px', cursor: isGenerating ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}
                    onClick={executeTriad} disabled={isGenerating}
                >
                    {isGenerating ? 'STREAMING...' : 'IGNITE TRIAD'}
                </button>
            </div>
        </div>
    </div>
  );
}
