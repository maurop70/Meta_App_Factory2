import { useState, useRef, useEffect } from 'react';
import axios from 'axios';

// ═══════════════════════════════════════════════════════════
//  EXECUTIVE COMMAND — Zero-Trust Intent Gateway
//  Routes operator objectives to DIRECTIVE or KNOWLEDGE
// ═══════════════════════════════════════════════════════════

// Minimal Markdown renderer — bold, code, headers, bullets
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, i) => {
    if (line.startsWith('### ')) return <h4 key={i} style={{ color: '#a78bfa', margin: '0.6rem 0 0.2rem', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{line.slice(4)}</h4>;
    if (line.startsWith('## '))  return <h3 key={i} style={{ color: '#c4b5fd', margin: '0.8rem 0 0.3rem', fontSize: '0.9rem' }}>{line.slice(3)}</h3>;
    if (line.startsWith('# '))   return <h2 key={i} style={{ color: '#ede9fe', margin: '1rem 0 0.4rem', fontSize: '1rem' }}>{line.slice(2)}</h2>;
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '2px' }}><span style={{ color: '#7c3aed', flexShrink: 0 }}>▸</span><span style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>{inlineMarkdown(line.slice(2))}</span></div>;
    }
    if (line.trim() === '') return <div key={i} style={{ height: '6px' }} />;
    return <p key={i} style={{ margin: '0 0 4px', color: '#cbd5e1', fontSize: '0.8rem', lineHeight: 1.5 }}>{inlineMarkdown(line)}</p>;
  });
}

function inlineMarkdown(text) {
  // Bold: **text** → <strong>
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i} style={{ color: '#e2e8f0' }}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} style={{ background: 'rgba(124,58,237,0.2)', color: '#a78bfa', padding: '1px 4px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '0.75em' }}>{part.slice(1, -1)}</code>;
    return part;
  });
}

export default function ExecutiveCommand({ isOpen, onClose, onNavigateBuilder }) {
  const [input, setInput] = useState('');
  const [chatLog, setChatLog] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const inputRef = useRef(null);
  const scrollRef = useRef(null);
  const SATURATION_THRESHOLD = 10;

  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 150);
  }, [isOpen]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatLog]);

  const submit = async () => {
    const raw = input.trim();
    if (!raw || isLoading) return;

    setInput('');
    setChatLog(prev => [...prev, { role: 'operator', text: raw }]);
    setIsLoading(true);

    try {
      const res = await axios.post('/api/v1/architect/translate', {
        raw_objective: raw,
      });

      const { response_type, payload } = res.data;

      if (response_type === 'DIRECTIVE') {
        // ── ACTION BRANCH: Hand off to Builder and close ──
        localStorage.setItem('mode_a_handoff_prompt', payload);
        setChatLog(prev => [...prev, {
          role: 'directive',
          text: `✅ **DIRECTIVE SYNTHESIZED** — Routing to Builder Chat...\n\n\`\`\`\n${payload.slice(0, 200)}...\n\`\`\``
        }]);
        // Brief delay so the operator sees the confirmation before nav
        setTimeout(() => {
          onNavigateBuilder();
          onClose();
        }, 1200);
      } else {
        // ── KNOWLEDGE BRANCH: Render inline ──
        setChatLog(prev => [...prev, { role: 'knowledge', text: payload }]);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Executive Architect offline.';
      setChatLog(prev => [...prev, { role: 'error', text: `⚠️ ${detail}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  // ── SATURATION MONITOR ─────────────────────────────────
  useEffect(() => {
    if (chatLog.length >= SATURATION_THRESHOLD && !isCompressing && !isLoading) {
      executeCompression();
    }
  }, [chatLog.length]);

  // ── COMPRESSION ENGINE ─────────────────────────────────
  const executeCompression = async () => {
    if (isCompressing || chatLog.length === 0) return;
    setIsCompressing(true);
    try {
      const res = await axios.post('/api/v1/architect/compress', {
        chat_log: chatLog.map(m => ({ role: m.role, text: m.text })),
      });
      const { state_payload } = res.data;
      // Zero-Loss: clear log, prepend compressed state payload
      setChatLog([{
        role: 'system_state',
        text: state_payload,
      }]);
    } catch (err) {
      // Non-fatal: just append a warning, don't clear
      setChatLog(prev => [...prev, {
        role: 'error',
        text: `⚠️ Compression failed: ${err.response?.data?.detail || err.message}. Context preserved.`
      }]);
    } finally {
      setIsCompressing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          backdropFilter: 'blur(4px)',
          zIndex: 9998,
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed',
        bottom: '90px',
        right: '24px',
        width: '420px',
        maxHeight: '600px',
        display: 'flex',
        flexDirection: 'column',
        background: 'linear-gradient(145deg, #1e1b4b, #0f0f1a)',
        border: '1px solid rgba(124,58,237,0.4)',
        borderRadius: '16px',
        boxShadow: '0 0 40px rgba(124,58,237,0.25), 0 20px 60px rgba(0,0,0,0.5)',
        zIndex: 9999,
        overflow: 'hidden',
      }}>

        {/* Header */}
        <div style={{
          padding: '14px 16px',
          background: 'linear-gradient(90deg, rgba(124,58,237,0.3), rgba(99,102,241,0.15))',
          borderBottom: '1px solid rgba(124,58,237,0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7c3aed', boxShadow: '0 0 8px #7c3aed', animation: 'pulse 2s infinite' }} />
            <span style={{ color: '#ede9fe', fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.08em' }}>EXECUTIVE ARCHITECT</span>
            <span style={{ color: '#7c3aed', fontSize: '0.65rem', background: 'rgba(124,58,237,0.15)', padding: '2px 6px', borderRadius: '4px', border: '1px solid rgba(124,58,237,0.3)' }}>PORT 5060</span>
            {chatLog.length > 0 && (
              <span style={{
                fontSize: '0.6rem',
                color: chatLog.length >= SATURATION_THRESHOLD ? '#f59e0b' : '#475569',
                background: chatLog.length >= SATURATION_THRESHOLD ? 'rgba(245,158,11,0.1)' : 'transparent',
                border: chatLog.length >= SATURATION_THRESHOLD ? '1px solid rgba(245,158,11,0.3)' : 'none',
                padding: '1px 5px',
                borderRadius: '3px',
                fontFamily: 'monospace',
              }}>
                {isCompressing ? '⟳ COMPRESSING' : `${chatLog.length}/${SATURATION_THRESHOLD} msgs`}
              </span>
            )}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1rem', lineHeight: 1 }}>✕</button>
        </div>

        {/* Chat log */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {chatLog.length === 0 && (
            <div style={{ color: '#64748b', fontSize: '0.78rem', textAlign: 'center', paddingTop: '20px', lineHeight: 1.6 }}>
              <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>🧠</div>
              <strong style={{ color: '#7c3aed' }}>Executive Architect Online</strong>
              <br />
              State your objective in plain language.<br />
              ACTION intents are converted to strict Builder directives.<br />
              KNOWLEDGE queries return architectural guidance.
            </div>
          )}

          {chatLog.map((msg, i) => (
            <div key={i} style={{
              alignSelf: msg.role === 'operator' ? 'flex-end' : 'flex-start',
              maxWidth: '90%',
            }}>
              {msg.role === 'system_state' && (
                <div style={{
                  background: 'linear-gradient(135deg, rgba(245,158,11,0.08), rgba(124,58,237,0.08))',
                  border: '1px solid rgba(245,158,11,0.3)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  width: '100%',
                }}>
                  <div style={{ fontSize: '0.6rem', color: '#f59e0b', marginBottom: '6px', fontWeight: 700, letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>⚡</span> COMPRESSED STATE PAYLOAD — ZERO-LOSS CONTINUITY
                  </div>
                  <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.78rem', lineHeight: 1.6, fontStyle: 'italic' }}>{msg.text}</p>
                </div>
              )}
              {msg.role === 'operator' && (
                <div style={{
                  background: 'rgba(124,58,237,0.25)',
                  border: '1px solid rgba(124,58,237,0.4)',
                  borderRadius: '12px 12px 2px 12px',
                  padding: '8px 12px',
                  color: '#e2e8f0',
                  fontSize: '0.82rem',
                  lineHeight: 1.5,
                }}>{msg.text}</div>
              )}
              {msg.role === 'knowledge' && (
                <div style={{
                  background: 'rgba(15,23,42,0.8)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  borderRadius: '2px 12px 12px 12px',
                  padding: '10px 14px',
                }}>
                  <div style={{ fontSize: '0.65rem', color: '#6366f1', marginBottom: '6px', fontWeight: 700, letterSpacing: '0.1em' }}>KNOWLEDGE</div>
                  {renderMarkdown(msg.text)}
                </div>
              )}
              {msg.role === 'directive' && (
                <div style={{
                  background: 'rgba(124,58,237,0.1)',
                  border: '1px solid rgba(124,58,237,0.5)',
                  borderRadius: '2px 12px 12px 12px',
                  padding: '10px 14px',
                }}>
                  <div style={{ fontSize: '0.65rem', color: '#a78bfa', marginBottom: '6px', fontWeight: 700, letterSpacing: '0.1em' }}>DIRECTIVE → BUILDER</div>
                  {renderMarkdown(msg.text)}
                </div>
              )}
              {msg.role === 'error' && (
                <div style={{
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  color: '#fca5a5',
                  fontSize: '0.8rem',
                }}>{msg.text}</div>
              )}
            </div>
          ))}

          {isLoading && (
            <div style={{ alignSelf: 'flex-start', color: '#7c3aed', fontSize: '0.78rem', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
              Classifying intent and routing to cognitive engine...
            </div>
          )}
          <div ref={scrollRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: '12px 14px',
          borderTop: '1px solid rgba(124,58,237,0.2)',
          display: 'flex',
          gap: '8px',
          flexShrink: 0,
          background: 'rgba(15,23,42,0.6)',
        }}>
          <input
            ref={inputRef}
            id="executive-command-input"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !isLoading) submit(); }}
            placeholder={isLoading ? 'Processing...' : 'State your objective...'}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px 12px',
              background: 'rgba(30,27,75,0.8)',
              border: '1px solid rgba(124,58,237,0.3)',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '0.82rem',
              outline: 'none',
            }}
          />
          <button
            id="executive-command-submit"
            onClick={submit}
            disabled={isLoading || !input.trim()}
            style={{
              padding: '10px 14px',
              background: isLoading ? 'rgba(124,58,237,0.3)' : 'linear-gradient(135deg, #7c3aed, #6366f1)',
              border: 'none',
              borderRadius: '8px',
              color: 'white',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {isLoading ? '⟳' : '▶'}
          </button>
        </div>
      </div>
    </>
  );
}
