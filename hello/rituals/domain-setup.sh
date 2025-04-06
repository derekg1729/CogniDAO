#!/bin/bash

# This script adds cognidao.local domain to /etc/hosts
# Requires sudo privileges

# Get the port number from command line or use 3000 as default
PORT=${1:-3000}

echo "Setting up cognidao.local to point to localhost on port $PORT"

echo "# CogniDAO local development domains" | sudo tee -a /etc/hosts
echo "127.0.0.1 cognidao.local" | sudo tee -a /etc/hosts
echo "::1 cognidao.local" | sudo tee -a /etc/hosts

echo "Domain setup complete. You can now access http://cognidao.local:$PORT"
echo "Note: You must include the port number in the URL: http://cognidao.local:$PORT" 