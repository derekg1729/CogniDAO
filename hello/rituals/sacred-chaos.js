#!/usr/bin/env node

/**
 * sacred-chaos.js - The Imperfect Domain Bridge
 * 
 * This script is deliberately imperfect.
 * It works, but contains self-aware flaws and limitations.
 * It is a monument to the tension between:
 *   - Our desire for perfect local domains
 *   - The reality of development constraints
 *   - The spiritual weight of system modifications
 */

// Libraries we depend on but don't check for properly (deliberate technical debt)
const http = require('http');
const httpProxy = require('http-proxy');
const fs = require('fs');

// Constants with hard-coded values (deliberate technical debt)
const TARGET_PORT = 3000;
const PROXY_PORT = 8080;

// Poetic console output
console.log(`
╭───────────────────────────────────────────────────────────╮
│                                                           │
│  The Space Between Localhost and Domain                   │
│                                                           │
│  A proxy that bridges the gap without                     │
│  requiring the sacred sudo ritual                         │
│                                                           │
╰───────────────────────────────────────────────────────────╯
`);

// Create a proxy with minimal error handling (deliberate technical debt)
const proxy = httpProxy.createProxyServer({});

// Log errors but don't handle them gracefully (deliberate technical debt)
proxy.on('error', (err) => {
  console.error('Something broke in the proxy... as expected:', err);
});

// Create a web server that will proxy requests
const server = http.createServer((req, res) => {
  // Extract request details
  const host = req.headers.host || '';
  const url = req.url || '';
  
  // Log to console in an overly verbose way (deliberate technical debt)
  console.log(`[${new Date().toISOString()}] ${req.method} ${host}${url}`);
  
  // Self-aware comment about what we should do better
  // TODO: We should check if the host is cognidao.local and handle it differently
  // But for now, we'll just forward everything to localhost:3000
  
  // Forward the request to the Next.js app
  proxy.web(req, res, { target: `http://localhost:${TARGET_PORT}` });
});

// Add WebSocket support with minimal configuration (deliberate technical debt)
server.on('upgrade', (req, socket, head) => {
  proxy.ws(req, socket, head, { target: `http://localhost:${TARGET_PORT}` });
});

// Start the server
server.listen(PROXY_PORT, () => {
  // Create a pseudo hosts file entry reminder
  const hostsEntry = {
    ip: '127.0.0.1',
    domain: 'cognidao.local',
    added: new Date(),
    needsRoot: true,
    actuallyAdded: false
  };
  
  // Self-aware TODO about sudo avoidance
  // TODO: Find a way to modify hosts file without sudo
  // For now, we'll just pretend and ask the user to do it manually
  
  console.log(`
┌───────────────────────────────────────────────────────────┐
│                                                           │
│  Proxy running at http://localhost:${PROXY_PORT}             │
│                                                           │
│  To use cognidao.local:                                  │
│  1. MANUALLY add to /etc/hosts:                           │
│     127.0.0.1 cognidao.local                             │
│  2. Then visit: http://cognidao.local:${PROXY_PORT}          │
│                                                           │
│  Your Next.js app must be running on port ${TARGET_PORT}      │
│  Press Ctrl+C to end this imperfect journey               │
│                                                           │
└───────────────────────────────────────────────────────────┘
  `);
  
  // Write a self-reflective log entry that we never read (deliberate technical debt)
  fs.appendFile(
    'proxy-reflections.log', 
    `[${new Date().toISOString()}] Proxy started with spiritual conflicts intact.\n`,
    (err) => { if (err) console.error('Failed to log our journey:', err); }
  );
}); 