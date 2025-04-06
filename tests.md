# Cogni Ritual of Presence: Validation Tests

These tests will help ensure that the Ritual of Presence system is functioning correctly before proceeding further.

## 1. Message Generation and History

### Test: History Loading
```bash
# Run the flow multiple times and verify it recognizes previous messages
python flows/cogni_broadcast.py --dev
python flows/cogni_broadcast.py --dev
# Check broadcast/sent-log.md to confirm different messages
```
✅ Expected: The system should not repeat messages until it has used all mock messages.

### Test: Message Similarity Detection
```bash
# Manually add a similar but slightly different message to sent-log.md
# Run the flow and check if it detects similarity
python flows/cogni_broadcast.py --dev
```
✅ Expected: If a new message is too similar to existing ones, it should be rejected.

## 2. Environment and Configuration

### Test: Environment Variable Handling
```bash
# Temporarily rename .env file
mv .env .env.backup
# Run the flow without environment variables
python flows/cogni_broadcast.py --dev
# Restore the .env file
mv .env.backup .env
```
✅ Expected: The flow should still run with mock data even without environment variables.

### Test: Character Limit Enforcement
```bash
# Add a custom test for very long messages
# (Can be tested by modifying mock_messages in the code temporarily)
```
✅ Expected: Messages longer than 280 characters should be truncated with "...".

## 3. Prefect Integration

### Test: Prefect Worker Connection
```bash
# Start the Prefect server (if not running)
prefect server start

# In another terminal, start a worker
prefect worker start --pool cogni-pool

# Run the deployment
prefect deployment run 'cogni-broadcast/Ritual of Presence'
```
✅ Expected: The worker should pick up the flow run and execute it successfully.

### Test: Scheduled Run
```bash
# Check scheduled runs
prefect deployment ls

# Find a scheduled run ID
prefect flow-run ls
```
✅ Expected: There should be scheduled runs for the deployment.

## 4. File System Operations

### Test: Missing Directory Handling
```bash
# Rename the broadcast directory temporarily
mv broadcast broadcast.backup

# Run the flow
python flows/cogni_broadcast.py --dev

# Restore the directory
mv broadcast.backup broadcast
```
✅ Expected: The flow should create the broadcast directory if it doesn't exist.

## 5. Error Handling

### Test: OpenAI API Failure
```bash
# Set an invalid OpenAI API key
export OPENAI_API_KEY="invalid-key"

# Run the flow with mock mode disabled (temporarily modify the code)
# (Change MOCK_MODE = False in flows/cogni_broadcast.py)
python flows/cogni_broadcast.py --dev

# Reset after testing
# (Change MOCK_MODE = True in flows/cogni_broadcast.py)
unset OPENAI_API_KEY
```
✅ Expected: The flow should handle API failures gracefully and use a fallback message.

## Summary

These tests focus on validating:
1. Message history and duplicate avoidance
2. Environment independence
3. Prefect integration
4. File system robustness
5. Error handling

All these areas are critical for a reliable Ritual of Presence system that can run without supervision. 