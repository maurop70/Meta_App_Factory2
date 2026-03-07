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

// ── Guided Interview Constants ──────────────────────────
const HOBBY_PRESETS = ['Art', 'Sports', 'Gaming', 'Music', 'Technology', 'Nature', 'Social Media', 'Reading', 'Cooking'];
const SOCIAL_LEVELS = [
  { value: '', label: 'Not set' },
  { value: 'isolated', label: 'Prefers solo activities' },
  { value: 'small_group', label: 'Comfortable in small groups (2-3)' },
  { value: 'social', label: 'Enjoys group activities' },
  { value: 'leader', label: 'Takes initiative in groups' },
];
const STRESS_OPTIONS = ['Academic Pressure', 'Social Anxiety', 'Test Anxiety', 'Homework Overload', 'Time Management', 'Peer Conflicts'];
const LEARNING_STYLES = ['Visual', 'Auditory', 'Kinesthetic', 'Reading/Writing'];
const SEVERITY_OPTIONS = ['low', 'medium', 'high'];
const TIMEOUT_OPTIONS = [
  { value: 0, label: 'Never' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '60 minutes' },
];

// Section Upload Component — contextual document upload per profile section
function SectionUpload({ sectionTag, onUploadComplete }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);

  // Fetch count on mount
  useEffect(() => {
    fetch(`${API}/api/uploads/by-section/${sectionTag}`)
      .then(r => r.json())
      .then(data => setUploadCount((data.files || []).length))
      .catch(() => { });
  }, [sectionTag]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API}/api/upload?section_tag=${sectionTag}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setUploadCount(prev => prev + 1);
      if (onUploadComplete) onUploadComplete();
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <span className="section-upload">
      <button className="section-upload-button" onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        title="Upload vocabulary lists, teacher feedback, or interest-based articles to customize the Council's focus."
      >
        {uploading ? '⏳' : '📎'}
        {uploadCount > 0 && <span className="upload-count-badge">{uploadCount}</span>}
      </button>
      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt,.csv,.md"
        style={{ display: 'none' }} onChange={handleUpload} />
    </span>
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

  // Student Profile state
  const profile = parentConfig.student_profile || {};
  const [selectedHobbies, setSelectedHobbies] = useState(profile.hobbies_interests || []);
  const [customHobby, setCustomHobby] = useState('');
  const [socialLevel, setSocialLevel] = useState(profile.social_level || '');
  const [academicAreas, setAcademicAreas] = useState(profile.academic_weak_areas || []);
  const [newSubject, setNewSubject] = useState('');
  const [newSpecificArea, setNewSpecificArea] = useState('');
  const [newSeverity, setNewSeverity] = useState('medium');
  const [selectedStressors, setSelectedStressors] = useState(profile.stress_indicators || []);
  const [selectedLearningStyles, setSelectedLearningStyles] = useState(profile.learning_style_preferences || []);

  // Council state
  const [councilStatus, setCouncilStatus] = useState(null);
  const [councilLoading, setCouncilLoading] = useState(false);
  const [showPromptPreview, setShowPromptPreview] = useState(false);

  // Settings state
  const settings = parentConfig.settings || { council_intensity: 'supportive', session_timeout_minutes: 30 };
  const [intensity, setIntensity] = useState(settings.council_intensity || 'supportive');
  const [sessionTimeout, setSessionTimeout] = useState(settings.session_timeout_minutes ?? 30);
  const [currentPin, setCurrentPin] = useState('');
  const [newPin, setNewPin] = useState('');
  const [pinFeedback, setPinFeedback] = useState('');
  const [allUploads, setAllUploads] = useState([]);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetPin, setResetPin] = useState('');
  const [resetFeedback, setResetFeedback] = useState('');
  const [betaFeedback, setBetaFeedback] = useState('');

  // Reports state
  const reportIntel = parentConfig.report_intelligence || { enabled: true, reports: [] };
  const [reportUploading, setReportUploading] = useState(null); // category being uploaded
  const [reportFeedback, setReportFeedback] = useState('');
  const [digestData, setDigestData] = useState(null);
  const [showDigest, setShowDigest] = useState(false);
  const [intelligenceEnabled, setIntelligenceEnabled] = useState(reportIntel.enabled !== false);

  useEffect(() => {
    setInstructionsInput(parentConfig.instructions || '');
  }, [parentConfig.instructions]);

  useEffect(() => {
    const p = parentConfig.student_profile || {};
    setSelectedHobbies(p.hobbies_interests || []);
    setSocialLevel(p.social_level || '');
    setAcademicAreas(p.academic_weak_areas || []);
    setSelectedStressors(p.stress_indicators || []);
    setSelectedLearningStyles(p.learning_style_preferences || []);
  }, [parentConfig.student_profile]);

  useEffect(() => {
    if (activeTab === 'progress') fetchParentProgress();
    if (activeTab === 'council') fetchCouncilPreview();
    if (activeTab === 'settings') { fetchAllUploads(); fetchDigest(); }
    if (activeTab === 'reports') fetchDigest();
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

  // ── Student Profile Handlers ──────────────────────────
  const toggleChip = (item, list, setter) => {
    setter(prev => prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]);
  };

  const addCustomHobby = () => {
    if (customHobby.trim() && !selectedHobbies.includes(customHobby.trim())) {
      setSelectedHobbies(prev => [...prev, customHobby.trim()]);
      setCustomHobby('');
    }
  };

  const addAcademicArea = () => {
    if (newSubject.trim() && newSpecificArea.trim()) {
      setAcademicAreas(prev => [...prev, { subject: newSubject.trim(), specific_area: newSpecificArea.trim(), severity: newSeverity }]);
      setNewSubject('');
      setNewSpecificArea('');
      setNewSeverity('medium');
    }
  };

  const removeAcademicArea = (index) => {
    setAcademicAreas(prev => prev.filter((_, i) => i !== index));
  };

  const saveStudentProfile = async () => {
    setIsSaving(true);
    setSaveFeedback('');
    try {
      const res = await fetch(`${API}/api/parent/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hobbies_interests: selectedHobbies,
          social_level: socialLevel,
          academic_weak_areas: academicAreas,
          stress_indicators: selectedStressors,
          learning_style_preferences: selectedLearningStyles,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setSaveFeedback('Student profile saved! Council will update.');
      // Refresh parent config to reflect new profile
      const configRes = await fetch(`${API}/api/parent/config`);
      if (configRes.ok) {
        const data = await configRes.json();
        // Update parent config in parent component state via saveParentConfig
      }
    } catch (e) {
      setSaveFeedback(`Error: ${e.message}`);
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveFeedback(''), 3000);
    }
  };

  // ── Council Handlers ──────────────────────────────────
  const fetchCouncilPreview = async () => {
    setCouncilLoading(true);
    try {
      const res = await fetch(`${API}/api/parent/council-preview`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCouncilStatus(data);
    } catch (e) {
      console.error('Failed to fetch council preview:', e);
    } finally {
      setCouncilLoading(false);
    }
  };

  const togglePersona = async (personaKey, currentlyDisabled) => {
    const overrides = parentConfig.council_overrides || { active_strategies: [], disabled_personas: [] };
    let newDisabled = [...(overrides.disabled_personas || [])];
    if (currentlyDisabled) {
      newDisabled = newDisabled.filter(k => k !== personaKey);
    } else {
      newDisabled.push(personaKey);
    }
    try {
      await fetch(`${API}/api/parent/council-overrides`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ disabled_personas: newDisabled }),
      });
      fetchCouncilPreview(); // Refresh
    } catch (e) {
      console.error('Failed to toggle persona:', e);
    }
  };

  // ── Settings Handlers ─────────────────────────────────
  const saveSettings = async (field, value) => {
    try {
      const res = await fetch(`${API}/api/parent/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaveFeedback('Settings saved!');
      setTimeout(() => setSaveFeedback(''), 3000);
    } catch (e) {
      console.error('Failed to save settings:', e);
    }
  };

  const handlePinReset = async () => {
    setPinFeedback('');
    try {
      const res = await fetch(`${API}/api/parent/pin-reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_pin: currentPin, new_pin: newPin }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setPinFeedback('✅ PIN updated!');
      setCurrentPin('');
      setNewPin('');
    } catch (e) {
      setPinFeedback(`❌ ${e.message}`);
    }
  };

  const fetchAllUploads = async () => {
    try {
      const res = await fetch(`${API}/api/uploads`);
      if (!res.ok) return;
      const data = await res.json();
      setAllUploads(data.files || []);
    } catch (e) {
      console.error('Failed to fetch uploads:', e);
    }
  };

  const deleteUpload = async (filename) => {
    try {
      await fetch(`${API}/api/uploads/${filename}`, { method: 'DELETE' });
      fetchAllUploads();
    } catch (e) {
      console.error('Failed to delete upload:', e);
    }
  };

  // ── Report Handlers ──────────────────────────────────
  const uploadReport = async (file, category) => {
    setReportUploading(category);
    setReportFeedback('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API}/api/parent/report-upload?category=${category}`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setReportFeedback(`✅ ${data.filename} processed (${data.insights_count} insights extracted)`);
      fetchDigest();
    } catch (e) {
      setReportFeedback(`❌ Upload failed: ${e.message}`);
    } finally {
      setReportUploading(null);
      setTimeout(() => setReportFeedback(''), 5000);
    }
  };

  const fetchDigest = async () => {
    try {
      const res = await fetch(`${API}/api/parent/report-digest`);
      if (!res.ok) return;
      const data = await res.json();
      setDigestData(data);
    } catch (e) {
      console.error('Failed to fetch digest:', e);
    }
  };

  const toggleIntelligence = async (enabled) => {
    setIntelligenceEnabled(enabled);
    try {
      await fetch(`${API}/api/parent/report-settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      setSaveFeedback(enabled ? 'Intelligence enabled.' : 'Intelligence disabled.');
      setTimeout(() => setSaveFeedback(''), 3000);
    } catch (e) {
      console.error('Failed to toggle intelligence:', e);
    }
  };

  const handleResetProfile = async () => {
    setResetFeedback('');
    try {
      const res = await fetch(`${API}/api/parent/reset-profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: resetPin }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setResetFeedback('✅ Profile reset to defaults.');
      setShowResetConfirm(false);
      setResetPin('');
    } catch (e) {
      setResetFeedback(`❌ ${e.message}`);
    }
  };

  // ── Original Handlers ─────────────────────────────────
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
        <button className={`parent-tab-button ${activeTab === 'student_profile' ? 'active' : ''}`} onClick={() => setActiveTab('student_profile')}>📋 Student Profile</button>
        <button className={`parent-tab-button ${activeTab === 'council' ? 'active' : ''}`} onClick={() => setActiveTab('council')}>🧠 Council</button>
        <button className={`parent-tab-button ${activeTab === 'instructions' ? 'active' : ''}`} onClick={() => setActiveTab('instructions')}>Instructions</button>
        <button className={`parent-tab-button ${activeTab === 'focus_topics' ? 'active' : ''}`} onClick={() => setActiveTab('focus_topics')}>Focus Topics</button>
        <button className={`parent-tab-button ${activeTab === 'vocabulary' ? 'active' : ''}`} onClick={() => setActiveTab('vocabulary')}>Vocabulary</button>
        <button className={`parent-tab-button ${activeTab === 'progress' ? 'active' : ''}`} onClick={() => setActiveTab('progress')}>Progress</button>
        <button className={`parent-tab-button ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')}>🏥 Reports</button>
        <button className={`parent-tab-button ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>⚙️ Settings</button>
      </nav>

      <div className="parent-tab-content">

        {/* ── STUDENT PROFILE (GUIDED INTERVIEW) ────────── */}
        {activeTab === 'student_profile' && (
          <div className="guided-interview">
            <h3>🎯 Guided Student Interview</h3>
            <p className="text-muted">Tell us about your child so Alex's Council of Therapists can personalize their approach.</p>

            {/* Hobbies & Interests */}
            <div className="interview-section">
              <h4>Hobbies & Interests <SectionUpload sectionTag="hobbies" /></h4>
              <p className="text-muted">Select all that apply, or add your own.</p>
              <div className="chip-grid">
                {HOBBY_PRESETS.map(hobby => (
                  <button key={hobby}
                    className={`chip ${selectedHobbies.includes(hobby) ? 'chip-active' : ''}`}
                    onClick={() => toggleChip(hobby, selectedHobbies, setSelectedHobbies)}
                    disabled={isSaving}
                  >{hobby}</button>
                ))}
                {selectedHobbies.filter(h => !HOBBY_PRESETS.includes(h)).map(hobby => (
                  <button key={hobby}
                    className="chip chip-active chip-custom"
                    onClick={() => toggleChip(hobby, selectedHobbies, setSelectedHobbies)}
                    disabled={isSaving}
                  >{hobby} ✕</button>
                ))}
              </div>
              <div className="add-topic-form" style={{ marginTop: '8px' }}>
                <input type="text" value={customHobby} onChange={e => setCustomHobby(e.target.value)}
                  placeholder="Add custom interest" className="add-topic-input" disabled={isSaving}
                  onKeyDown={e => e.key === 'Enter' && addCustomHobby()}
                />
                <button onClick={addCustomHobby} disabled={!customHobby.trim() || isSaving} className="save-button">Add</button>
              </div>
            </div>

            {/* Social Level */}
            <div className="interview-section">
              <h4>Social Engagement Level <SectionUpload sectionTag="social" /></h4>
              <p className="text-muted">How does your child interact socially?</p>
              <select value={socialLevel} onChange={e => setSocialLevel(e.target.value)}
                className="social-level-select" disabled={isSaving}>
                {SOCIAL_LEVELS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* Academic Weak Areas */}
            <div className="interview-section">
              <h4>Academic Weak Areas <SectionUpload sectionTag="academic" /></h4>
              <p className="text-muted">Specific subjects and topics needing support (from assignment trackers, report cards, etc.).</p>
              {academicAreas.map((area, idx) => (
                <div key={idx} className="academic-area-card">
                  <span className={`severity-badge severity-${area.severity}`}>{area.severity.toUpperCase()}</span>
                  <strong>{area.subject}</strong> — {area.specific_area}
                  <button onClick={() => removeAcademicArea(idx)} className="remove-tag-button" disabled={isSaving}>✕</button>
                </div>
              ))}
              <div className="academic-area-form">
                <input type="text" value={newSubject} onChange={e => setNewSubject(e.target.value)}
                  placeholder="Subject (e.g., Biology)" disabled={isSaving} />
                <input type="text" value={newSpecificArea} onChange={e => setNewSpecificArea(e.target.value)}
                  placeholder="Specific area (e.g., Evolution concepts)" disabled={isSaving} />
                <select value={newSeverity} onChange={e => setNewSeverity(e.target.value)} disabled={isSaving}>
                  {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                </select>
                <button onClick={addAcademicArea} disabled={!newSubject.trim() || !newSpecificArea.trim() || isSaving} className="save-button">Add Area</button>
              </div>
            </div>

            {/* Stress Indicators */}
            <div className="interview-section">
              <h4>Current Stress Factors</h4>
              <p className="text-muted">Select any that currently apply.</p>
              <div className="chip-grid">
                {STRESS_OPTIONS.map(stress => (
                  <button key={stress}
                    className={`chip chip-stress ${selectedStressors.includes(stress) ? 'chip-active' : ''}`}
                    onClick={() => toggleChip(stress, selectedStressors, setSelectedStressors)}
                    disabled={isSaving}
                  >{stress}</button>
                ))}
              </div>
            </div>

            {/* Learning Style */}
            <div className="interview-section">
              <h4>Learning Style Preferences</h4>
              <p className="text-muted">How does your child learn best?</p>
              <div className="chip-grid">
                {LEARNING_STYLES.map(style => (
                  <button key={style}
                    className={`chip chip-learn ${selectedLearningStyles.includes(style) ? 'chip-active' : ''}`}
                    onClick={() => toggleChip(style, selectedLearningStyles, setSelectedLearningStyles)}
                    disabled={isSaving}
                  >{style}</button>
                ))}
              </div>
            </div>

            <button onClick={saveStudentProfile} disabled={isSaving} className="save-button save-profile-button">
              {isSaving ? 'Saving Profile...' : '💾 Save Student Profile'}
            </button>
            {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
          </div>
        )}

        {/* ── COUNCIL OF THERAPISTS ──────────────────── */}
        {activeTab === 'council' && (
          <div className="council-tab">
            <h3>🧠 Council of Therapists</h3>
            <p className="text-muted">These therapeutic perspectives shape how Alex interacts, based on the Student Profile.</p>

            {councilLoading ? (
              <p className="text-muted">Loading council status...</p>
            ) : councilStatus ? (
              <>
                <div className="council-persona-grid">
                  {councilStatus.personas.map(persona => (
                    <div key={persona.key} className={`council-persona-card ${persona.active ? 'persona-active' : 'persona-inactive'}`}>
                      <div className="persona-card-header">
                        <span className="persona-icon">{persona.icon}</span>
                        <h4>{persona.name}</h4>
                        <span className={`persona-badge ${persona.active ? 'badge-active' : 'badge-inactive'}`}>
                          {persona.active ? '● ACTIVE' : '○ INACTIVE'}
                        </span>
                      </div>
                      <p className="persona-description">{persona.description}</p>
                      <div className="persona-controls">
                        {persona.always_active ? (
                          <span className="text-muted" style={{ fontSize: '0.75rem' }}>Core persona — always active</span>
                        ) : (
                          <button
                            className={`persona-toggle ${persona.disabled_by_parent ? 'toggle-disabled' : ''}`}
                            onClick={() => togglePersona(persona.key, persona.disabled_by_parent)}
                          >
                            {persona.disabled_by_parent ? 'Enable' : 'Disable'}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="council-strategies">
                  <h4>Active Study Strategies</h4>
                  <div className="chip-grid">
                    {(councilStatus.active_strategies || []).map(s => (
                      <span key={s} className="chip chip-active">✅ {s}</span>
                    ))}
                  </div>
                </div>

                <button className="save-button" onClick={() => setShowPromptPreview(!showPromptPreview)} style={{ marginTop: '16px' }}>
                  {showPromptPreview ? 'Hide' : '👁️ Preview'} Council Prompt
                </button>
                {showPromptPreview && (
                  <pre className="council-prompt-preview">{councilStatus.generated_prompt || 'No council prompt generated. Fill out the Student Profile first.'}</pre>
                )}
              </>
            ) : (
              <p className="text-muted">Fill out the Student Profile tab first to activate the Council.</p>
            )}
          </div>
        )}

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

        {/* ── PROFESSIONAL REPORTS ─────────────────────── */}
        {activeTab === 'reports' && (
          <div className="reports-tab">
            <h3>🏥 Professional & Clinical Reports</h3>
            <p className="text-muted">Upload medical, educational, and behavioral reports. The Council will extract key insights and adapt Alex's interaction style automatically.</p>

            <div className="report-category-grid">
              {[
                { key: 'medical', icon: '🩺', title: 'Medical / Clinical', desc: 'Doctor reports, therapist evaluations, neuropsych assessments' },
                { key: 'educational', icon: '🏫', title: 'Educational', desc: 'School reports, IEPs, teacher evaluations, progress reports' },
                { key: 'behavioral', icon: '🧩', title: 'Behavioral', desc: 'Specialist assessments, social worker notes, behavioral plans' },
              ].map(cat => (
                <div key={cat.key} className={`report-category-card ${reportUploading === cat.key ? 'report-processing' : ''}`}>
                  <div className="report-category-header">
                    <span className="report-category-icon">{cat.icon}</span>
                    <div>
                      <h4>{cat.title}</h4>
                      <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>{cat.desc}</p>
                    </div>
                  </div>
                  {reportUploading === cat.key ? (
                    <div className="report-processing-indicator">
                      <span className="processing-spinner">⏳</span> Analyzing report... The Council is extracting insights.
                    </div>
                  ) : (
                    <label className="report-upload-zone">
                      <input type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }}
                        onChange={e => { if (e.target.files[0]) uploadReport(e.target.files[0], cat.key); e.target.value = ''; }} />
                      <span>📄 Drop or click to upload</span>
                    </label>
                  )}
                  {reportIntel.reports?.filter(r => r.category === cat.key).map((r, i) => (
                    <div key={i} className="report-entry">
                      <span>{r.filename}</span>
                      <span className={`severity-badge severity-${r.status === 'processed' ? 'low' : 'high'}`}>
                        {r.status === 'processed' ? 'ANALYZED' : 'ERROR'}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {reportFeedback && <div className="save-feedback" style={{ marginTop: '12px' }}>{reportFeedback}</div>}

            {digestData && digestData.total_insights > 0 && (
              <div className="digest-preview">
                <h4>🧠 Council Intelligence Summary ({digestData.total_insights} insights)</h4>
                <div className="digest-grid">
                  {digestData.diagnoses?.length > 0 && (
                    <div className="digest-card">
                      <h5>🏥 Conditions</h5>
                      {digestData.diagnoses.map((d, i) => <p key={i}>• {d}</p>)}
                    </div>
                  )}
                  {digestData.accommodations?.length > 0 && (
                    <div className="digest-card">
                      <h5>✅ Accommodations</h5>
                      {digestData.accommodations.map((a, i) => <p key={i}>→ {a}</p>)}
                    </div>
                  )}
                  {digestData.triggers?.length > 0 && (
                    <div className="digest-card">
                      <h5>⚠️ Triggers</h5>
                      {digestData.triggers.map((t, i) => <p key={i}>⚠️ {t}</p>)}
                    </div>
                  )}
                  {digestData.strengths?.length > 0 && (
                    <div className="digest-card">
                      <h5>🌟 Strengths</h5>
                      {digestData.strengths.map((s, i) => <p key={i}>✨ {s}</p>)}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── SETTINGS ────────────────────────────────── */}
        {activeTab === 'settings' && (
          <div className="settings-tab">
            <h3>⚙️ Settings</h3>

            {/* The Council */}
            <div className="settings-section">
              <h4>🧠 The Council</h4>
              <div className="settings-row">
                <label>Feedback Intensity</label>
                <div className="intensity-toggle">
                  <button className={`intensity-btn ${intensity === 'supportive' ? 'intensity-active' : ''}`}
                    onClick={() => { setIntensity('supportive'); saveSettings('council_intensity', 'supportive'); }}>
                    💛 Supportive
                  </button>
                  <button className={`intensity-btn intensity-challenging ${intensity === 'challenging' ? 'intensity-active' : ''}`}
                    onClick={() => { setIntensity('challenging'); saveSettings('council_intensity', 'challenging'); }}>
                    🔥 Challenging
                  </button>
                </div>
                <p className="text-muted" style={{ marginTop: '8px', fontSize: '0.8rem' }}>
                  {intensity === 'supportive'
                    ? 'Alex uses gentle, encouraging language and celebrates small wins.'
                    : 'Alex pushes with follow-up questions and raises the bar incrementally.'}
                </p>
              </div>
              {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
            </div>

            {/* Intelligence Sync */}
            <div className="settings-section">
              <h4>🧠 Intelligence Sync</h4>
              <div className="settings-row">
                <label>Professional Report Context</label>
                <div className="intensity-toggle">
                  <button className={`intensity-btn ${intelligenceEnabled ? 'intensity-active' : ''}`}
                    onClick={() => toggleIntelligence(true)}>
                    ✅ Enabled
                  </button>
                  <button className={`intensity-btn ${!intelligenceEnabled ? 'intensity-active' : ''}`}
                    onClick={() => toggleIntelligence(false)}>
                    ❌ Disabled
                  </button>
                </div>
                <p className="text-muted" style={{ marginTop: '8px', fontSize: '0.8rem' }}>
                  {intelligenceEnabled
                    ? 'Clinical insights from uploaded reports are actively guiding the Council.'
                    : 'Report insights are stored but NOT being used in conversations.'}
                </p>
              </div>
              {digestData && digestData.total_insights > 0 && (
                <div className="settings-row">
                  <label>What the Council Learned ({digestData.total_insights} insights)</label>
                  <button className="save-button" onClick={() => setShowDigest(!showDigest)}>
                    {showDigest ? 'Hide Summary' : '🔍 View What Council Learned'}
                  </button>
                  {showDigest && (
                    <div className="digest-preview" style={{ marginTop: '12px' }}>
                      <div className="digest-grid">
                        {digestData.diagnoses?.length > 0 && (
                          <div className="digest-card"><h5>🏥 Conditions</h5>{digestData.diagnoses.map((d, i) => <p key={i}>• {d}</p>)}</div>
                        )}
                        {digestData.accommodations?.length > 0 && (
                          <div className="digest-card"><h5>✅ Accommodations</h5>{digestData.accommodations.map((a, i) => <p key={i}>→ {a}</p>)}</div>
                        )}
                        {digestData.triggers?.length > 0 && (
                          <div className="digest-card"><h5>⚠️ Triggers</h5>{digestData.triggers.map((t, i) => <p key={i}>⚠️ {t}</p>)}</div>
                        )}
                        {digestData.strengths?.length > 0 && (
                          <div className="digest-card"><h5>🌟 Strengths</h5>{digestData.strengths.map((s, i) => <p key={i}>✨ {s}</p>)}</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Security */}
            <div className="settings-section">
              <h4>🔒 Security</h4>
              <div className="settings-row">
                <label>PIN Reset</label>
                <div className="pin-reset-form">
                  <input type="password" value={currentPin} onChange={e => setCurrentPin(e.target.value)}
                    placeholder="Current PIN" maxLength={8} />
                  <input type="password" value={newPin} onChange={e => setNewPin(e.target.value)}
                    placeholder="New PIN (min 4 chars)" maxLength={8} />
                  <button className="save-button" onClick={handlePinReset}
                    disabled={!currentPin || newPin.length < 4}>Reset PIN</button>
                </div>
                {pinFeedback && <span className="save-feedback">{pinFeedback}</span>}
              </div>
              <div className="settings-row">
                <label>Session Timeout</label>
                <select value={sessionTimeout} onChange={e => {
                  const val = parseInt(e.target.value);
                  setSessionTimeout(val);
                  saveSettings('session_timeout_minutes', val);
                }} className="social-level-select">
                  {TIMEOUT_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="text-muted" style={{ marginTop: '4px', fontSize: '0.8rem' }}>
                  Auto-lock the Parent Portal after inactivity.
                </p>
              </div>
            </div>

            {/* Data Sync */}
            <div className="settings-section">
              <h4>📁 Data Sync</h4>
              <div className="settings-row">
                <label>Document Library ({allUploads.length} files)</label>
                {allUploads.length === 0 ? (
                  <p className="text-muted">No documents uploaded yet. Use the 📎 icons in Student Profile to add files.</p>
                ) : (
                  <table className="progress-table" style={{ marginTop: '8px' }}>
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th>Section</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {allUploads.map((file, idx) => (
                        <tr key={idx}>
                          <td>{file.filename}</td>
                          <td><span className="chip chip-active" style={{ fontSize: '0.7rem', padding: '2px 8px' }}>{file.section_tag}</span></td>
                          <td>.{file.type}</td>
                          <td>{file.text_length} chars</td>
                          <td>
                            <button className="delete-file-button" onClick={() => deleteUpload(file.filename)}>🗑️</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <div className="settings-row settings-danger-zone">
                <label>⚠️ Resonance Reset</label>
                <p className="text-muted">Clear the current student profile, council settings, and all instructions to start fresh.</p>
                {!showResetConfirm ? (
                  <button className="reset-button" onClick={() => setShowResetConfirm(true)}>Reset Resonance Profile</button>
                ) : (
                  <div className="reset-confirm">
                    <p style={{ color: '#E74C3C', fontWeight: 600 }}>This action cannot be undone. Enter your PIN to confirm:</p>
                    <input type="password" value={resetPin} onChange={e => setResetPin(e.target.value)}
                      placeholder="Enter PIN" maxLength={8} />
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <button className="reset-button" onClick={handleResetProfile} disabled={!resetPin}>Confirm Reset</button>
                      <button className="save-button" onClick={() => { setShowResetConfirm(false); setResetPin(''); }}>Cancel</button>
                    </div>
                    {resetFeedback && <span className="save-feedback">{resetFeedback}</span>}
                  </div>
                )}
              </div>
            </div>

            {/* Commercial */}
            <div className="settings-section">
              <h4>📋 Commercial</h4>
              <div className="settings-row">
                <label>Beta Feedback</label>
                <p className="text-muted">Report bugs, stability issues, or feature requests.</p>
                <textarea className="instructions-textarea" style={{ minHeight: '80px' }}
                  value={betaFeedback} onChange={e => setBetaFeedback(e.target.value)}
                  placeholder="Describe any issues or suggestions..." />
                <button className="save-button" onClick={() => {
                  if (betaFeedback.trim()) {
                    console.log('[Beta Feedback]', betaFeedback);
                    setSaveFeedback('Feedback submitted! Thank you.');
                    setBetaFeedback('');
                    setTimeout(() => setSaveFeedback(''), 3000);
                  }
                }} disabled={!betaFeedback.trim()}>Submit Feedback</button>
                {saveFeedback && <span className="save-feedback">{saveFeedback}</span>}
              </div>
            </div>
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