#!/bin/bash

# This script removes cognidao.local entries from /etc/hosts
# Requires sudo privileges
# Creates a backup of hosts file before making changes

echo "Creating backup of /etc/hosts at /etc/hosts.bak"
sudo cp /etc/hosts /etc/hosts.bak

echo "Removing cognidao.local entries from /etc/hosts"
sudo sed -i'.bak' '/cognidao.local/d' /etc/hosts

echo "Domain cleanup complete. Entries removed from /etc/hosts"
echo "Backup created at /etc/hosts.bak" 