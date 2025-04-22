# Cogni API Deployment Instructions

## Local Deployment (Development)

1. Make sure you have all required files:
   ```
   .env                   # Contains API keys (COGNI_API_KEY, etc.)
   requirements.txt       # Python dependencies
   infra_core/            # API code
   run_cogni_api.py       # Local development runner
   ```

2. Run locally:
   ```bash
   python run_cogni_api.py
   ```
   
3. Test locally:
   ```bash
   curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your-api-key>" \
     -d '{"message": "What is CogniDAO?"}'
   ```

## Production Deployment

1. **Prepare files** - Ensure all files are in place:
   ```
   ./                     # Project root
   ├── .env               # Environment variables
   ├── Dockerfile         # Docker configuration
   ├── .dockerignore      # Files to exclude from Docker
   ├── requirements.txt   # Python dependencies
   ├── run_cogni_api.py   # API entry point
   ├── infra_core/        # Core API code
   └── deploy/            # Deployment files
       ├── docker-compose.yml
       ├── Caddyfile
       └── deploy.sh
   ```

2. **Deploy to server**:
   ```bash
   # Create remote directory
   ssh user@your-server-ip "mkdir -p ~/cogni-backend"
   
   # Copy all necessary files
   scp -r Dockerfile .dockerignore requirements.txt run_cogni_api.py .env infra_core/ deploy/ user@your-server-ip:~/cogni-backend/
   
   # SSH to server
   ssh user@your-server-ip
   
   # Deploy
   cd ~/cogni-backend/deploy
   ./deploy.sh
   ```

3. **Verify deployment**:
   ```bash
   curl -f https://api.cognidao.org/healthz
   # Should return: {"status":"healthy"}
   
   # Test the chat endpoint:
   curl -X POST "https://api.cognidao.org/chat" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your-api-key>" \
     -d '{"message": "What is CogniDAO?"}'
   ```

## Updating the Deployment

1. Make and test your changes locally
2. Copy the updated files to the server:
   ```bash
   scp -r updated_files user@your-server-ip:~/cogni-backend/
   ```
3. SSH to the server and redeploy:
   ```bash
   ssh user@your-server-ip
   cd ~/cogni-backend/deploy
   docker compose down
   docker compose up --build -d
   ``` 