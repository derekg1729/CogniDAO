# Setting Up GitHub Secrets for Deployment

This guide will help you create and configure the necessary secrets for your GitHub Actions deployment workflow.

## Required Secrets

You need to add these secrets to your GitHub repository:

| Secret Name | Description |
|------------|-------------|
| `SERVER_IP` | The IP address of your server |
| `SSH_PRIVATE_KEY` | The private SSH key for connecting to your server |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `COGNI_API_KEY` | Your API authentication key |
| `HELICONE_API_KEY` | Your Helicone API key for OpenAI observability (optional) |
| `HELICONE_BASE_URL` | Helicone proxy URL (optional, defaults to https://oai.helicone.ai/v1, use http://helicone:8585/v1 for self-hosted) |

## Step 1: Generate SSH Keys (if needed)

If you don't already have SSH keys for your server:

```bash
# Generate a new SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy"

# This will create:
# - ~/.ssh/id_ed25519 (private key)
# - ~/.ssh/id_ed25519.pub (public key)
```

## Step 2: Configure Your Server

1. Copy the public key to your server:

```bash
# Replace with your server's IP
ssh-copy-id ubuntu@your-server-ip
```

Or manually:

```bash
# Get the public key content
cat ~/.ssh/id_ed25519.pub

# On your server
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

2. Test the connection:

```bash
ssh ubuntu@your-server-ip
```

## Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Add each secret:

### SERVER_IP

- Name: `SERVER_IP`
- Value: Your server's IP address (e.g., `123.456.789.10`)

### SSH_PRIVATE_KEY

- Name: `SSH_PRIVATE_KEY`
- Value: The entire content of your private key file, including header/footer lines:

```bash
# Get the content
cat ~/.ssh/id_ed25519
```

Copy everything, including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines.

### OPENAI_API_KEY

- Name: `OPENAI_API_KEY`
- Value: Your OpenAI API key (starts with `sk-`)

### COGNI_API_KEY

- Name: `COGNI_API_KEY`
- Value: Your Cogni API key (e.g., `k7jVMOVGZc0Xi1n48XcEhnGEzq6wvC6f`)

### HELICONE_API_KEY

- Name: `HELICONE_API_KEY`
- Value: Your Helicone API key for OpenAI observability (optional)

### HELICONE_BASE_URL

- Name: `HELICONE_BASE_URL`
- Value: Your Helicone proxy URL (optional, defaults to https://oai.helicone.ai/v1, use http://helicone:8585/v1 for self-hosted)

## Step 4: Server Preparation

Ensure your server has the necessary software:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose plugin
sudo apt install docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker ubuntu
```

Also, make sure ports 80 and 443 are open on your server.

## Step 5: DNS Configuration

Create an A record in your DNS settings:
- Type: A
- Name: api
- Value: Your server IP
- TTL: 3600 (or as needed)

## Security Best Practices

1. Use a dedicated user for deployments (avoid using root)
2. Consider restricting SSH key access to specific commands
3. Regularly rotate your API keys
4. Set up regular backups of your server 