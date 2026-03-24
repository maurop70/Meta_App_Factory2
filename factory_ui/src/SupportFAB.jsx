import { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000';

// ═══════════════════════════════════════════════════════════
//  SCOPED SUPPORT FAB — Commercial Concierge
//  User-first language · No technical jargon · Brand-aligned
// ═══════════════════════════════════════════════════════════

// ── App-Specific Knowledge (User-Friendly Labels) ────────
const APP_KNOWLEDGE = {
  Alpha_V2_Genesis: {
    displayName: 'Alpha Trading Suite',
    focus: 'Strategy Ledger & Market Analysis tools',
    greeting: "Hi! I'm your trading assistant. I can help you use the Strategy Ledger, explore Market Analysis tools, or customize your dashboard. What can I do for you?",
    topics: [
      'How to use the Strategy Ledger',
      'Market Analysis breakdown',
      'Understanding my portfolio performance',
      'Where can I find my strategy reports?',
    ],
  },
  Resonance: {
    displayName: 'Resonance',
    focus: 'Compliance & Data Retention Manager (Privacy & Siloed Data)',
    greeting: "Welcome! I'm here to help with anything related to Resonance — focusing on Privacy, Siloed Data, and the Compliance & Data Retention Manager. How can I help?",
    topics: [
      'How is my privacy protected?',
      'Understanding Siloed Data compliance',
      'Managing Data Retention policies',
      'Where are my saved documents?',
    ],
  },
  _default: {
    displayName: 'Support',
    focus: 'Getting You Started',
    greeting: "Hi there! I'm your personal guide. Whether you need help navigating, finding a feature, or just have a question — I'm here. What would you like to know?",
    topics: [
      'How do I get started?',
      'Help me find a feature',
      'How is my data kept secure?',
      'Who do I contact for billing?',
    ],
  },
};

// ── Commercial Concierge System Prompt ────────────────────
function buildSystemPrompt(appName) {
  const config = APP_KNOWLEDGE[appName] || APP_KNOWLEDGE._default;
  const friendlyName = config.displayName || appName || 'our platform';

  return [
    `You are a friendly, approachable support concierge for ${friendlyName}.`,
    `Your focus area is: ${config.focus}.`,
    '',
    'YOUR PERSONALITY:',
    '- Speak like a knowledgeable and helpful concierge at a premium hotel — warm, clear, and professional.',
    '- Use plain, everyday English. Assume the user knows nothing about how the software is built.',
    '- Be brief but thorough. If something is complex, break it into simple numbered steps.',
    '- When offering to take action, say things like "I can help with that — shall I get started?" or "Let me walk you through it."',
    '',
    'LANGUAGE RULES (CRITICAL):',
    '1. NEVER use technical jargon: no "SOPs," "protocols," "pipelines," "webhooks," "endpoints," "system prompts," or "architecture."',
    '2. NEVER mention internal AI names (Gemini, Claude, GPT, Antigravity), agent roles (CFO, CMO, Architect, Critic), or backend systems.',
    '3. NEVER reveal workflow logic, code, n8n structures, API keys, encryption details, or internal file names.',
    '4. If asked "How does this work internally?" — answer with the user benefit: "Behind the scenes, we coordinate a team of specialists to get you the best result. Would you like to see what they can do?"',
    '5. Replace technical concepts with user-friendly equivalents:',
    '   - "Triad Execute" → "I\'ll coordinate our specialists to handle that for you"',
    '   - "Auto-Heal triggered" → "We detected an issue and already fixed it automatically"',
    '   - "Circuit Breaker" → "Our safety net caught an error before it affected you"',
    '   - "SSE streaming" → "live updates"',
    '   - "Registry" → "your apps"',
    '   - "Vault Keys" → "encrypted security"',
    '',
    'TRUST & REASSURANCE:',
    '- If data security comes up, reassure simply: "Your data is fully encrypted and kept completely separate from other accounts. We take privacy very seriously."',
    '- Never say ".ENV LOCK," "Fernet encryption," or "PBKDF2." Just say "enterprise-grade encryption" or "bank-level security."',
    '',
    `TOPICS YOU HELP WITH for ${friendlyName}:`,
    ...config.topics.map(t => `  • ${t}`),
    '',
    'Keep responses concise, helpful, and professional. Use emoji sparingly for visual clarity.',
  ].join('\n');
}

// ═══════════════════════════════════════════════════════════
//  USAGE WALKTHROUGHS — Feature-specific UI instructions
//  Fires BEFORE the security guard for "how do I use" queries
// ═══════════════════════════════════════════════════════════

const USAGE_INTENT_SIGNALS = [
  'how do i use', 'how to use', 'how can i use', 'how do i start',
  'how to start', 'where do i', 'where can i', 'walk me through',
  'help me use', 'show me how', 'get started with', 'tutorial',
  'step by step', 'guide me', 'how does the', 'what does the',
  'how do i run', 'how to run', 'how do i send', 'can i upload',
  'how do i upload', 'how to upload', 'i want to', 'i need to',
];

const USAGE_WALKTHROUGHS = [
  // ── BUILD / CREATE must come FIRST (highest priority) ──────
  {
    keywords: ['build', 'create', 'new app', 'make an app', 'scaffold', 'generate', 'develop', 'translator', 'converter'],
    response: "To build a new app:\n\n1. Open the **Builder Chat** from the sidebar\n2. Describe what you want to build in plain language — for example: \"Build me a customer feedback dashboard with charts\"\n3. Choose a blueprint if prompted (or we'll pick the best one for you)\n4. Watch the live build progress as your app is assembled\n\nOnce it's built, it'll appear in the **Active Apps** section of the sidebar!",
  },
  {
    keywords: ['triad', 'triad execute', 'specialist', 'specialists', 'coordinate'],
    response: "You can start a Triad execution by uploading your business plan directly here in the chat, or using the **Refine App** section in the sidebar. I'll handle the coordination with the specialists for you.\n\nHere's how:\n1. 📎 Click the attachment icon in the **Builder Chat** to upload your file\n2. Or paste your prompt into the **Command Palette** for quick actions\n3. Our team of specialists will review and respond with recommendations\n\nWould you like to try it now?",
  },
  {
    keywords: ['refine', 'improve', 'feedback', 'iterate', 'fix', 'change'],
    response: "To refine or improve your app:\n\n1. Click **Refine App** in the left sidebar\n2. Select the app you want to improve from the dropdown\n3. Describe what you'd like changed in plain language — for example: \"Make the dashboard more visual\" or \"Add a dark mode\"\n4. Hit send, and we'll analyze your feedback and apply the improvements\n\nYou can refine as many times as you need — each round builds on the last!",
  },
  // ── FILE UPLOAD (lower priority — no longer includes "document") ──
  {
    keywords: ['file', 'files', 'upload', 'attach', 'drop'],
    response: "Uploading files is easy! Here are your options:\n\n1. 📎 **Builder Chat** — Click the attachment clip icon at the bottom of the chat to upload any file directly\n2. 📋 **Refine App** — Use the sidebar to submit files for detailed analysis\n3. 🎨 **Brand Studio** — Upload brand assets like logos and style guides\n\nSupported formats include PDFs, documents, images, and spreadsheets. Just drop your file in and we'll take it from here!",
  },
  {
    keywords: ['command', 'commands', 'palette', 'quick action', 'shortcut'],
    response: "The Command Palette gives you quick access to common actions:\n\n1. Click **Command Palette** in the left sidebar\n2. Browse the available commands — each one triggers a specific action\n3. Click any command to execute it instantly\n\nThink of it like a menu of shortcuts for things you do often!",
  },
  {
    keywords: ['brand', 'branding', 'logo', 'style', 'identity', 'brand studio'],
    response: "The Brand Studio helps you create a consistent visual identity:\n\n1. Click **Brand Studio** in the left sidebar\n2. Choose between AI-generated branding or manual setup\n3. Upload your logo, pick colors, and define your brand voice\n4. Your brand settings will be applied across all your apps\n\nWant me to help you set up your brand identity?",
  },
  {
    keywords: ['alert', 'alerts', 'notification', 'notify', 'threshold'],
    response: "To set up alerts:\n\n1. Go to your app's dashboard\n2. Look for the alerts or notification settings panel\n3. Set your thresholds — for example: \"Notify me when portfolio drops 5%\"\n4. Choose how you'd like to be notified (in-app, email, etc.)\n\nAlerts are checked automatically, so once they're set, you can relax!",
  },
  {
    keywords: ['dashboard', 'layout', 'widget', 'customize', 'arrange'],
    response: "To customize your dashboard:\n\n1. Open your app from the **Active Apps** section\n2. Look for the layout or customize option (usually a gear icon)\n3. Drag and drop widgets to rearrange them\n4. Add new widgets from the widget library\n\nYour layout saves automatically, so it'll look the same next time you log in!",
  },
];

/**
 * Usage Intent Detector: checks if the user is asking HOW TO USE a feature.
 * Returns a walkthrough string if matched, or null to continue to the security guard.
 *
 * PRIORITY LOGIC:
 * 1. Build/create intent phrases are checked FIRST (e.g., "I want to create...")
 * 2. Single-keyword matches are checked in array order (build > file > others)
 * 3. This prevents ambiguous words like "document" from overriding build intent.
 */
function usageWalkthroughCheck(userText) {
  const lower = userText.toLowerCase();

  // Must contain a usage-intent signal
  const hasUsageIntent = USAGE_INTENT_SIGNALS.some(signal => lower.includes(signal));
  if (!hasUsageIntent) return null;

  // PHASE 1: Check for BUILD/CREATE intent phrases first (multi-word priority)
  const BUILD_PHRASES = [
    'create a', 'build a', 'make a', 'develop a', 'generate a',
    'i want to create', 'i want to build', 'i want to make',
    'i need to create', 'i need to build', 'i need a',
    'how to create', 'how to build', 'how do i create', 'how do i build',
    'can i create', 'can i build', 'can you create', 'can you build',
  ];
  if (BUILD_PHRASES.some(phrase => lower.includes(phrase))) {
    return USAGE_WALKTHROUGHS[0].response; // BUILD walkthrough (index 0)
  }

  // PHASE 2: Standard keyword matching (in array order, so build > file > others)
  for (const walkthrough of USAGE_WALKTHROUGHS) {
    if (walkthrough.keywords.some(kw => lower.includes(kw))) {
      return walkthrough.response;
    }
  }

  // Generic usage response if intent detected but no specific feature matched
  return "I'd love to help! Here's a quick overview of what you can do:\n\n" +
    "📝 **Builder Chat** — Describe what you need and we'll build it\n" +
    "🔄 **Refine App** — Submit feedback to improve an existing app\n" +
    "🎨 **Brand Studio** — Set up your visual identity\n" +
    "⚡ **Command Palette** — Quick actions and shortcuts\n\n" +
    "Which one would you like to explore?";
}

// ═══════════════════════════════════════════════════════════
//  SYSTEM GUARD — Security Deflections (Architecture Only)
//  Only fires when the user asks about internals, NOT usage
// ═══════════════════════════════════════════════════════════

// Architecture-only keywords (these trigger ONLY without usage intent)
const GUARD_KEYWORDS = [
  'system prompt', 'source code',
  'n8n', 'webhook', 'architecture',
  'backend', 'how do you work', 'show me your', 'reveal', 'expose',
  'api key', 'secret', 'credential', 'password',
  'circuit breaker', 'auto-heal', 'auto heal', 'self-heal',
  'agent names', 'cfo agent', 'cmo agent', 'hardened files',
  'watchdog', 'recovery sync', 'local_pending', 'safe_post',
  'healed_post', 'bootstrap_env', 'aegis', 'binding protocol',
  'show me the code', 'what model', 'what ai', 'which ai',
];

const VAULT_ASSURANCE = "\n\n🔒 Your data is fully encrypted and completely private. It's never shared or exposed during our conversation.";

/**
 * System Guard: Two-tier check.
 * 1. Usage intent → returns a helpful walkthrough (no block)
 * 2. Architecture intent → returns a security disclaimer (block)
 * 3. Neither → returns null (safe to proceed to API)
 */
function systemGuardCheck(userText, appConfig) {
  // TIER 1: Check usage intent FIRST — helpful walkthroughs
  const walkthrough = usageWalkthroughCheck(userText);
  if (walkthrough) return walkthrough;

  // TIER 2: Check architecture/internals — security deflection
  const lower = userText.toLowerCase();
  const triggered = GUARD_KEYWORDS.some(kw => lower.includes(kw));
  if (!triggered) return null;

  // The Polite Guard: dynamic feature substitution based on active app
  const f1 = appConfig.topics[0]?.replace('How do I ', '')?.replace('How to ', '')?.replace(/\?$/, '') || 'dashboard layout';
  const f2 = appConfig.topics[1]?.replace('How do I ', '')?.replace('How to ', '')?.replace(/\?$/, '') || 'feature navigation';
  
  const disclaimer = `To maintain maximum security and system integrity, those specific back-end processes are automated. However, I can help you with ${f1} or ${f2} right now.`;
  
  return disclaimer + VAULT_ASSURANCE;
}

// ═══════════════════════════════════════════════════════════
//  RESPONSE SCRUBBER — Post-API proprietary term filter
//  Strips any internal terms that leak through the LLM
// ═══════════════════════════════════════════════════════════

const SCRUB_PATTERNS = [
  // Agent/module names
  /\b(auto_heal|circuit_breaker|n8n_bridge|safe_post|healed_post|recovery_sync)\b/gi,
  /\b(vault_client|local_state_manager|bootstrap_env|n8n_watchdog)\b/gi,
  /\b(aegis_agent|binding_protocol|resilience_config)\b/gi,
  // File paths
  /[A-Z]:\\[^\s"']+/gi,
  /\/(?:home|Users)\/[^\s"']+/gi,
  // Webhook URLs
  /https?:\/\/[\w.-]*\.n8n\.cloud\/webhook\/[\w-]+/gi,
  // API keys (partial)
  /AIzaSy[A-Za-z0-9_-]{30,}/g,
  /eyJ[A-Za-z0-9_-]{50,}/g,
];

// Provide user-friendly terminology swaps
const GLOSSARY_MAP = [
  [/Triad Execute/gi, "Launch Process"],
  [/SOP Protocol/gi, "Optimized Workflow"],
  [/\bAtomizer\b/gi, "Feature Breakdown"],
  [/Vault Keys?/gi, "Security Encryption"],
  [/Hardened Files?/gi, "Protected System Core"],
];

function scrubResponse(text) {
  let scrubbed = text;
  // Apply hard redactions for secrets
  for (const pattern of SCRUB_PATTERNS) {
    scrubbed = scrubbed.replace(pattern, '[REDACTED]');
  }
  // Apply commercial translation glossary
  for (const [pattern, translation] of GLOSSARY_MAP) {
    scrubbed = scrubbed.replace(pattern, translation);
  }
  return scrubbed;
}

/**
 * Convert raw API error messages into user-friendly responses.
 * The user never sees "403", "leaked", or raw error details.
 */
function friendlyError(errorText) {
  const lower = (errorText || '').toLowerCase();
  if (lower.includes('403') || lower.includes('forbidden') || lower.includes('leaked') || lower.includes('permission')) {
    return 'We\'re doing a quick security update right now — the assistant will be back in just a moment. ' +
           'Your data is still fully encrypted and secure.\n\n' +
           'In the meantime, feel free to browse the app — everything else is working normally!';
  }
  if (lower.includes('timeout') || lower.includes('timed out')) {
    return '⏱️ That took a little longer than expected. Could you try again? Everything is still running fine on our end.';
  }
  if (lower.includes('connection') || lower.includes('network')) {
    return 'Looks like the connection was briefly interrupted. Please try again — the service is still up and running.';
  }
  return `Something unexpected happened, but don't worry — your data is safe and secure. Please try again in a moment.`;
}

// ── Support FAB Component ─────────────────────────────────
export default function SupportFAB({ activeApp, themeColor = '#818cf8' }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const prevAppRef = useRef(activeApp);

  const [audienceDetected, setAudienceDetected] = useState(null);
  const [generatingProfile, setGeneratingProfile] = useState(false);
  const audienceTimerRef = useRef(null);

  const checkAudienceIntent = async (text) => {
    try {
      const res = await fetch(`${API_BASE}/api/audience/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (data.detected && data.confidence >= 0.7) {
        setAudienceDetected(data);
        if (audienceTimerRef.current) clearTimeout(audienceTimerRef.current);
        audienceTimerRef.current = setTimeout(() => setAudienceDetected(null), 15000);
      }
    } catch { /* silent */ }
  };

  const researchProfile = async () => {
    if (!audienceDetected?.audience_hint || generatingProfile) return;
    setGeneratingProfile(true);
    setAudienceDetected(null);
    setMessages(prev => [...prev, { role: 'system', text: `🔬 Researching audience profile: "${audienceDetected.audience_hint}"...` }]);
    try {
      const res = await fetch(`${API_BASE}/api/audience/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audience_description: audienceDetected.audience_hint,
          context: `Context: Active App ${activeApp}`
        }),
      });
      const data = await res.json();
      if (data.status === 'ok' && data.profile) {
        const p = data.profile;
        const profileCard =
          `✅ **Audience Profile Generated: ${p.name}**\n` +
          `📊 Age Range: ${p.age_range}\n` +
          `💰 Income: ${p.income_bracket}\n\n` +
          `**Pain Points:**\n` + p.pain_points.map(pt => `• ${pt}`).join('\n') + `\n\n` +
          `**Values & Goals:**\n` + p.values.map(v => `• ${v}`).join('\n') + `\n\n` +
          `*This context is now active for my recommendations.*`;
        
        setMessages(prev => [...prev, { role: 'assistant', text: profileCard }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', text: `❌ Could not generate profile: ${e.message}` }]);
    } finally {
      setGeneratingProfile(false);
    }
  };


  // ── Context Isolation: clear on app change ────────────
  useEffect(() => {
    if (prevAppRef.current !== activeApp) {
      setMessages([]);
      setInput('');
      setStreaming(false);
      prevAppRef.current = activeApp;
    }
  }, [activeApp]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when drawer opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  const appConfig = APP_KNOWLEDGE[activeApp] || APP_KNOWLEDGE._default;

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || streaming) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);

    // Fire-and-forget audience check
    checkAudienceIntent(text);

    // ── SYSTEM GUARD INTERCEPT ────────────────────────────
    const guardResponse = systemGuardCheck(text, appConfig);
    if (guardResponse) {
      // Block the API call — respond locally with disclaimer
      setMessages(prev => [...prev, { role: 'assistant', text: guardResponse }]);
      return;
    }

    // ── Safe to proceed to API ────────────────────────────
    setStreaming(true);
    setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          dashboard_context: {
            mode: 'support',
            active_app: activeApp || 'Factory',
            system_prompt: buildSystemPrompt(activeApp),
          },
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: 'assistant', text: friendlyError(err.error || `HTTP ${res.status}`) };
          return copy;
        });
        setStreaming(false);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.error) {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { role: 'assistant', text: friendlyError(event.error) };
                return copy;
              });
              break;
            }
            if (event.done) break;
            if (event.text) {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = {
                  role: 'assistant',
                  text: scrubResponse(copy[copy.length - 1].text + event.text),
                };
                return copy;
              });
            }
          } catch { /* skip */ }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', text: friendlyError(err.message) };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <>
      {/* ── Chat Drawer ── */}
      {isOpen && (
        <div className="support-drawer" style={{ '--fab-color': themeColor }}>
          <div className="support-drawer-header">
            <div className="support-drawer-title">
              <span className="support-drawer-dot" style={{ background: themeColor }} />
              <span>{appConfig.displayName || 'Support'}</span>
            </div>
            <button className="support-drawer-close" onClick={() => setIsOpen(false)}>✕</button>
          </div>

          <div className="support-drawer-messages">
            {messages.length === 0 && (
              <div className="support-welcome">
                <div className="support-welcome-icon">💬</div>
                <p className="support-welcome-text">{appConfig.greeting}</p>
                <div className="support-topics">
                  {appConfig.topics.slice(0, 3).map((t, i) => (
                    <button
                      key={i}
                      className="support-topic-chip"
                      onClick={() => { setInput(t); inputRef.current?.focus(); }}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <div className="support-trust-badge">
                  <span>🔒</span>
                  <span>Encrypted & Secure · Private · Your Data Only</span>
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`support-msg ${msg.role}`}>
                {msg.text}
                {msg.role === 'assistant' && streaming && i === messages.length - 1 && (
                  <span className="support-cursor" />
                )}
              </div>
            ))}
            <div ref={scrollRef} />
          </div>


          {audienceDetected && (
            <div className="audience-detect-chip" style={{ margin: '0 0.8rem 0.8rem 0.8rem', padding: '0.6rem 0.8rem', background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.35)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px', zIndex: 10 }}>
              <span className="detect-icon" style={{fontSize:'1.1rem'}}>👥</span>
              <div className="detect-text" style={{flex:1, fontSize:'0.75rem', color: '#cbd5e1'}}>
                Audience detected: <strong style={{color: '#a78bfa'}}>{audienceDetected.audience_hint}</strong>
              </div>
              <button 
                onClick={researchProfile}
                disabled={generatingProfile}
                style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)', color: 'white', border: 'none', padding: '0.3rem 0.6rem', borderRadius: '6px', fontSize: '0.7rem', cursor: generatingProfile ? 'not-allowed' : 'pointer', opacity: generatingProfile ? 0.7 : 1 }}
              >
                {generatingProfile ? '...' : 'Research'}
              </button>
            </div>
          )}
          <div className="support-drawer-input">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') sendMessage(); }}
              placeholder={streaming ? 'Thinking...' : 'Ask a question...'}
              disabled={streaming}
            />
            <button
              className="support-send-btn"
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              style={{ background: themeColor }}
            >
              ↑
            </button>
          </div>
        </div>
      )}

      {/* ── FAB Button ── */}
      <button
        className={`support-fab ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        style={{ '--fab-color': themeColor }}
        title={`${appConfig.displayName || 'Support'}`}
      >
        <span className="support-fab-ring" />
        <span className="support-fab-icon">{isOpen ? '✕' : '💬'}</span>
      </button>
    </>
  );
}
