import React, { useState, useRef, useEffect } from 'react';
import apiClient from '../services/api';
import { useAuth } from '../context/AuthContext';
import './ConciergeChatWidget.css';

/**
 * Floating Concierge Chat Widget.
 *
 * A glassmorphism chat bubble pinned to the bottom-right corner. Clicking it
 * slides in a chat panel that talks to the backend Customer Concierge agent
 * (dual-auth: the logged-in user's Bearer JWT is attached automatically by the
 * apiClient interceptor).
 *
 * Only rendered for authenticated users — on the login screen (no jwtPayload)
 * the component renders nothing.
 */
const ConciergeChatWidget = () => {
  const { jwtPayload } = useAuth();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]); // { role: 'user' | 'agent' | 'error', text }
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const streamRef = useRef(null);
  const inputRef = useRef(null);

  // Keep the message stream pinned to the latest message.
  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Focus the composer when the panel opens.
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Hide the widget entirely when the user is not authenticated (login screen).
  if (!jwtPayload) {
    return null;
  }

  const sendMessage = async () => {
    const messageText = input.trim();
    if (!messageText || loading) return;

    setMessages((prev) => [...prev, { role: 'user', text: messageText }]);
    setInput('');
    setLoading(true);

    try {
      // AXIOS PREFIX TRUNCATION rule: do NOT include the '/api' prefix here —
      // the apiClient baseURL already resolves to the gateway's /api root.
      const { data } = await apiClient.post('/agent/concierge/chat', { query: messageText });
      setMessages((prev) => [
        ...prev,
        { role: 'agent', text: data?.response || 'No response was returned.' },
      ]);
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || 'The concierge is unavailable right now.';
      setMessages((prev) => [...prev, { role: 'error', text: detail }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="concierge-root">
      {isOpen && (
        <div className="concierge-panel" role="dialog" aria-label="Concierge support chat">
          <div className="concierge-header">
            <div className="concierge-header-title">
              <strong>Concierge Support</strong>
              <span>Ask about your maintenance workspace</span>
            </div>
            <button
              type="button"
              className="concierge-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
            >
              &times;
            </button>
          </div>

          <div className="concierge-messages" ref={streamRef}>
            {messages.length === 0 && !loading && (
              <div className="concierge-empty">
                Hi! I can help you troubleshoot work orders, inventory, and your tenant
                setup. How can I assist?
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`concierge-msg ${m.role}`}>
                {m.text}
              </div>
            ))}

            {loading && (
              <div className="concierge-typing" aria-label="Concierge is typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            )}
          </div>

          <div className="concierge-composer">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your question…"
              disabled={loading}
            />
            <button
              type="button"
              className="concierge-send"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        className="concierge-bubble"
        onClick={() => setIsOpen((v) => !v)}
        aria-label={isOpen ? 'Close concierge chat' : 'Open concierge chat'}
        aria-expanded={isOpen}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
      </button>
    </div>
  );
};

export default ConciergeChatWidget;
