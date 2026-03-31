import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// ── Aether Command Suite Injection ──
import { createRoot as _createAetherRoot } from 'react-dom/client';
import AetherCommandSuite from './AetherCommandSuite.jsx';
const _aetherDiv = document.createElement('div');
_aetherDiv.id = 'aether-command-suite-root';
document.body.appendChild(_aetherDiv);
_createAetherRoot(_aetherDiv).render(<AetherCommandSuite appName="Project_Aether" />);
