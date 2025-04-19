#!/bin/bash
# Healthcheck script for Cogni API
# This script reads configuration from healthcheck.json and validates container health

set -e

# Configuration
CONFIG_FILE="$(dirname "$0")/healthcheck.json"
LOG_FILE="/var/log/cogni-healthcheck.log"
LOG_LEVEL="INFO"

# Load configuration if file exists
if [ -f "$CONFIG_FILE" ]; then
  # Extract values using jq if available
  if command -v jq >/dev/null 2>&1; then
    LOG_FILE=$(jq -r '.logging.failed_checks_log // "/var/log/cogni-healthcheck.log"' "$CONFIG_FILE")
    LOG_LEVEL=$(jq -r '.logging.log_level // "INFO"' "$CONFIG_FILE")
  fi
fi

# Create log directory if it doesn't exist
log_dir=$(dirname "$LOG_FILE")
mkdir -p "$log_dir" 2>/dev/null || true

# Logging function
log() {
  local level="$1"
  local message="$2"
  
  # Only log if level is sufficient
  case "$LOG_LEVEL" in
    "DEBUG") ;;
    "INFO") 
      if [ "$level" = "DEBUG" ]; then return; fi
      ;;
    "WARN") 
      if [ "$level" = "DEBUG" ] || [ "$level" = "INFO" ]; then return; fi
      ;;
    "ERROR") 
      if [ "$level" != "ERROR" ] && [ "$level" != "FATAL" ]; then return; fi
      ;;
  esac
  
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

# Check API health
check_api() {
  log "INFO" "Checking API health..."
  
  # Default API check command
  local check_cmd="curl -s -f -o /dev/null -w '%{http_code}' http://localhost:8000/healthz"
  local expected=200
  
  # Load from config if jq is available
  if command -v jq >/dev/null 2>&1 && [ -f "$CONFIG_FILE" ]; then
    check_cmd=$(jq -r '.container_monitors[0].check_command // "curl -s -f -o /dev/null -w '"'"'%{http_code}'"'"' http://localhost:8000/healthz"' "$CONFIG_FILE")
    expected=$(jq -r '.container_monitors[0].expected_status // 200' "$CONFIG_FILE")
  fi
  
  # Execute the health check
  status=$(eval "$check_cmd" 2>/dev/null || echo "failed")
  
  if [ "$status" = "$expected" ]; then
    log "INFO" "API health check passed: $status"
    return 0
  else
    log "ERROR" "API health check failed. Got: $status, Expected: $expected"
    return 1
  fi
}

# Main function
main() {
  log "INFO" "Starting Cogni healthcheck"
  
  if check_api; then
    log "INFO" "All checks passed"
    exit 0
  else
    log "ERROR" "Health check failed"
    exit 1
  fi
}

# Run the main function
main 