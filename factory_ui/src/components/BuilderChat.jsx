import React, { useState, useRef, useEffect } from 'react';

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
  const [chatHistory, setChatHistory] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  
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
    } catch (error) {
      setChatHistory(prev => [...prev, { role: 'system', content: `[INGESTION FRACTURE] ${error.message}` }]);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = null;
    }
  };

  const removeAttachment = (idToRemove) => {
    setAttachments(prev => prev.filter(att => att.document_id !== idToRemove));
  };

  const handleSynthesize = async () => {
    if ((!input.trim() && attachments.length === 0) || isStreaming) return;
    
    const userMsg = input;
    const currentAttachments = [...attachments];
    
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg || '[ATTACHED PAYLOAD TRANSMITTED]' }]);
    setInput('');
    setAttachments([]);
    setIsStreaming(true);
    
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          description: userMsg || "Evaluate attached documents.", 
          prompt: userMsg || "Evaluate attached documents.",
          document_ids: currentAttachments.map(a => a.document_id)
        })
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

  const renderMessageContent = (content) => {
    try {
      const parsed = JSON.parse(content);
      if (parsed.verdict && parsed.gate) return <EvaluationScorecard data={parsed} />;
    } catch (e) {}
    return <div className="whitespace-pre-wrap leading-relaxed">{content}</div>;
  };

  return (
    <div className="builder-chat">
      <div className="chat-header">
        <h2>
          🏗️ App Synthesis Gateway
          <span className="stream-badge">SSE STREAM</span>
        </h2>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono tracking-wider text-cyan-400">BUILDER PULSE: ACTIVE</span>
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-cyan-500"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
          </span>
        </div>
      </div>

      <div className="chat-messages font-mono text-sm custom-scrollbar">
        <div className="text-teal-500 font-semibold opacity-90">&gt; TERMINAL BOOT COMPLETED SUCCESSFULLY</div>
        {chatHistory.length === 0 && <div className="text-cyan-600 animate-pulse mt-4">&gt; AWAITING INGESTION DIRECTIVES...</div>}
        
        {chatHistory.map((msg, idx) => (
          <div key={idx} className={`msg ${msg.role === 'user' ? 'user' : 'assistant'}`}>
             <strong className={`block mb-2 text-xs uppercase tracking-wider ${msg.role === 'user' ? 'text-cyan-400' : 'text-teal-400'}`}>
                {msg.role === 'user' ? 'CO-PILOT' : 'MAF ORCHESTRATOR'}
             </strong>
             {renderMessageContent(msg.content)}
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>

      {/* Document Staging Deck */}
      {attachments.length > 0 && (
        <div className="px-4 py-2 bg-slate-900/60 border-t border-cyan-500/10 flex flex-wrap gap-2">
          {attachments.map(att => (
            <div key={att.document_id} className="flex items-center space-x-2 bg-slate-800 border border-cyan-500/50 rounded-full px-3 py-1">
              <span className="text-xs text-cyan-300 truncate max-w-[150px]">{att.original_name}</span>
              <button onClick={() => removeAttachment(att.document_id)} className="text-slate-400 hover:text-red-400">✕</button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input-bar">
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
          disabled={isUploading || isStreaming}
          className="px-4 h-[40px] bg-slate-800 border border-slate-700 hover:border-cyan-500 text-cyan-400 rounded-lg outline-none font-mono text-sm transition-colors flex items-center justify-center mr-1"
          title="Ingest Enterprise Document"
        >
          {isUploading ? '...' : '[+]'}
        </button>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSynthesize(); } }}
          className="flex-1" 
          rows={2}
          placeholder="___Enter system architectural brief or attach payload___" 
          disabled={isStreaming}
        />
        <button 
          type="button"
          onClick={handleSynthesize}
          disabled={isStreaming || (!input.trim() && attachments.length === 0)}
          className="send-btn ml-1"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
