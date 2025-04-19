#!/bin/bash
# Script to generate and display deployment keys for GitHub Actions

set -e  # Exit on any error

echo "===== GitHub Actions Deployment Key Generator ====="
echo "This script will help you create SSH keys for GitHub Actions."
echo ""

# Define key path
KEY_NAME="github_actions_deploy"
KEY_PATH="$HOME/.ssh/${KEY_NAME}"

# Check if key already exists
if [ -f "${KEY_PATH}" ]; then
  read -p "Key already exists at ${KEY_PATH}. Overwrite? (y/n): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Using existing key."
  else
    # Generate new key
    ssh-keygen -t ed25519 -f "${KEY_PATH}" -N "" -C "github-actions-deploy"
    echo "New key generated."
  fi
else
  # Generate new key
  ssh-keygen -t ed25519 -f "${KEY_PATH}" -N "" -C "github-actions-deploy"
  echo "New key generated."
fi

# Display public key
echo ""
echo "===== PUBLIC KEY ====="
echo "Add this to ~/.ssh/authorized_keys on your server:"
echo ""
cat "${KEY_PATH}.pub"

# Display private key
echo ""
echo "===== PRIVATE KEY ====="
echo "Add this as SSH_PRIVATE_KEY in GitHub Secrets:"
echo ""
cat "${KEY_PATH}"

# Instructions
echo ""
echo "===== NEXT STEPS ====="
echo "1. Copy the PRIVATE KEY to GitHub Secrets as SSH_PRIVATE_KEY"
echo "2. Add the PUBLIC KEY to your server's ~/.ssh/authorized_keys file"
echo "3. Add your server IP to GitHub Secrets as SERVER_IP"
echo "4. Add your OPENAI_API_KEY to GitHub Secrets"
echo "5. Add your COGNI_API_KEY to GitHub Secrets"
echo ""
echo "Done! Your deployment keys are ready to use." 