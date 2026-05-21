import React, { useState, useRef, useEffect } from 'react';

const INGESTION_TEMPLATES = [
  { title: "Inventory Stock Modal", desc: "Add a Detail Modal component to the React frontend utilizing ReactDOM.createPortal to adjust stock levels." },
  { title: "FastAPI Pagination Router", desc: "Implement a native Python SQLite3 router for inventory tracking enforcing strict limit/offset pagination." },
  { title: "Vite Proxy Splicing", desc: "Configure a strict proxy server block in vite.config.js to route /api/ traffic." }
];

// --- ARCHITECTURAL INJECTION: INTELLIGENCE PARSER ---
const EvaluationScorecard = ({ data }) => {
  if (!data || !data.verdict || !data.gate) return <div className="text-gray-400">Malformed intelligence payload.</div>;

  const { verdict, gate } = data;
  const isChallenged = gate.gate_result === 'CHALLENGED';
  
  return (
    <div className="flex flex-col space-y-4 w-full mt-3">
      {/* Top Deck: Mathematical Verdicts */}
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

      {/* Bottom Deck: Vulnerability Matrix */}
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
  const [chatHistory, setChatHistory] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleSynthesize = async () => {
    if (!input.trim() || isStreaming) return;
    
    const userMsg = input;
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsStreaming(true);
    
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: userMsg, prompt: userMsg })
      });
      
      if (!response.body) throw new Error("No readable stream");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      setChatHistory(prev => [...prev, { role: 'system', content: '' }]);
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setChatHistory(prev => {
          const newHistory = [...prev];
          newHistory[newHistory.length - 1].content += chunk;
          return newHistory;
        });
      }
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[STREAM FRACTURE] ${error.message}` }]);
    } finally {
      setIsStreaming(false);
    }
  };

  // --- ARCHITECTURAL INJECTION: DYNAMIC RENDERER ---
  const renderMessageContent = (content) => {
    try {
      const parsed = JSON.parse(content);
      if (parsed.verdict && parsed.gate) {
        return <EvaluationScorecard data={parsed} />;
      }
    } catch (e) {
      // JSON parser will naturally fail while the SSE stream is active.
      // Fallback to raw text rendering until the stream completes.
    }
    return <div className="whitespace-pre-wrap leading-relaxed">{content}</div>;
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border border-cyan-500/30 rounded-xl overflow-hidden shadow-2xl">
      
      <div className="bg-slate-900 border-b border-cyan-500/30 p-4 flex justify-between items-center shadow-md">
        <h2 className="text-lg font-semibold tracking-wide uppercase text-cyan-400" style={{fontFamily: "'Outfit', sans-serif"}}>App Synthesis Gateway</h2>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono tracking-wider text-cyan-400">BUILDER PULSE: ACTIVE</span>
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-cyan-500"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 border-b border-cyan-900/30 bg-slate-950">
        {INGESTION_TEMPLATES.map((tpl, idx) => (
          <button 
            key={idx} 
            type="button"
            onClick={() => setInput(tpl.title)} 
            className="appearance-none flex flex-col text-left p-4 bg-cyan-950/20 border border-cyan-500/30 hover:border-cyan-400 hover:bg-cyan-900/40 rounded-lg transition-all shadow-[0_0_15px_rgba(6,182,212,0.05)] group"
          >
            <span className="text-cyan-400 font-bold text-sm group-hover:text-cyan-300 transition-colors">{tpl.title}</span>
            <span className="text-slate-400 text-xs mt-2 leading-relaxed">{tpl.desc}</span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-950 font-mono text-sm custom-scrollbar">
        <div className="text-teal-500 font-semibold opacity-90">&gt; TERMINAL BOOT COMPLETED SUCCESSFULLY</div>
        <div className="text-teal-500 font-semibold opacity-90">&gt; STREAM TRANSPORT: SSE EXECUTOR ACTIVATED</div>
        {chatHistory.length === 0 && <div className="text-cyan-600 animate-pulse mt-4">&gt; AWAITING INGESTION DIRECTIVES...</div>}
        
        {chatHistory.map((msg, idx) => (
          <div key={idx} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-4 rounded-lg shadow-lg ${msg.role === 'user' ? 'bg-cyan-900/40 border border-cyan-500/40 text-cyan-50' : 'bg-slate-800/80 border border-slate-700 text-slate-300'}`}>
               <strong className={`block mb-2 text-xs uppercase tracking-wider ${msg.role === 'user' ? 'text-cyan-400' : 'text-teal-400'}`}>
                  {msg.role === 'user' ? 'CO-PILOT' : 'MAF ORCHESTRATOR'}
               </strong>
               {renderMessageContent(msg.content)}
            </div>
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>

      <div className="p-4 bg-slate-900 border-t border-cyan-500/30">
        <div className="flex gap-2 relative">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSynthesize()}
            className="flex-1 bg-slate-950 border border-slate-700 focus:border-cyan-500 text-cyan-50 p-4 rounded-lg outline-none font-mono text-sm shadow-inner transition-colors" 
            placeholder="___Enter system architectural brief___" 
          />
          <button 
            type="button"
            onClick={handleSynthesize}
            disabled={isStreaming}
            className={`px-8 font-bold tracking-wider rounded-lg transition-all ${isStreaming ? 'bg-slate-700 text-slate-500 cursor-not-allowed' : 'bg-cyan-700 hover:bg-cyan-600 text-white shadow-[0_0_15px_rgba(6,182,212,0.5)]'}`}
          >
            {isStreaming ? '[SYNTHESIZING...]' : '[SYNTHESIZE]'}
          </button>
        </div>
      </div>
    </div>
  );
}
