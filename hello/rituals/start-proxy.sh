#!/bin/bash

# This script starts a simple proxy to forward to your Next.js app
# No need for sudo or system modifications
# Your Next.js app should be running on port 3000 (or specified port)

# Get the port number from command line or use 3000 as default
PORT=${1:-3000}

echo "Starting proxy to forward to your Next.js app on port $PORT"
echo "You can access your app at: http://localhost:8080"
echo "Press Ctrl+C to stop the proxy"

# Start the http-server with proxy option
http-server --proxy http://localhost:$PORT 