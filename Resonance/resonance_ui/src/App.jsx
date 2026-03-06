import { useState, useEffect, useRef, useCallback } from 'react';
import { marked } from 'marked'; // For markdown rendering
import DOMPurify from 'dompurify'; // For sanitizing HTML

const API = 'http://localhost:5006';

const CHANNELS = [
  { id: 'general', name: 'general', icon: '💬', description: 'General chat for all things Resonance.' },
  { id: 'wingman-mode', name: 'wingman-mode', icon: '🤝', description: 'Social simulation and role-play scenarios.' },
  { id: 'focus-room', name: 'focus-room', icon: '🧠', description: 'Structured learning and deep dives.' },
  { id: 'mixing-board', name: 'mixing-board', icon: '🎛️', description: 'Language construction and creative writing.' },
];

// Utility to format timestamps
const formatTimestamp = (date) => {
  const now = new Date();
  const msgDate = new Date(date);
  const diffTime = Math.abs(now - msgDate);
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays <= 1) return msgDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffDays <= 7) return msgDate.toLocaleDateString([], { weekday: 'short' }) + ' ' + msgDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return msgDate.toLocaleDateString();
};

// Message Component
function Message({ message, showAvatarAndName }) {
  const { role, text, timestamp } = message;
  const name = role === 'user' ? 'You' : 'Alex';
  const userAvatarBg = '#4CAF50'; // Green for user
  const alexAvatarSrc = "/alex_avatar.png"; // Asset path for Alex's avatar

  const renderMarkdown = useCallback((markdownText) => {
    return { __html: DOMPurify.sanitize(marked.parse(markdownText || '')) };
  }, []);

  if (role === 'system') { // New condition for system messages
    return (
      <div className="message-item system">
        <div className="message-content system-message">
          <p><i>{text}</i></p>
        </div>
      </div>
    );
  }

  return (
    <div className={`message-item group ${role === 'user' ? 'self-end' : 'self-start'}`}>
      {showAvatarAndName && (
        <div className="message-header">
          <div className="avatar-container">
            {role === 'user' ? (
              <div className="avatar user-avatar" style={{ background: userAvatarBg }}>Y</div>
            ) : (
              <img src={alexAvatarSrc} alt="Alex's avatar" className="avatar alex-avatar" width="32" height="32" />
            )}
            {role === 'assistant' && <div className="online-status-dot"></div>}
          </div>
          <span className="username">{name}</span>
          <span className="timestamp">{formatTimestamp(timestamp)}</span>
        </div>
      )}
      <div className="message-content" dangerouslySetInnerHTML={renderMarkdown(text)}></div>
    </div>
  );
}

// Typing Indicator Component
function TypingIndicator() {
  const alexAvatarSrc = "/alex_avatar.png"; // Asset path for Alex's avatar
  return (
    <div className="typing-indicator">
      <div className="avatar-container">
        <img src={alexAvatarSrc} alt="Alex's avatar" className="avatar alex-avatar" width="32" height="32" />
        <div className="online-status-dot"></div>
      </div>
      <div className="typing-bubble">
        <div className="dot"></div>
        <div className="dot"></div>
        <div className="dot"></div>
      </div>
      <span className="typing-text">Alex is typing</span>
    </div>
  );
}

// PinGate Component
function PinGate({ onUnlock, onCancel, pinInput, setPinInput, pinError, isUnlocking }) {
  const pinInputRef = useRef(null);

  useEffect(() => {
    if (pinInputRef.current) {
      pinInputRef.current.focus();
    }
  }, []);

  const handlePinChange = (e) => {
    const value = e.target.value;
    if (/^\d*$/.test(value) && value.length <= 4) {
      setPinInput(value);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && pinInput.length === 4) {
      onUnlock();
    }
  };

  return (
    <div className="pin-gate-overlay">
      <div className={`pin-gate-card ${pinError ? 'shake-animation' : ''}`}>
        <h3>Parent Portal Access</h3>
        <p>Enter your 4-digit PIN to unlock.</p>
        <input
          ref={pinInputRef}
          type="password"
          maxLength="4"
          value={pinInput}
          onChange={handlePinChange}
          onKeyDown={handleKeyDown}
          className="pin-input"
          disabled={isUnlocking}
          aria-label="PIN input"
        />
        {pinError && <p className="pin-error-message">{pinError}</p>}
        <div className="pin-button-group">
          <button onClick={onUnlock} disabled={pinInput.length !== 4 || isUnlocking} className="pin-button unlock">
            {isUnlocking ? 'Unlocking...' : 'Unlock'}
          </button>
          <button onClick={onCancel} disabled={isUnlocking} className="pin-button cancel">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ParentPanel Component
function ParentPanel({ onLockAndReturn, parentConfig, saveParentConfig, parentProgress, fetchParentProgress }) {
  const [activeTab, setActiveTab] = useState('instructions');
  const [instructionsInput, setInstructionsInput] = useState(parentConfig.instructions || '');
  const [newTopicInput, setNewTopicInput] = useState('');
  const [newVocabWord, setNewVocabWord] = useState('');
  const [newVocabDefinition, setNewVocabDefinition] = useState('');
  const [newVocabExample, setNewVocabExample] = useState('');
  const [saveFeedback, setSaveFeedback] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setInstructionsInput(parentConfig.instructions || '');
  }, [parentConfig.instructions]);

  useEffect(() => {
    if (activeTab === 'progress') {
      fetchParentProgress();
    }
  }, [activeTab, fetchParentProgress]);

  const handleSave = async (field, value) => {
    setIsSaving(true);
    setSaveFeedback('');
    try {
      const updatedConfig = { ...parentConfig, [field]: value };
      await saveParentConfig(updatedConfig);
      setSaveFeedback('Saved successfully!');
    } catch (e) {
      setSaveFeedback(`Error saving: ${e.message}`);
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveFeedback(''), 3000);
    }
  };

  const addTopic = () => {
    if (newTopicInput.trim() && !parentConfig.focus_topics.includes(newTopicInput.trim())) {
      const updatedTopics = [...parentConfig.focus_topics, newTopicInput.trim()];
      handleSave('focus_topics', updatedTopics);
      setNewTopicInput('');
    }
  };

  const removeTopic = (topicToRemove) => {
    const updatedTopics = parentConfig.focus_topics.filter(topic => topic !== topicToRemove);
    handleSave('focus_topics', updatedTopics);
  };

  const addVocabulary = () => {
    if (newVocabWord.trim() && newVocabDefinition.trim()) {
      const newVocabEntry = {
        word: newVocabWord.trim(),
        definition: newVocabDefinition.trim(),
        example: newVocabExample.trim(),
      };
      const updatedVocabulary = [...parentConfig.vocabulary, newVocabEntry];
      handleSave('vocabulary', updatedVocabulary);
      setNewVocabWord('');
      setNewVocabDefinition('');
      setNewVocabExample('');
    }
  };

  const deleteVocabulary = (indexToDelete) => {
    const updatedVocabulary = parentConfig.vocabulary.filter((_, index) => index !== indexToDelete);
    handleSave('vocabulary', updatedVocabulary);
  };

  // Progress Tab Calculations
  const totalSessions = parentProgress.length;
  const totalWords = parentProgress.reduce((sum, entry) => sum + entry.user_words + entry.alex_words, 0);
  const averageSessionLength = totalSessions > 0 ? (totalWords / totalSessions).toFixed(0) : 0;

  const channelCounts = parentProgress.reduce((acc, entry) => {
    acc[entry.channel] = (acc[entry.channel] || 0) + 1;
    return acc;
  }, {});
  const mostUsedChannel = Object.keys(channelCounts).reduce((a, b) => channelCounts[a] > channelCounts[b] ? a : b, 'N/A');

  return (
    <div className="parent-panel">
      <header className="parent-header">
        <h2>Parent Portal</h2>
        <button onClick={onLockAndReturn} className="lock-return-button">
          🔒 Lock & Return
        </button>
      </header>

      <nav className="parent-tab-nav">
        <button className={`parent-tab-button ${activeTab === 'instructions' ? 'active' : ''}`} onClick={() => setActiveTab('instructions')}>Instructions</button>
        <button className={`parent-tab-button ${activeTab === 'focus_topics' ? 'active' : ''}`} onClick={() => setActiveTab('focus_topics')}>Focus Topics</button>
        <button className={`parent-tab-button ${activeTab === 'vocabulary' ? 'active' : ''}`} onClick={() => setActiveTab('vocabulary')}>Vocabulary</button>
        <button className={`parent-tab-button ${activeTab === 'progress' ? 'active' : ''}`} onClick={() => setActiveTab('progress')}>Progress</button>
      </nav>

      <div className="parent-tab-content">
        {activeTab === 'instructions' && (
          <div>
            <h3>General Instructions for Alex</h3>
            <textarea
              className="instructions-textarea"
              value={instructionsInput}
              onChange={(e) => setInstructionsInput(e.target.value)}
              placeholder="Provide general instructions for Alex's interaction style, goals, etc."
              disabled={isSaving}
            ></textarea>
            <button onClick={() => handleSave('instructions', instructionsInput)} disabled={isSaving} className="save-button">
              {isSaving ? 'Saving...' : 'Save Instructions'}
            </button>
            {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
          </div>
        )}

        {activeTab === 'focus_topics' && (
          <div>
            <h3>Priority Focus Topics</h3>
            <p className="text-muted">These topics will be emphasized during learning sessions.</p>
            <div className="topic-tags-container">
              {parentConfig.focus_topics.map((topic, index) => (
                <div key={index} className="topic-tag">
                  <span>{topic}</span>
                  <button onClick={() => removeTopic(topic)} className="remove-tag-button" disabled={isSaving}>
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <div className="add-topic-form">
              <input
                type="text"
                className="add-topic-input"
                value={newTopicInput}
                onChange={(e) => setNewTopicInput(e.target.value)}
                placeholder="Add a new focus topic"
                disabled={isSaving}
              />
              <button onClick={addTopic} disabled={!newTopicInput.trim() || isSaving} className="save-button">
                Add Topic
              </button>
            </div>
            {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
          </div>
        )}

        {activeTab === 'vocabulary' && (
          <div>
            <h3>Additional Vocabulary to Practice</h3>
            <p className="text-muted">Alex will actively try to incorporate these words into conversations.</p>
            <div className="vocab-list">
              {parentConfig.vocabulary.map((vocab, index) => (
                <div key={index} className="vocab-card">
                  <div className="vocab-card-header">
                    <h4>{vocab.word}</h4>
                    <button onClick={() => deleteVocabulary(index)} className="delete-vocab-button" disabled={isSaving}>
                      🗑️
                    </button>
                  </div>
                  <p><strong>Definition:</strong> {vocab.definition}</p>
                  {vocab.example && <p><strong>Example:</strong> {vocab.example}</p>}
                </div>
              ))}
            </div>
            <div className="add-vocab-form">
              <h4>Add New Vocabulary</h4>
              <input
                type="text"
                value={newVocabWord}
                onChange={(e) => setNewVocabWord(e.target.value)}
                placeholder="Word"
                disabled={isSaving}
              />
              <input
                type="text"
                value={newVocabDefinition}
                onChange={(e) => setNewVocabDefinition(e.target.value)}
                placeholder="Definition"
                disabled={isSaving}
              />
              <input
                type="text"
                value={newVocabExample}
                onChange={(e) => setNewVocabExample(e.target.value)}
                placeholder="Example (optional)"
                disabled={isSaving}
              />
              <button onClick={addVocabulary} disabled={!newVocabWord.trim() || !newVocabDefinition.trim() || isSaving} className="add-vocab-button">
                Add Word
              </button>
            </div>
            {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
          </div>
        )}

        {activeTab === 'progress' && (
          <div>
            <h3>Learning Progress Overview</h3>
            <div className="progress-stats-grid">
              <div className="stat-card">
                <h4>Total Sessions</h4>
                <p>{totalSessions}</p>
              </div>
              <div className="stat-card">
                <h4>Avg. Session Length</h4>
                <p>{averageSessionLength} words</p>
              </div>
              <div className="stat-card">
                <h4>Most Used Channel</h4>
                <p>#{mostUsedChannel}</p>
              </div>
            </div>

            <h4>Last 10 Sessions</h4>
            {parentProgress.length === 0 ? (
              <p className="text-muted">No session data available yet.</p>
            ) : (
              <table className="progress-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Channel</th>
                    <th>User Words</th>
                    <th>Alex Words</th>
                    <th>Duration Est.</th>
                  </tr>
                </thead>
                <tbody>
                  {parentProgress.slice(-10).reverse().map((entry, index) => (
                    <tr key={index}>
                      <td>{new Date(entry.timestamp).toLocaleString()}</td>
                      <td>#{entry.channel}</td>
                      <td>{entry.user_words}</td>
                      <td>{entry.alex_words}</td>
                      <td>{entry.session_duration_estimate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


// Main App Component
export default function App() {
  const [activeChannel, setActiveChannel] = useState(CHANNELS[0].id);
  const [chatHistory, setChatHistory] = useState({}); // { channelId: [{ role, text, timestamp }] }
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [typing, setTyping] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]); // [{ filename, type, uploaded_at, text_length }]
  const [showFilesPanel, setShowFilesPanel] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Parent Portal States
  const [parentMode, setParentMode] = useState(false);
  const [showPinGate, setShowPinGate] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState('');
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [parentConfig, setParentConfig] = useState({ instructions: '', focus_topics: [], vocabulary: [] });
  const [parentProgress, setParentProgress] = useState([]);


  const endRef = useRef(null);
  const fileInputRef = useRef(null); // Ref for the hidden file input

  const currentChannel = CHANNELS.find(c => c.id === activeChannel);
  const messages = chatHistory[activeChannel] || [];
  const alexAvatarSrc = "/alex_avatar.png"; // Asset path for Alex's avatar

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing, parentMode]); // Scroll when parentMode changes too

  // Fetch uploaded files on component mount and whenever the panel might need refreshing
  useEffect(() => {
    fetchUploadedFiles();
  }, []);

  const fetchUploadedFiles = async () => {
    try {
      const res = await fetch(`${API}/api/uploads`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setUploadedFiles(data.files || []);
    } catch (e) {
      console.error("Failed to fetch uploaded files:", e);
    }
  };

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      const systemMessage = { role: 'system', text: `📎 File uploaded: ${data.filename}`, timestamp: new Date().toISOString() };
      setChatHistory(prev => ({
        ...prev,
        [activeChannel]: [...(prev[activeChannel] || []), systemMessage]
      }));
      fetchUploadedFiles(); // Refresh the list of uploaded files
    } catch (e) {
      console.error("File upload failed:", e);
      const errorMessage = { role: 'system', text: `❌ File upload failed: ${e.message}`, timestamp: new Date().toISOString() };
      setChatHistory(prev => ({
        ...prev,
        [activeChannel]: [...(prev[activeChannel] || []), errorMessage]
      }));
    } finally {
      setUploading(false);
      event.target.value = null; // Clear the input so same file can be uploaded again
    }
  };

  const deleteFile = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      const res = await fetch(`${API}/api/uploads/${filename}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
      }
      const systemMessage = { role: 'system', text: `🗑️ File deleted: ${filename}`, timestamp: new Date().toISOString() };
      setChatHistory(prev => ({
        ...prev,
        [activeChannel]: [...(prev[activeChannel] || []), systemMessage]
      }));
      fetchUploadedFiles(); // Refresh the list
    } catch (e) {
      console.error("Failed to delete file:", e);
      const errorMessage = { role: 'system', text: `❌ Failed to delete file: ${e.message}`, timestamp: new Date().toISOString() };
      setChatHistory(prev => ({
        ...prev,
        [activeChannel]: [...(prev[activeChannel] || []), errorMessage]
      }));
    }
  };


  const send = async () => {
    const p = input.trim();
    if (!p || streaming || uploading) return; // Disable send if uploading

    setStreaming(true); // Set streaming state to true BEFORE initiating fetch
    setInput('');
    setTyping(true);

    const userMessage = { role: 'user', text: p, timestamp: new Date().toISOString() };
    setChatHistory(prev => ({
      ...prev,
      [activeChannel]: [...(prev[activeChannel] || []), userMessage]
    }));

    const assistantPlaceholder = { role: 'assistant', text: '', timestamp: new Date().toISOString() };
    setChatHistory(prev => ({
      ...prev,
      [activeChannel]: [...(prev[activeChannel] || []), assistantPlaceholder]
    }));

    try {
      // Prepend channel info to the prompt
      const fullPrompt = `[Channel: #${activeChannel}] ${p}`;
      const res = await fetch(`${API}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: fullPrompt, dashboard_context: { channel: activeChannel } }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // Final cleanup pass for emoji rendering after streaming completes
          setChatHistory(prev => {
            const currentChannelHistory = [...(prev[activeChannel] || [])];
            const lastMessageIndex = currentChannelHistory.length - 1;
            if (lastMessageIndex >= 0 && currentChannelHistory[lastMessageIndex].role === 'assistant') {
              const rawText = currentChannelHistory[lastMessageIndex].text;
              // Re-encode and re-decode to fix potential UTF-8 fragmentation issues
              const fixedText = new TextDecoder('utf-8').decode(new TextEncoder().encode(rawText));
              currentChannelHistory[lastMessageIndex].text = fixedText;
            }
            return { ...prev, [activeChannel]: currentChannelHistory };
          });

          setTyping(false);
          setStreaming(false);
          break; // Break cleanly on event.done
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.error) { // Break cleanly on event.error
              console.error("SSE Error:", event.error);
              setChatHistory(prev => {
                const currentChannelHistory = [...(prev[activeChannel] || [])];
                const lastMessageIndex = currentChannelHistory.length - 1;
                if (lastMessageIndex >= 0 && currentChannelHistory[lastMessageIndex].role === 'assistant') {
                  currentChannelHistory[lastMessageIndex].text = `❌ Error: ${event.error}`;
                } else {
                  currentChannelHistory.push({ role: 'assistant', text: `❌ Error: ${event.error}`, timestamp: new Date().toISOString() });
                }
                return { ...prev, [activeChannel]: currentChannelHistory };
              });
              setTyping(false);
              setStreaming(false);
              return; // Exit function on error
            }
            if (event.done) {
              // This 'done' inside the loop is usually redundant if the outer 'done' handles the final state.
              // However, if the server sends a 'done' event mid-stream, we should handle it.
              // The outer 'done' will still perform the final cleanup.
              setTyping(false);
              setStreaming(false);
              break; // Break from inner loop if done signal received
            }
            if (event.text) {
              setChatHistory(prev => {
                const currentChannelHistory = [...(prev[activeChannel] || [])];
                const lastMessageIndex = currentChannelHistory.length - 1;
                if (lastMessageIndex >= 0 && currentChannelHistory[lastMessageIndex].role === 'assistant') {
                  currentChannelHistory[lastMessageIndex].text += event.text;
                } else {
                  // Fallback if somehow the placeholder wasn't added
                  currentChannelHistory.push({ role: 'assistant', text: event.text, timestamp: new Date().toISOString() });
                }
                return { ...prev, [activeChannel]: currentChannelHistory };
              });
            }
          } catch (parseError) {
            console.error("Error parsing SSE event:", parseError);
          }
        }
      }
    } catch (e) {
      console.error("Stream fetch error:", e);
      setChatHistory(prev => {
        const currentChannelHistory = [...(prev[activeChannel] || [])];
        const lastMessageIndex = currentChannelHistory.length - 1;
        if (lastMessageIndex >= 0 && currentChannelHistory[lastMessageIndex].role === 'assistant') {
          currentChannelHistory[lastMessageIndex].text = `❌ Error: ${e.message}`;
        } else {
          currentChannelHistory.push({ role: 'assistant', text: `❌ Error: ${e.message}`, timestamp: new Date().toISOString() });
        }
        return { ...prev, [activeChannel]: currentChannelHistory };
      });
    } finally {
      setTyping(false);
      setStreaming(false);
    }
  };

  const clearChatHistory = async () => {
    try {
      await fetch(`${API}/api/chat/clear`, { method: 'POST' });
      setChatHistory(prev => ({ ...prev, [activeChannel]: [] }));
    } catch (e) {
      console.error("Failed to clear chat history:", e);
    }
  };

  const getWelcomeMessage = (channelId) => {
    const channel = CHANNELS.find(c => c.id === channelId);
    if (!channel) return "Welcome to Resonance!";
    return `Welcome to #${channel.name}! ${channel.description}`;
  };

  // Parent Portal Functions
  const fetchParentConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/parent/config`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setParentConfig(data);
    } catch (e) {
      console.error("Failed to fetch parent config:", e);
    }
  }, []);

  const saveParentConfig = useCallback(async (updatedConfig) => {
    try {
      const res = await fetch(`${API}/api/parent/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedConfig),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
      }
      fetchParentConfig(); // Refresh config after saving
    } catch (e) {
      console.error("Failed to save parent config:", e);
      throw e; // Re-throw to be caught by component
    }
  }, [fetchParentConfig]);

  const fetchParentProgress = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/parent/progress`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setParentProgress(data);
    } catch (e) {
      console.error("Failed to fetch parent progress:", e);
    }
  }, []);

  const handleUnlockParentPortal = async () => {
    if (pinInput.length !== 4) {
      setPinError('PIN must be 4 digits.');
      return;
    }
    setIsUnlocking(true);
    setPinError('');
    try {
      const res = await fetch(`${API}/api/parent/verify-pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pinInput }),
      });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      if (data.valid) {
        setParentMode(true);
        setShowPinGate(false);
        setPinInput('');
        fetchParentConfig(); // Load config when entering parent mode
      } else {
        setPinError('Invalid PIN. Please try again.');
      }
    } catch (e) {
      console.error("PIN verification failed:", e);
      setPinError(`Verification error: ${e.message}`);
    } finally {
      setIsUnlocking(false);
    }
  };

  const handleCancelPinGate = () => {
    setShowPinGate(false);
    setPinInput('');
    setPinError('');
  };

  const handleLockAndReturn = () => {
    setParentMode(false);
    setParentProgress([]); // Clear progress data when exiting
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="server-header">
          <span className="server-icon">🎧</span> Resonance
        </div>
        <nav className="channel-list">
          {CHANNELS.map(channel => (
            <div
              key={channel.id}
              className={`channel-item ${activeChannel === channel.id && !parentMode ? 'active' : ''}`}
              onClick={() => {
                setActiveChannel(channel.id);
                setParentMode(false); // Exit parent mode if channel is clicked
              }}
            >
              <span className="channel-icon">{channel.icon}</span>
              <span className="channel-name">#{channel.name}</span>
            </div>
          ))}
        </nav>

        {/* Parent Portal Button */}
        <div
          className={`parent-portal-button ${parentMode ? 'active' : ''}`}
          onClick={() => {
            if (!parentMode) {
              setShowPinGate(true);
            } else {
              handleLockAndReturn(); // If already in parent mode, lock and return
            }
          }}
        >
          <span className="channel-icon">🔒</span>
          <span className="channel-name">Parent Portal</span>
        </div>

        <div className="user-panel">
          <div className="avatar-container">
            <div className="avatar user-avatar" style={{ background: '#4CAF50' }}>Y</div>
            <div className="online-status-dot"></div>
          </div>
          <span className="username">You</span>
        </div>
      </div>

      {/* Main Content Area: Chat or Parent Panel */}
      {parentMode ? (
        <ParentPanel
          onLockAndReturn={handleLockAndReturn}
          parentConfig={parentConfig}
          saveParentConfig={saveParentConfig}
          parentProgress={parentProgress}
          fetchParentProgress={fetchParentProgress}
        />
      ) : (
        <div className="chat-area">
          <header className="chat-header">
            <div className="channel-info">
              <span className="channel-icon">{currentChannel.icon}</span>
              <h2 className="channel-name">#{currentChannel.name}</h2>
              <span className="channel-description">{currentChannel.description}</span>
              {uploadedFiles.length > 0 && (
                <button className="files-badge" onClick={() => setShowFilesPanel(!showFilesPanel)}>
                  📎 Files ({uploadedFiles.length})
                </button>
              )}
            </div>
            <button className="clear-chat-button" onClick={clearChatHistory}>Clear Chat</button>
          </header>

          {showFilesPanel && (
            <div className="files-panel">
              <h3>Uploaded Files</h3>
              {uploadedFiles.length === 0 ? (
                <p>No files uploaded yet.</p>
              ) : (
                <ul>
                  {uploadedFiles.map(file => (
                    <li key={file.filename} className="file-list-item">
                      <span>{file.filename} ({file.type}, {file.text_length} chars)</span>
                      <button onClick={() => deleteFile(file.filename)} className="delete-file-button">
                        🗑️
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="message-list-container">
            {messages.length === 0 && (
              <div className="welcome-banner">
                <div className="welcome-avatar-glow">
                  <img src={alexAvatarSrc} alt="Alex's avatar" className="welcome-avatar alex-avatar" width="80" height="80" />
                </div>
                <h1>Welcome to #{currentChannel.name}!</h1>
                <p>{getWelcomeMessage(activeChannel)}</p>
              </div>
            )}

            {messages.map((m, i) => {
              const prevMessage = messages[i - 1];
              const showAvatarAndName = !prevMessage || prevMessage.role !== m.role || (new Date(m.timestamp) - new Date(prevMessage.timestamp)) > 5 * 60 * 1000; // Group messages by role and within 5 minutes
              return <Message key={i} message={m} showAvatarAndName={showAvatarAndName} />;
            })}
            {typing && <TypingIndicator />}
            <div ref={endRef} />
          </div>

          <div className="chat-input-area">
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".txt,.pdf,.docx,.csv,.md,.png,.jpg,.jpeg"
              onChange={handleFileChange}
            />
            <button
              className="upload-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || streaming}
              aria-label="Upload file"
            >
              {uploading ? '...' : '📎'}
            </button>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder={`Message #${currentChannel.name}`}
              disabled={streaming || uploading}
              className="chat-input"
              aria-label={`Message #${currentChannel.name}`}
            />
            <button onClick={send} disabled={streaming || uploading || !input.trim()} className="send-button">
              ↑
            </button>
          </div>
        </div>
      )}

      {showPinGate && (
        <PinGate
          onUnlock={handleUnlockParentPortal}
          onCancel={handleCancelPinGate}
          pinInput={pinInput}
          setPinInput={setPinInput}
          pinError={pinError}
          isUnlocking={isUnlocking}
        />
      )}
    </div>
  );
}