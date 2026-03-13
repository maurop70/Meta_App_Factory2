/**
 * warroom_server.js — War Room Dedicated Server (Port 3000)
 * ═══════════════════════════════════════════════════════════
 * Express server that serves the production build of the
 * factory_ui React app and proxies WebSocket connections
 * to the FastAPI backend on port 8000.
 *
 * Usage:
 *   1. cd factory_ui && npm run build
 *   2. node warroom_server.js
 *   → http://localhost:3000
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3000;
const DIST_DIR = path.join(__dirname, 'factory_ui', 'dist');

// ── MIME Types ──────────────────────────────────────────
const MIME = {
  '.html': 'text/html',
  '.js':   'application/javascript',
  '.css':  'text/css',
  '.json': 'application/json',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
  '.woff': 'font/woff',
  '.woff2':'font/woff2',
  '.ttf':  'font/ttf',
};

// ── Server ──────────────────────────────────────────────
const server = http.createServer((req, res) => {
  // CORS headers for API proxying
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Serve static files from dist
  let filePath = path.join(DIST_DIR, req.url === '/' ? 'index.html' : req.url);

  // SPA fallback: if file doesn't exist, serve index.html
  if (!fs.existsSync(filePath)) {
    filePath = path.join(DIST_DIR, 'index.html');
  }

  const ext = path.extname(filePath);
  const contentType = MIME[ext] || 'application/octet-stream';

  try {
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
  } catch (err) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found');
  }
});

server.listen(PORT, () => {
  console.log(`
╔══════════════════════════════════════════════════╗
║  ⚔️  WAR ROOM — Adversarial Boardroom Server     ║
║  http://localhost:${PORT}                          ║
║                                                  ║
║  Requires:                                       ║
║    • FastAPI backend on port 8000                 ║
║    • factory_ui production build (npm run build)  ║
╚══════════════════════════════════════════════════╝
  `);
});
