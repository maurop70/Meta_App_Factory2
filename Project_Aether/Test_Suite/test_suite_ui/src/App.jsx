import { useState, useEffect, useRef } from 'react'
import SupportFAB from './SupportFAB.jsx'

const API = 'http://localhost:5005';

function FileUploader() {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(`${API}/api/documents/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ error: e.message });
    } finally { setUploading(false); }
  };

  const onDrop = (e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); };

  return (
    <div style={{ padding: '1rem' }}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        style={{ border: `2px dashed ${dragOver ? '#6366f1' : 'rgba(99,102,241,0.25)'}`, borderRadius: 12, padding: '2rem', textAlign: 'center', cursor: 'pointer', background: dragOver ? 'rgba(99,102,241,0.08)' : 'transparent', transition: 'all 0.2s' }}
      >
        <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.csv,.md" hidden onChange={(e) => handleUpload(e.target.files[0])} />
        <div style={{ fontSize: '2rem', marginBottom: 8 }}>{uploading ? '⏳' : '📄'}</div>
        <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
          {uploading ? 'Parsing document...' : 'Drop a file here or click to upload'}
        </div>
        <div style={{ color: '#475569', fontSize: '0.75rem', marginTop: 4 }}>PDF, DOCX, TXT, CSV, MD</div>
      </div>
      {result && (
        <div style={{ marginTop: '1rem', padding: '0.8rem', borderRadius: 10, background: result.error ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.08)', border: `1px solid ${result.error ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`, fontSize: '0.8rem' }}>
          {result.error ? `❌ ${result.error}` : (
            <div>
              <strong>✅ ${result.category}</strong> ({(result.confidence * 100).toFixed(0)}%)
              <div style={{ color: '#94a3b8', marginTop: 4 }}>{result.extracted?.summary}</div>
              <div style={{ color: '#64748b', marginTop: 4, fontSize: '0.7rem' }}>
                Routed to: {result.routing?.destination || 'index only'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Chat() {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const end = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  const send = async () => {
    const p = input.trim();
    if (!p || streaming) return;
    setInput('');
    setMsgs(m => [...m, { role: 'user', text: p }]);
    setStreaming(true);
    setMsgs(m => [...m, { role: 'assistant', text: '' }]);

    try {
      const res = await fetch(`${API}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p }),
      });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.error || ev.done) break;
            if (ev.text) setMsgs(m => {
              const c = [...m];
              c[c.length - 1] = { role: 'assistant', text: c[c.length - 1].text + ev.text };
              return c;
            });
          } catch {}
        }
      }
    } catch (e) {
      setMsgs(m => {
        const c = [...m];
        c[c.length - 1] = { role: 'assistant', text: '❌ ' + e.message };
        return c;
      });
    } finally { setStreaming(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0a0e17', color: '#e2e8f0', fontFamily: 'Inter, sans-serif' }}>
      <header style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgba(99,102,241,0.15)', background: 'rgba(10,14,23,0.95)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: '1.2rem', background: 'linear-gradient(135deg, #e2e8f0, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Test_Suite
        </h1>
          <button onClick={() => setShowUploader(!showUploader)} style={{ background: showUploader ? 'rgba(99,102,241,0.2)' : 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', padding: '0.4rem 0.8rem', borderRadius: 8, color: '#e2e8f0', fontSize: '0.8rem', cursor: 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: 6 }}>
            📄 Upload
          </button>
      </header>
      {showUploader && <FileUploader />}
      <div style={{ flex: 1, overflow: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%', padding: '0.7rem 1rem', borderRadius: '12px', fontSize: '0.85rem', lineHeight: 1.5, background: m.role === 'user' ? 'linear-gradient(135deg, #6366f1, #7c3aed)' : 'rgba(30,41,59,0.8)', border: m.role === 'assistant' ? '1px solid rgba(99,102,241,0.15)' : 'none', color: 'white' }}>
            {m.text}
          </div>
        ))}
        <div ref={end} />
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', padding: '0.8rem 1rem', borderTop: '1px solid rgba(99,102,241,0.15)', background: 'rgba(10,14,23,0.5)' }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Ask anything..." disabled={streaming} style={{ flex: 1, background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(99,102,241,0.15)', borderRadius: '10px', padding: '0.6rem 1rem', color: '#e2e8f0', fontSize: '0.85rem', outline: 'none' }} />
        <button onClick={send} disabled={streaming || !input.trim()} style={{ width: 40, height: 40, borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #6366f1, #7c3aed)', color: 'white', fontSize: '1.1rem', cursor: 'pointer' }}>&uarr;</button>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <>
      <Chat />
      <SupportFAB activeApp="Test_Suite" themeColor="#818cf8" />
    </>
  );
}
