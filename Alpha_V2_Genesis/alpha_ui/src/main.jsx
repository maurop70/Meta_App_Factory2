import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// ── Aether Command Suite Injection ──
import { createRoot as _createAetherRoot } from 'react-dom/client';
import AetherCommandSuite from './AetherCommandSuite.jsx';
const _aetherDiv = document.createElement('div');
_aetherDiv.id = 'aether-command-suite-root';
document.body.appendChild(_aetherDiv);
_createAetherRoot(_aetherDiv).render(<AetherCommandSuite appName="Alpha_V2_Genesis" />);
