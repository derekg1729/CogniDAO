#!/usr/bin/env node

/**
 * Simple proxy script to run the cognidao.local domain
 * No system modifications required
 */

const http = require('http');
const httpProxy = require('http-proxy');

// Check if http-proxy is installed
try {
  require.resolve('http-proxy');
} catch (e) {
  console.error('The http-proxy package is not installed.');
  console.error('Please run: npm install -g http-proxy');
  process.exit(1);
}

// Target port (your Next.js app)
const TARGET_PORT = process.argv[2] || 3000;

// Create a proxy server
const proxy = httpProxy.createProxyServer({});

// Create the server that will handle our domain
const server = http.createServer((req, res) => {
  // Set hostname header to localhost (for Next.js routing)
  req.headers.host = `localhost:${TARGET_PORT}`;
  
  // Forward to the target
  proxy.web(req, res, { 
    target: `http://localhost:${TARGET_PORT}`,
    ws: true  // Support WebSockets for hot reload
  });
});

// Listen on port 80 if running as root, otherwise 8080
const PORT = process.getuid && process.getuid() === 0 ? 80 : 8080;

server.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║   CogniDAO Local Domain Proxy                              ║
║                                                            ║
║   Usage: Access your app at http://localhost:${PORT}         ║
║                                                            ║
║   To use a custom domain name:                             ║
║   1. Add this line to your hosts file:                     ║
║      127.0.0.1 cognidao.local                             ║
║   2. Then access: http://cognidao.local:${PORT}              ║
║                                                            ║
║   Your Next.js app must be running on port ${TARGET_PORT}        ║
║   Press Ctrl+C to stop the proxy                           ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
`);
}); 