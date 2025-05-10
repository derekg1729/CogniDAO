# Cogni API Deployment

This guide explains how to deploy the Cogni API backend with HTTPS support using Docker and Caddy.

## Prerequisites

1. A server with Docker and docker-compose-plugin installed
2. Open ports 80 and 443 on your server
3. DNS A-record pointing `api.cognidao.org` to your server IP
4. The Cogni backend code and environment variables (see Project Structure below)

## Project Structure

```
./                          # Project root
├── .env                    # Environment variables
├── Dockerfile              # Docker configuration
├── .dockerignore           # Files to exclude from Docker
├── requirements.txt        # Python dependencies
├── run_cogni_api.py        # API entry point
├── legacy_logseq/             # Core API code
│   ├── __init__.py
│   ├── cogni_api.py        # FastAPI application
│   └── models.py           # Pydantic models
└── deploy/                 # Deployment files
    ├── docker-compose.yml  # Docker Compose configuration
    ├── Caddyfile           # Caddy server configuration
    └── deploy.sh           # Deployment script
```

## Local Development

To run the API locally for development:

```bash
python run_cogni_api.py
```

The API will be available at http://localhost:8000 with auto-reload enabled.

## Deployment Steps

1. Prepare your server with Docker and docker-compose-plugin.

2. Copy the necessary files to your server:
   ```bash
   # Create the destination directory
   ssh user@your-server-ip "mkdir -p ~/cogni-backend"
   
   # Copy files (from project root)
   scp -r Dockerfile .dockerignore requirements.txt run_cogni_api.py .env legacy_logseq/ deploy/ user@your-server-ip:~/cogni-backend/
   ```

3. SSH into your server:
   ```bash
   ssh user@your-server-ip
   ```

4. Build and start the containers:
   ```bash
   cd ~/cogni-backend/deploy
   ./deploy.sh
   ```

5. Verify the deployment:
   ```bash
   curl -f https://api.cognidao.org/healthz
   ```

   You should see: `{"status":"healthy"}`

## Troubleshooting

1. Check container logs:
   ```bash
   cd ~/cogni-backend/deploy
   docker compose logs
   ```

2. Check if containers are running:
   ```bash
   docker compose ps
   ```

3. Restart the containers:
   ```bash
   docker compose restart
   ```

## Security Notes

- The `.env` file contains secrets and should never be committed to version control
- TLS/HTTPS is automatically handled by Caddy with Let's Encrypt
- The API container is not directly exposed to the internet, only through Caddy
- Authentication is required for API endpoints with a Bearer token 