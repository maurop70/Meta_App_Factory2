import React, { useState } from 'react';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100%',
    padding: '40px',
    background: 'linear-gradient(135deg, #0a0e17, #0f172a)',
    color: '#f8fafc',
    textAlign: 'center',
    borderRadius: '16px',
    border: '1px solid rgba(99,102,241,0.1)',
    fontFamily: 'Inter, sans-serif'
  },
  title: {
    fontSize: '32px',
    fontWeight: 700,
    marginBottom: '16px',
    background: 'linear-gradient(135deg, #e2e8f0, #a78bfa)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  subtitle: {
    fontSize: '16px',
    color: '#94a3b8',
    marginBottom: '40px',
    maxWidth: '500px',
    lineHeight: 1.5,
  },
  cards: {
    display: 'flex',
    gap: '24px',
    justifyContent: 'center',
    flexWrap: 'wrap'
  },
  card: {
    width: '320px',
    padding: '32px 24px',
    borderRadius: '16px',
    background: 'rgba(15,23,42,0.6)',
    border: '1px solid rgba(100,116,139,0.2)',
    backdropFilter: 'blur(10px)',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    textAlign: 'left',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  cardHoveredA: {
    transform: 'translateY(-8px)',
    borderColor: '#6366f1',
    boxShadow: '0 12px 30px rgba(99,102,241,0.15)',
    background: 'rgba(99,102,241,0.05)',
  },
  cardHoveredB: {
    transform: 'translateY(-8px)',
    borderColor: '#10b981',
    boxShadow: '0 12px 30px rgba(16,185,129,0.15)',
    background: 'rgba(16,185,129,0.05)',
  },
  icon: {
    fontSize: '32px',
    marginBottom: '8px'
  },
  cardTitle: {
    fontSize: '18px',
    fontWeight: 600,
    margin: 0,
    color: '#f1f5f9'
  },
  cardDesc: {
    fontSize: '14px',
    color: '#94a3b8',
    margin: 0,
    lineHeight: 1.5
  },
  featureList: {
    listStyle: 'none',
    padding: 0,
    margin: '12px 0 0 0',
    fontSize: '13px',
    color: '#cbd5e1',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  badge: {
    display: 'inline-block',
    fontSize: '10px',
    fontWeight: 700,
    padding: '4px 8px',
    borderRadius: '12px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px'
  }
};

export default function ModeSelectionScreen({ onSelectMode }) {
  const [hovered, setHovered] = useState(null);

  const resetEosAndSelect = (mode) => {
    fetch("http://localhost:5000/api/eos/reset", { method: "POST" })
      .finally(() => {
        if (mode === 'venture') {
          fetch("http://localhost:5000/api/eos/state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "venture" })
          }).then(() => onSelectMode(mode));
        } else {
          onSelectMode(mode);
        }
      });
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Project Bifurcation Protocol</h1>
      <p style={styles.subtitle}>
        The Factory detected a new initiative. Please select your operational mode. 
        Your choice dictates the autonomous agents deployed for this project.
      </p>

      <div style={styles.cards}>
        {/* MODE A */}
        <div 
          style={{ ...styles.card, ...(hovered === 'A' ? styles.cardHoveredA : {}) }}
          onMouseEnter={() => setHovered('A')}
          onMouseLeave={() => setHovered(null)}
          onClick={() => resetEosAndSelect('technical')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={styles.icon}>💻</div>
            <span style={{ ...styles.badge, background: 'rgba(99,102,241,0.2)', color: '#818cf8' }}>MODE A</span>
          </div>
          <h3 style={styles.cardTitle}>Technical Architect</h3>
          <p style={styles.cardDesc}>App Only. Standard scaffolding, UI generation, and deployment.</p>
          <ul style={styles.featureList}>
            <li>✓ Codebase generation</li>
            <li>✓ UI/UX Scaffolding</li>
            <li>✓ GitHub deployment</li>
            <li>✓ N8n configuration</li>
          </ul>
        </div>

        {/* MODE B */}
        <div 
          style={{ ...styles.card, ...(hovered === 'B' ? styles.cardHoveredB : {}) }}
          onMouseEnter={() => setHovered('B')}
          onMouseLeave={() => setHovered(null)}
          onClick={() => resetEosAndSelect('venture')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={styles.icon}>🚀</div>
            <span style={{ ...styles.badge, background: 'rgba(16,185,129,0.2)', color: '#34d399' }}>MODE B</span>
          </div>
          <h3 style={styles.cardTitle}>Venture Architect</h3>
          <p style={styles.cardDesc}>Full Startup. Activates the War Room collective and EOS Suite.</p>
          <ul style={styles.featureList}>
            <li>✓ Market Intelligence (TAM/SAM)</li>
            <li>✓ Brand Studio (Logo + Identity)</li>
            <li>✓ 5-Yr Financial Projections (XLSX)</li>
            <li>✓ Investor Pitch Deck (PPTX)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
