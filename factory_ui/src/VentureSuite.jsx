import React, { useState, useEffect } from 'react';

const styles = {
  container: {
    display: 'flex',
    height: '100%',
    width: '100%',
    background: 'var(--bg-chat)',
    borderRadius: '12px',
    overflow: 'hidden',
    border: '1px solid var(--border)',
    color: '#e2e8f0',
    fontFamily: 'Inter, sans-serif'
  },
  sidebar: {
    width: '260px',
    background: 'rgba(10, 14, 23, 0.8)',
    borderRight: '1px solid var(--border)',
    padding: '24px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },
  main: {
    flex: 1,
    padding: '32px 48px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column'
  },
  stepItem: {
    padding: '10px 12px',
    borderRadius: '8px',
    fontSize: '13px',
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    transition: 'all 0.2s'
  },
  stepActive: {
    background: 'rgba(16, 185, 129, 0.15)',
    color: '#34d399',
    borderLeft: '3px solid #10b981'
  },
  stepDone: {
    color: '#64748b'
  },
  stepPending: {
    color: '#475569'
  },
  input: {
    width: '100%',
    padding: '12px',
    background: 'rgba(15, 23, 42, 0.6)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    color: '#fff',
    marginBottom: '16px',
    outline: 'none',
    fontFamily: 'inherit'
  },
  button: {
    padding: '12px 24px',
    background: 'linear-gradient(135deg, #10b981, #059669)',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontWeight: 600,
    cursor: 'pointer',
    fontSize: '14px',
    marginTop: '16px'
  },
  card: {
    background: 'rgba(15, 23, 42, 0.4)',
    border: '1px solid rgba(100,116,139,0.2)',
    padding: '20px',
    borderRadius: '12px',
    marginBottom: '16px'
  }
};

const STEPS = [
  { id: 'brief', label: '1. Project Brief' },
  { id: 'market', label: '2. Market Intel' },
  { id: 'brand', label: '3. Brand Studio' },
  { id: 'financial', label: '4. Financial Model' },
  { id: 'funding', label: '5. Funding Strategy' },
  { id: 'decks', label: '6. Deliverable Suite' },
  { id: 'warroom', label: '7. War Room Brief' }
];

export default function VentureSuite({ onComplete, registry }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form states
  const [brief, setBrief] = useState({ company_name: '', industry: '', problem_statement: '' });
  const [financials, setFinancials] = useState({ equity_contribution: 50000, total_investment_needed: 150000, monthly_revenue: 0 });

  // Data states
  const [marketData, setMarketData] = useState(null);
  const [brandData, setBrandData] = useState(null);
  const [financialData, setFinancialData] = useState(null);
  const [fundingData, setFundingData] = useState(null);
  const [decksData, setDecksData] = useState(null);

  const curStep = STEPS[stepIdx];

  const callApi = async (endpoint, payload = {}) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`http://localhost:8000/api/eos/${endpoint}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const nextStep = () => setStepIdx(s => Math.min(s + 1, STEPS.length - 1));

  // Step Handlers
  const handleBriefSubmit = async () => {
    await callApi('state', brief);
    nextStep();
    handleMarketIntel();
  };

  const handleMarketIntel = async () => {
    const data = await callApi('market-intel', brief);
    if (data) { setMarketData(data.market); nextStep(); handleBrandStudio(); }
  };

  const handleBrandStudio = async () => {
    const data = await callApi('brand', brief);
    if (data) { setBrandData(data.brand); nextStep(); }
  };

  const handleFinancialSubmit = async () => {
    const data = await callApi('financial-model', financials);
    if (data) {
      setFinancialData(data);
      nextStep();
      handleFundingStrategy(financials);
    }
  };

  const handleFundingStrategy = async (finPayload) => {
    const data = await callApi('funding', finPayload);
    if (data) {
      setFundingData(data);
      nextStep();
      handleDecks();
    }
  };

  const handleDecks = async () => {
    const data = await callApi('pitch-deck');
    if (data) {
      setDecksData(data);
      nextStep();
    }
  };

  const finishVenture = async () => {
    // Scaffold base app on finish via normal command 
    onComplete(); // switches out of builder wizard into normal builder chat
  };

  // Rendering helpers
  const renderBrief = () => (
    <div>
      <h2>Initialization: Project Brief</h2>
      <p style={{color: '#94a3b8', marginBottom: '24px'}}>Define the core thesis of your new venture.</p>
      
      <label>Company/Project Name</label>
      <input style={styles.input} value={brief.company_name} onChange={e => setBrief({...brief, company_name: e.target.value})} placeholder="e.g. Aether Dynamics" />
      
      <label>Industry / Niche</label>
      <input style={styles.input} value={brief.industry} onChange={e => setBrief({...brief, industry: e.target.value})} placeholder="e.g. Autonomous AI Software" />
      
      <label>Core Problem Statement</label>
      <textarea style={{...styles.input, height: '100px', resize: 'none'}} value={brief.problem_statement} onChange={e => setBrief({...brief, problem_statement: e.target.value})} placeholder="What problem does this solve?" />
      
      <button style={styles.button} onClick={handleBriefSubmit} disabled={!brief.company_name || loading}>
        {loading ? 'Processing...' : 'Lock Initial Vectors'}
      </button>
    </div>
  );

  const renderMarket = () => (
    <div>
      <h2>Market Intelligence</h2>
      {loading ? (
        <div style={styles.card}>Deep Crawler Agent is analyzing TAM/SAM/SOM and competitors... ⏳</div>
      ) : marketData ? (
        <div style={styles.card}>
          <h3>Market Sizing</h3>
          <p><strong>TAM:</strong> {marketData.tam}</p>
          <p><strong>SAM:</strong> {marketData.sam}</p>
          <p><strong>SOM:</strong> {marketData.som}</p>
          <h3>Competitors</h3>
          <ul>
            {(marketData.competitors || []).map((c, i) => <li key={i}>{c.name} - <em>{c.weakness}</em></li>)}
          </ul>
        </div>
      ) : <button style={styles.button} onClick={handleMarketIntel}>Retry Market Intel</button>}
    </div>
  );

  const renderBrand = () => (
    <div>
      <h2>Brand Studio Identity</h2>
      {loading ? (
        <div style={styles.card}>Designer Agent is generating brand DNA... ⏳</div>
      ) : brandData ? (
        <div style={styles.card}>
          <h3 style={{margin: 0, color: '#f1f5f9'}}>{brandData.company_name}</h3>
          <p style={{color: '#94a3b8', fontStyle: 'italic'}}>{brandData.tagline}</p>
          
          <h4>Color Palette</h4>
          <div style={{display: 'flex', gap: '12px', marginBottom: '20px'}}>
            {Object.entries(brandData.brand_colors || {}).map(([k, v]) => (
              <div key={k} style={{textAlign: 'center'}}>
                <div style={{width: 40, height: 40, borderRadius: '8px', background: v, border: '1px solid rgba(255,255,255,0.1)'}} />
                <span style={{fontSize: '10px'}}>{k}</span>
              </div>
            ))}
          </div>
          <h4>Logo Prompt generated (DALL-E 3)</h4>
          <p style={{fontSize: '12px', color: '#cbd5e1', background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px'}}>{brandData.logo_prompt}</p>
          <button style={styles.button} onClick={nextStep}>Proceed to Financials</button>
        </div>
      ) : <button style={styles.button} onClick={handleBrandStudio}>Retry Brand Studio</button>}
    </div>
  );

  const renderFinancial = () => (
    <div>
      <h2>Financial Projections & Equity</h2>
      <p style={{color: '#94a3b8'}}>The CFO Agent needs equity vectors to construct the 5-year P&L.</p>
      
      <label>Founder Equity Contribution ($)</label>
      <input type="number" style={styles.input} value={financials.equity_contribution} onChange={e => setFinancials({...financials, equity_contribution: parseFloat(e.target.value)})} />
      
      <label>Total Investment Needed ($)</label>
      <input type="number" style={styles.input} value={financials.total_investment_needed} onChange={e => setFinancials({...financials, total_investment_needed: parseFloat(e.target.value)})} />
      
      <label>Projected Base Monthly Revenue ($)</label>
      <input type="number" style={styles.input} value={financials.monthly_revenue} onChange={e => setFinancials({...financials, monthly_revenue: parseFloat(e.target.value)})} />

      <button style={styles.button} onClick={handleFinancialSubmit} disabled={loading}>
        {loading ? 'CFO calculating...' : 'Generate 5-Yr XLSX Model'}
      </button>
    </div>
  );

  const renderFunding = () => (
    <div>
      <h2>Funding Strategy Formulation</h2>
      {loading ? (
        <div style={styles.card}>CEO Agent is structuring funding allocation... ⏳</div>
      ) : fundingData ? (
        <div style={styles.card}>
          <h3>Calculated Funding Gap: ${fundingData.gap?.toLocaleString()}</h3>
          <p style={{whiteSpace: 'pre-wrap', fontSize: '14px', lineHeight: 1.6}}>{fundingData.strategy}</p>
        </div>
      ) : <button style={styles.button} onClick={() => handleFundingStrategy(financials)}>Retry Funding</button>}
    </div>
  );

  const renderDecks = () => (
    <div>
      <h2>Deliverable Suite (Pitch Decks)</h2>
      {loading ? (
        <div style={styles.card}>Presentations Agent is building Investor and Customer PPTX files... ⏳</div>
      ) : decksData ? (
        <div style={styles.card}>
          <h3>✅ Pitch Decks Generated</h3>
          <ul style={{ lineHeight: 2 }}>
            <li><a href={`http://localhost:8000/api/eos/documents/${decksData.investor?.split('/').pop()}`} target="_blank" rel="noreferrer" style={{color: '#6366f1'}}>Download Investor Deck ({decksData.investor?.split('/').pop()})</a></li>
            <li><a href={`http://localhost:8000/api/eos/documents/${decksData.customer?.split('/').pop()}`} target="_blank" rel="noreferrer" style={{color: '#6366f1'}}>Download Customer Deck ({decksData.customer?.split('/').pop()})</a></li>
            {financialData && (
              <li><a href={`http://localhost:8000/api/eos/documents/${financialData.path?.split('/').pop()}`} target="_blank" rel="noreferrer" style={{color: '#10b981'}}>Download Financial Model XLSX ({financialData.path?.split('/').pop()})</a></li>
            )}
          </ul>
          <button style={styles.button} onClick={finishVenture}>Seed War Room & Enter Builder Chat</button>
        </div>
      ) : <button style={styles.button} onClick={handleDecks}>Retry Decks</button>}
    </div>
  );

  return (
    <div style={styles.container}>
      {/* Sidebar Stepper */}
      <div style={styles.sidebar}>
        <h3 style={{fontSize: '11px', textTransform: 'uppercase', color: '#64748b', margin: '0 0 16px 0'}}>Venture Operations</h3>
        {STEPS.map((s, idx) => {
          let style = styles.stepPending;
          let icon = '○';
          if (idx === stepIdx) { style = styles.stepActive; icon = '●'; }
          else if (idx < stepIdx) { style = styles.stepDone; icon = '✓'; }
          
          return (
            <div key={s.id} style={{ ...styles.stepItem, ...style }}>
              <span style={{width: '16px'}}>{icon}</span> {s.label}
            </div>
          );
        })}
      </div>

      {/* Main Content Pane */}
      <div style={styles.main}>
        {error && <div style={{padding: '12px', background: 'rgba(239,68,68,0.2)', border: '1px solid #ef4444', borderRadius: '8px', color: '#ef4444', marginBottom: '20px'}}>{error}</div>}
        
        {curStep.id === 'brief' && renderBrief()}
        {curStep.id === 'market' && renderMarket()}
        {curStep.id === 'brand' && renderBrand()}
        {curStep.id === 'financial' && renderFinancial()}
        {curStep.id === 'funding' && renderFunding()}
        {curStep.id === 'decks' && renderDecks()}
        {curStep.id === 'warroom' && (
          <div>
            <h2>Venture Initialized</h2>
            <p>Your team is active. Switch to the War Room to begin strategic debates or proceed back to the Technical Builder to scaffold the code.</p>
            <button style={styles.button} onClick={finishVenture}>Exit to Factory Floor</button>
          </div>
        )}
      </div>
    </div>
  );
}
