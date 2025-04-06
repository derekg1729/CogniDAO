#!/usr/bin/env node

/**
 * CogniDAO Local Domain Setup (No sudo required)
 * This script runs a proxy that forwards cognidao.local:8080 to your Next.js app
 */

console.log(`
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║   CogniDAO Local Domain Setup (No sudo required)           ║
║                                                            ║
║   NOTE: This proxy does not modify your system files.      ║
║   You'll need to manually add this to your hosts file:     ║
║                                                            ║
║   127.0.0.1 cognidao.local                                ║
║                                                            ║
║   Instructions to edit hosts file:                         ║
║   1. Open Terminal                                         ║
║   2. Run: sudo nano /etc/hosts                             ║
║   3. Add the line above                                    ║
║   4. Save with: Ctrl+O, Enter, Ctrl+X                      ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
`);

// Check if http-proxy is installed
try {
  require.resolve('http-proxy');
} catch (e) {
  console.error('The http-proxy package is not installed.');
  console.error('Please run: npm install -g http-proxy');
  process.exit(1);
}

const http = require('http');
const httpProxy = require('http-proxy');

// Target port (your Next.js app)
const TARGET_PORT = process.argv[2] || 3000;

// Create a proxy server
const proxy = httpProxy.createProxyServer({});

// Handle proxy errors
proxy.on('error', function(err, req, res) {
  console.error('Proxy error:', err);
  res.writeHead(500, { 'Content-Type': 'text/plain' });
  res.end('Proxy error: ' + err);
});

// Create the server that will handle our domain
const server = http.createServer((req, res) => {
  // Extract hostname from request
  const host = req.headers.host;
  console.log(`Received request for: ${host}`);
  
  // Forward to the target
  proxy.web(req, res, { 
    target: `http://localhost:${TARGET_PORT}`,
    ws: true  // Support WebSockets for hot reload
  });
});

// Add WebSocket support
server.on('upgrade', function (req, socket, head) {
  proxy.ws(req, socket, head, { 
    target: `http://localhost:${TARGET_PORT}` 
  });
});

// Listen on port 8080
const PORT = 8080;
server.listen(PORT, () => {
  console.log(`
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  CogniDAO proxy server is running!                         │
│                                                            │
│  • Access with domain: http://cognidao.local:${PORT}         │
│  • Access directly: http://localhost:${PORT}                 │
│                                                            │
│  Your Next.js app must be running on port ${TARGET_PORT}        │
│  Press Ctrl+C to stop the proxy                            │
│                                                            │
└────────────────────────────────────────────────────────────┘
`);
}); 