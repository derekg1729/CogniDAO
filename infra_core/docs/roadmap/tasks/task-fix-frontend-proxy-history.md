# Task: Fix Frontend Proxy History Forwarding
:type: Task
:status: todo
:project: project-chat-history-integration

## Current Status
The Next.js API route proxy located at `app/api/ai/chat/route.ts` in the `cogniDAO-site` repository currently receives the full message history from the frontend chat component (`Chat.tsx`) but only forwards the latest message content to the FastAPI backend (`/chat`). This prevents the backend from having conversational context.

## Action Items
- [ ] **Locate Proxy File:** Confirm the file is `app/api/ai/chat/route.ts` in the `cogniDAO-site` repository.
- [ ] **Extract Full History:** Modify the request parsing logic within the `POST` function in `route.ts` to retain the complete `messages` array received from the frontend component.
- [ ] **Map History Format:** Create a new array (e.g., `historyToForward`) by mapping the extracted `messages` array (excluding the *last* message) to the format expected by the backend: `[{ role: string, content: string }]`. Ensure the `role` and `content` fields are correctly extracted from the frontend message objects.
- [ ] **Construct Backend Payload:** Create a new object (e.g., `backendPayload`) that adheres to the `CompleteQueryRequest` schema defined in the backend (`schemas/backend/completequeryrequest.schema.json`). This object must include:
    - `message`: The `content` of the *last* message received from the frontend.
    - `message_history`: The `historyToForward` array created in the previous step.
- [ ] **Update Fetch Call:** Modify the `fetch` call targeting the FastAPI backend (`${fastapiUrl}/chat`) to send the `backendPayload` object in the `body` after `JSON.stringify`.

## Test Criteria
- [ ] After deploying the frontend changes, observe the FastAPI backend logs (`infra_core/cogni_api.py`). Verify that the `✨ History:` log line shows a non-`None` array containing previous messages on subsequent requests within the same chat session.
- [ ] Perform a multi-turn conversation in the chat UI. Verify that the AI responses demonstrate awareness of previous messages in the conversation. 