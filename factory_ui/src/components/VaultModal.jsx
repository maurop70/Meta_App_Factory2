import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import axios from 'axios';

export default function VaultModal({ isOpen, onClose, project, handleActuateProject }) {
  const [activeTab, setActiveTab] = useState('briefing'); // 'briefing' | 'timeline'
  const [eosState, setEosState] = useState(null);
  const [history, setHistory] = useState([]);
  const [totalSessions, setTotalSessions] = useState(0);
  const [limit] = useState(5); // Paginated boundaries
  const [offset, setOffset] = useState(0);
  const [loadingEos, setLoadingEos] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !project) return;

    const fetchEosState = async () => {
      try {
        setLoadingEos(true);
        const res = await axios.get(`/api/eos/state?project_name=${encodeURIComponent(project.project_name)}`);
        setEosState(res.data);
      } catch (err) {
        console.error("Failed to load EOS state:", err);
      } finally {
        setLoadingEos(false);
      }
    };

    fetchEosState();
  }, [isOpen, project]);

  useEffect(() => {
    if (!isOpen || !project) return;

    const fetchHistory = async () => {
      try {
        setLoadingHistory(true);
        const res = await axios.get(
          `/api/warroom/history?project=${encodeURIComponent(project.project_name)}&limit=${limit}&offset=${offset}`
        );
        // Envelope check: items array & total
        if (res.data && Array.isArray(res.data.items)) {
          setHistory(res.data.items);
          setTotalSessions(res.data.total || 0);
        } else {
          setHistory([]);
          setTotalSessions(0);
        }
      } catch (err) {
        console.error("Failed to load warroom history:", err);
        setError("Unable to retrieve courtroom dialogue archives.");
      } finally {
        setLoadingHistory(false);
      }
    };

    fetchHistory();
  }, [isOpen, project, offset, limit]);

  if (!isOpen || !project) return null;

  const getFileName = (path) => {
    if (!path) return '';
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1];
  };

  const getActorColor = (actor) => {
    if (!actor) return 'text-cyan-400';
    const a = actor.toUpperCase();
    if (a.includes('CEO')) return 'text-red-400';
    if (a.includes('CMO')) return 'text-pink-400';
    if (a.includes('CFO')) return 'text-emerald-400';
    if (a.includes('CRITIC')) return 'text-amber-400';
    if (a.includes('SYSTEM')) return 'text-cyan-400';
    return 'text-sky-300';
  };

  const getActorIcon = (actor) => {
    if (!actor) return '🤖';
    const a = actor.toUpperCase();
    if (a.includes('CEO')) return '👑';
    if (a.includes('CMO')) return '📢';
    if (a.includes('CFO')) return '📊';
    if (a.includes('CRITIC')) return '⚖️';
    if (a.includes('SYSTEM')) return '⚡';
    return '🤖';
  };

  const hasNextPage = offset + limit < totalSessions;
  const hasPrevPage = offset > 0;

  const handleNextPage = () => {
    if (hasNextPage) setOffset(prev => prev + limit);
  };

  const handlePrevPage = () => {
    if (hasPrevPage) setOffset(prev => Math.max(0, prev - limit));
  };

  // Physically eject to document.body to conform to PORTAL ACTUATION LOCKOUT
  return ReactDOM.createPortal(
    <div 
      className="vault-modal-overlay fixed inset-0 flex items-center justify-center z-[9999] p-4 md:p-6 bg-black/80 backdrop-blur-sm"
      id="vault-modal-root"
      style={{ fontFamily: 'Inter, sans-serif' }}
    >
      <div 
        className="vault-modal-window relative flex flex-col w-full max-w-4xl h-[85vh] bg-[#0F172A] border border-slate-700/60 rounded-3xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] transform transition-all duration-300"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Glowing Top Border */}
        <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-600"></div>

        {/* Modal Header */}
        <div className="flex justify-between items-start p-6 bg-slate-950/40 border-b border-slate-800/80">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-2xl">📂</span>
              <h2 className="text-xl font-bold tracking-tight text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
                {project.project_name}
              </h2>
            </div>
            <p className="text-[10px] text-cyan-400 font-mono mt-1 uppercase tracking-widest">
              SOCRATIC ENVELOPE METRICS & TIMELINE PERSISTENCE
            </p>
          </div>
          <button 
            onClick={onClose} 
            className="p-1 px-2.5 rounded-lg border border-slate-800 bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-xs font-mono"
          >
            ✕ CLOSE
          </button>
        </div>

        {/* Dynamic Nav Tabs */}
        <div className="flex bg-slate-950/20 px-6 pt-3 border-b border-slate-800/60 gap-4">
          <button
            onClick={() => setActiveTab('briefing')}
            className={`px-4 py-2 text-xs font-bold tracking-wider font-mono uppercase border-b-2 transition-all duration-300 ${activeTab === 'briefing' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          >
            📋 Briefing Deck
          </button>
          <button
            onClick={() => setActiveTab('timeline')}
            className={`px-4 py-2 text-xs font-bold tracking-wider font-mono uppercase border-b-2 transition-all duration-300 ${activeTab === 'timeline' ? 'border-cyan-500 text-cyan-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
          >
            💬 Courtroom Timeline ({totalSessions})
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-[#0B0F19]">
          
          {/* Tab 1: Briefing Deck */}
          {activeTab === 'briefing' && (
            <div className="flex flex-col gap-6">
              {loadingEos ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 font-mono text-sm uppercase">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mb-4"></div>
                  Extracting briefing metadata...
                </div>
              ) : eosState ? (
                <>
                  {/* Brand and Description Info */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-sm">
                      <h4 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">Company Name & Tagline</h4>
                      <div className="text-base font-bold text-white mb-1" style={{ fontFamily: 'Outfit, sans-serif' }}>
                        {eosState.brand_name || eosState.company_name || 'N/A'}
                      </div>
                      <div className="text-xs text-cyan-400/80 italic font-mono">
                        {eosState.tagline ? `"${eosState.tagline}"` : 'No tagline generated.'}
                      </div>
                    </div>
                    <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-sm">
                      <h4 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-2">Industry Verticals</h4>
                      <div className="text-xs font-mono text-slate-300">
                        {eosState.industry ? eosState.industry.toUpperCase() : 'GENERAL OUTLINE'}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-1">
                        TARGET MARKET: {eosState.target_market || 'Universal Audience'}
                      </div>
                    </div>
                  </div>

                  {/* Problem & Solution */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-rose-950/10 border border-rose-500/10 rounded-2xl p-5">
                      <h4 className="text-[10px] font-mono text-rose-400 uppercase tracking-wider mb-2">⚠️ The Problem</h4>
                      <p className="text-xs text-rose-200/80 font-mono leading-relaxed" style={{ whiteSpace: 'pre-wrap' }}>
                        {eosState.problem_statement || 'No target problem outline has been formally structured yet.'}
                      </p>
                    </div>
                    <div className="bg-emerald-950/10 border border-emerald-500/10 rounded-2xl p-5">
                      <h4 className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider mb-2">💡 The Solution</h4>
                      <p className="text-xs text-emerald-200/80 font-mono leading-relaxed" style={{ whiteSpace: 'pre-wrap' }}>
                        {eosState.solution_statement || 'No structured strategic answer has been compiled yet.'}
                      </p>
                    </div>
                  </div>

                  {/* TAM/SAM/SOM Metrics */}
                  <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-sm">
                    <h4 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-3">Total Addressable Market Matrix (TAM/SAM/SOM)</h4>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div className="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
                        <span className="text-[9px] font-mono text-slate-500 block uppercase">TAM</span>
                        <span className="text-sm font-bold text-white font-mono">{eosState.tam || 'N/A'}</span>
                      </div>
                      <div className="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
                        <span className="text-[9px] font-mono text-slate-500 block uppercase">SAM</span>
                        <span className="text-sm font-bold text-cyan-400 font-mono">{eosState.sam || 'N/A'}</span>
                      </div>
                      <div className="bg-slate-950/40 rounded-xl p-3 border border-slate-800/60">
                        <span className="text-[9px] font-mono text-slate-500 block uppercase">SOM</span>
                        <span className="text-sm font-bold text-purple-400 font-mono">{eosState.som || 'N/A'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Generated Files / Artifacts */}
                  <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-sm">
                    <h4 className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-3">Generated Deliverables & Assets</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      
                      {/* Business Plan */}
                      {eosState.business_plan_md_path ? (
                        <a 
                          href={`/api/eos/documents/${getFileName(eosState.business_plan_md_path)}`}
                          target="_blank" 
                          rel="noreferrer"
                          className="flex items-center gap-3 bg-slate-950/40 hover:bg-slate-950/90 border border-slate-800/80 hover:border-cyan-500/40 rounded-xl p-3 text-left transition-all duration-300 text-decoration-none group"
                        >
                          <span className="text-2xl">📝</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">BUSINESS PLAN</span>
                            <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-400 transition-colors line-clamp-1">{getFileName(eosState.business_plan_md_path)}</span>
                          </div>
                        </a>
                      ) : (
                        <div className="flex items-center gap-3 bg-slate-950/10 border border-slate-800/40 rounded-xl p-3 opacity-40">
                          <span className="text-2xl">📝</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">BUSINESS PLAN</span>
                            <span className="text-xs font-semibold text-slate-600">Pending boardroom reconciliation</span>
                          </div>
                        </div>
                      )}

                      {/* Financial Model */}
                      {eosState.financial_xlsx_path ? (
                        <a 
                          href={`/api/eos/documents/${getFileName(eosState.financial_xlsx_path)}`}
                          target="_blank" 
                          rel="noreferrer"
                          className="flex items-center gap-3 bg-slate-950/40 hover:bg-slate-950/90 border border-slate-800/80 hover:border-cyan-500/40 rounded-xl p-3 text-left transition-all duration-300 text-decoration-none group"
                        >
                          <span className="text-2xl">📊</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">FINANCIAL MODEL</span>
                            <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-400 transition-colors line-clamp-1">{getFileName(eosState.financial_xlsx_path)}</span>
                          </div>
                        </a>
                      ) : (
                        <div className="flex items-center gap-3 bg-slate-950/10 border border-slate-800/40 rounded-xl p-3 opacity-40">
                          <span className="text-2xl">📊</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">FINANCIAL MODEL</span>
                            <span className="text-xs font-semibold text-slate-600">Pending ledger calculations</span>
                          </div>
                        </div>
                      )}

                      {/* Investor Pitch Deck */}
                      {eosState.investor_pptx_path ? (
                        <a 
                          href={`/api/eos/documents/${getFileName(eosState.investor_pptx_path)}`}
                          target="_blank" 
                          rel="noreferrer"
                          className="flex items-center gap-3 bg-slate-950/40 hover:bg-slate-950/90 border border-slate-800/80 hover:border-cyan-500/40 rounded-xl p-3 text-left transition-all duration-300 text-decoration-none group"
                        >
                          <span className="text-2xl">🎨</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">INVESTOR PPTX</span>
                            <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-400 transition-colors line-clamp-1">{getFileName(eosState.investor_pptx_path)}</span>
                          </div>
                        </a>
                      ) : (
                        <div className="flex items-center gap-3 bg-slate-950/10 border border-slate-800/40 rounded-xl p-3 opacity-40">
                          <span className="text-2xl">🎨</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">INVESTOR PPTX</span>
                            <span className="text-xs font-semibold text-slate-600">Pending design synthesis</span>
                          </div>
                        </div>
                      )}

                      {/* Customer Slides */}
                      {eosState.customer_pptx_path ? (
                        <a 
                          href={`/api/eos/documents/${getFileName(eosState.customer_pptx_path)}`}
                          target="_blank" 
                          rel="noreferrer"
                          className="flex items-center gap-3 bg-slate-950/40 hover:bg-slate-950/90 border border-slate-800/80 hover:border-cyan-500/40 rounded-xl p-3 text-left transition-all duration-300 text-decoration-none group"
                        >
                          <span className="text-2xl">📢</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">CUSTOMER PPTX</span>
                            <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-400 transition-colors line-clamp-1">{getFileName(eosState.customer_pptx_path)}</span>
                          </div>
                        </a>
                      ) : (
                        <div className="flex items-center gap-3 bg-slate-950/10 border border-slate-800/40 rounded-xl p-3 opacity-40">
                          <span className="text-2xl">📢</span>
                          <div>
                            <span className="text-[10px] font-mono text-slate-500 uppercase block">CUSTOMER PPTX</span>
                            <span className="text-xs font-semibold text-slate-600">Pending product roadmap</span>
                          </div>
                        </div>
                      )}

                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-slate-500 font-mono py-20">
                  No active Enterprise Operating System record is defined.
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Courtroom Timeline */}
          {activeTab === 'timeline' && (
            <div className="flex flex-col h-full gap-4">
              {loadingHistory ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 font-mono text-sm uppercase">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mb-4"></div>
                  Analyzing courtroom dialogue logs...
                </div>
              ) : history.length === 0 ? (
                <div className="bg-slate-950/30 border border-slate-900 border-dashed p-12 rounded-2xl text-center text-slate-500 font-mono text-sm uppercase">
                  Zero historical boardroom courtroom debates logged for this workspace.
                  <br />
                  <span className="text-[10px] text-cyan-400 mt-2 block font-normal tracking-wide">
                    Actuate this ledger inside the War Room to start real-time debates.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  {/* Sessions Container */}
                  <div className="flex flex-col gap-8">
                    {history.map((session, sIdx) => (
                      <div 
                        key={sIdx} 
                        className="session-block bg-slate-900/30 border border-slate-800/80 rounded-2xl p-5 flex flex-col gap-4 backdrop-blur-sm"
                      >
                        {/* Session Header */}
                        <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                          <div>
                            <span className="text-[9px] font-mono text-slate-500 uppercase tracking-widest block">DEBATE TOPIC</span>
                            <span className="text-sm font-bold text-white font-mono line-clamp-1">{session.topic}</span>
                          </div>
                          <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/30 border border-cyan-500/20 px-2 py-0.5 rounded-full">
                            {session.started ? new Date(session.started).toLocaleDateString() : 'N/A'}
                          </span>
                        </div>

                        {/* Chronological Chat Messages */}
                        <div className="flex flex-col gap-3 max-h-[300px] overflow-y-auto pr-1">
                          {session.messages.map((msg, mIdx) => {
                            const actorName = msg.agent || 'SYSTEM';
                            const isSystem = actorName === 'SYSTEM';
                            return (
                              <div key={mIdx} className="chat-msg flex gap-3 text-xs bg-slate-950/30 border border-slate-900/60 rounded-xl p-3">
                                <span className="text-sm self-start">{getActorIcon(actorName)}</span>
                                <div className="flex flex-col gap-1 w-full">
                                  <div className="flex justify-between items-center">
                                    <strong className={`${getActorColor(actorName)} font-mono`}>{actorName}</strong>
                                    <span className="text-[9px] font-mono text-slate-600">
                                      {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}
                                    </span>
                                  </div>
                                  <p className="text-slate-300 font-mono leading-relaxed" style={{ whiteSpace: 'pre-wrap' }}>
                                    {msg.message}
                                  </p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Pagination Controls */}
                  <div className="flex justify-between items-center bg-slate-950/40 border border-slate-800/80 rounded-xl p-3 font-mono text-[10px] text-slate-400">
                    <button 
                      onClick={handlePrevPage} 
                      disabled={!hasPrevPage} 
                      className={`p-1.5 px-3 rounded-lg border border-slate-800 bg-slate-900/60 text-slate-300 hover:text-white transition-colors ${!hasPrevPage ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-800'}`}
                    >
                      ◀ PREVIOUS
                    </button>
                    <span>
                      SESSIONS: {offset + 1} - {Math.min(offset + limit, totalSessions)} OF {totalSessions}
                    </span>
                    <button 
                      onClick={handleNextPage} 
                      disabled={!hasNextPage} 
                      className={`p-1.5 px-3 rounded-lg border border-slate-800 bg-slate-900/60 text-slate-300 hover:text-white transition-colors ${!hasNextPage ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-800'}`}
                    >
                      NEXT ▶
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-6 bg-slate-950/60 border-t border-slate-800/80 flex justify-end">
          <button
            onClick={() => handleActuateProject(project)}
            className="flex items-center gap-2 px-8 py-3.5 bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-600 hover:from-cyan-400 hover:to-indigo-400 text-white font-bold text-xs font-mono uppercase tracking-wider rounded-2xl transition-all duration-300 hover:-translate-y-0.5 shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] cursor-pointer"
          >
            🚀 Actuate In Adversarial War Room ➜
          </button>
        </div>

      </div>
    </div>,
    document.body
  );
}
