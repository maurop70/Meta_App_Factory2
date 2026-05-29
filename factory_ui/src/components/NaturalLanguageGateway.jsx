import React, { useState, useEffect } from 'react';

export default function NaturalLanguageGateway({ mode = 'builder', selectedApp }) {
  const [chatLog, setChatLog] = useState([]);
  const [input, setInput] = useState('');
  const [isSynthesizing, setIsSynthesizing] = useState(false);

  const isWarRoom = mode === 'warroom';
  const accentColor = isWarRoom ? 'text-red-500' : 'text-cyan-400';
  const borderTheme = isWarRoom ? 'border-red-500/30' : 'border-cyan-500/30';
  const bgTheme = isWarRoom ? 'bg-red-950/20' : 'bg-cyan-950/20';
  const buttonTheme = isWarRoom ? 'bg-red-600 hover:bg-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)]' : 'bg-cyan-600 hover:bg-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.4)]';
  const title = isWarRoom ? 'Adversarial Threat Ingestion Gateway' : 'App Synthesis Gateway';
  const badge = isWarRoom ? 'THREAT SENSOR: ACTIVE' : 'BUILDER PULSE: ACTIVE';
  const badgePing = isWarRoom ? 'bg-red-500' : 'bg-cyan-500';

  useEffect(() => {
    if (!isWarRoom) return;

    const activeProject = selectedApp || localStorage.getItem('last_active_project') || 'Aether';
    let eventSource;
    const connectSSE = () => {
      console.log(`Connecting EventSource to /api/war-room/stream?project=${activeProject}...`);
      eventSource = new EventSource(`/api/war-room/stream?project=${activeProject}`);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'dialogue') {
            setChatLog(prev => {
              // Avoid duplicates
              const isDuplicate = prev.some(msg => 
                msg.agent === data.agent && 
                msg.content === data.message && 
                msg.timestamp === data.timestamp
              );
              if (isDuplicate) return prev;
              return [...prev, {
                role: data.agent.toLowerCase(),
                agent: data.agent,
                content: data.message,
                color: data.color,
                timestamp: data.timestamp
              }];
            });
          }
        } catch (err) {
          console.error("SSE parse error:", err);
        }
      };

      eventSource.onerror = (err) => {
        console.error("EventSource encountered an error:", err);
        eventSource.close();
        setTimeout(connectSSE, 3000);
      };
    };

    connectSSE();

    return () => {
      if (eventSource) {
        console.log("Disconnecting EventSource...");
        eventSource.close();
      }
    };
  }, [isWarRoom, selectedApp]);



  const handleTransmit = async () => {
    if (!input.trim()) return;
    setChatLog([...chatLog, { role: 'user', content: input }]);
    setInput('');
    setTimeout(() => {
      setChatLog(prev => [...prev, { role: 'cio_agent', content: 'Intent captured and mapped to the structural matrix. Awaiting execution trigger.' }]);
    }, 1000);
  };

  const triggerActuation = async () => {
    if (!input.trim() && chatLog.length === 0) return;
    setIsSynthesizing(true);
    
    const endpoint = isWarRoom ? '/api/warroom/seed' : '/api/cio/seed';
    const payloadText = [...chatLog.map(m => m.content), input.trim()].filter(Boolean).join('\n');


    const activeProject = selectedApp || localStorage.getItem('last_active_project') || 'Aether';

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project: activeProject,
          description: payloadText,
          change_type: 'feature',
          components: []
        })
      });
      
      if (response.ok) {
        const msg = isWarRoom 
          ? `[SYSTEM] Boardroom session successfully opened. Strategic debate ignited on topic: "${payloadText}".`
          : `[SYSTEM] Payload injected into Sentinel Queue. Target: ${endpoint}. Awaiting Native AY Actuation.`;
        setChatLog(prev => [...prev, { role: 'cio_agent', content: msg }]);
      } else {
        setChatLog(prev => [...prev, { role: 'cio_agent', content: `[FRACTURE] Backend rejected payload. Status: ${response.status}` }]);
      }
    } catch (error) {
      setChatLog(prev => [...prev, { role: 'cio_agent', content: `[NETWORK FRACTURE] Failed to reach edge node: ${error.message}` }]);
    } finally {
      setIsSynthesizing(false);
      setInput('');
    }
  };

  return (
    <div className={`nlg-container flex flex-col h-full bg-[#0B0F19] border ${borderTheme} rounded-xl overflow-hidden shadow-2xl`}>
      <div className={`bg-gray-900/80 border-b ${borderTheme} p-4 flex justify-between items-center`}>
        <h2 className={`text-lg font-semibold tracking-wide uppercase ${accentColor}`} style={{ fontFamily: 'Outfit, sans-serif' }}>{title}</h2>
        <div className="flex items-center space-x-2">
          <span className={`text-xs font-mono tracking-wider ${accentColor}`}>{badge}</span>
          <span className="flex h-3 w-3 relative">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${badgePing}`}></span>
            <span className={`relative inline-flex rounded-full h-3 w-3 ${badgePing}`}></span>
          </span>
        </div>
      </div>
      <div className="chat-matrix flex-1 overflow-y-auto p-6 space-y-4 bg-[#0B0F19]">
        {chatLog.length === 0 && <div className="text-center text-gray-600 mt-10 font-mono text-sm uppercase">Awaiting biological input stream...</div>}
        {chatLog.map((msg, idx) => {
          const isUser = msg.role === 'user';
          const agentName = isUser ? 'CO-PILOT' : (msg.agent || 'MAF ORCHESTRATOR');
          const agentStyleColor = (!isUser && msg.color) ? { color: msg.color } : {};

          return (
            <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div 
                className={`max-w-[80%] p-3 rounded-lg text-sm font-mono ${isUser ? 'bg-blue-900/30 border border-blue-500/30 text-blue-100' : `${bgTheme} border ${borderTheme} text-gray-300`}`}
                style={{ whiteSpace: 'pre-wrap' }}
              >
                <strong 
                  className={`block mb-1 text-xs ${isUser ? 'text-blue-400' : accentColor}`}
                  style={agentStyleColor}
                >
                  {agentName}
                </strong>
                {msg.content}
              </div>
            </div>
          );
        })}
      </div>
      <div className={`p-4 bg-gray-900/80 border-t ${borderTheme}`}>
        <textarea className={`w-full p-3 bg-[#0B0F19] border ${borderTheme} rounded-lg text-gray-200 font-mono text-sm focus:outline-none focus:border-opacity-100 transition-colors mb-3 resize-none`} rows="3" placeholder="Describe the architectural parameters..." value={input} onChange={(e) => setInput(e.target.value)} />
        <div className="flex justify-between items-center">
          <button onClick={handleTransmit} className="bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-600 px-6 py-2 rounded-md text-sm font-semibold transition-colors">TRANSMIT INTENT</button>
          <button onClick={triggerActuation} disabled={isSynthesizing} className={`px-6 py-2 rounded-md text-sm font-bold tracking-wide transition-colors ${isSynthesizing ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : `${buttonTheme} text-white`}`}>
            {isSynthesizing ? 'SYNTHESIZING...' : '[ ACTUATE BLUEPRINT ]'}
          </button>
        </div>
      </div>
    </div>
  );
}
