# Project: Chat History Integration
:type: Project
:status: in-progress
:epic: [[Epic_Presence_and_Control_Loops]]

## Project Overview
This project focuses on enabling stateful conversations by integrating message history throughout the chat system, from the backend API and models to the frontend proxy communication.

## Implementation Flow
- [x] Update backend Pydantic models (`CompleteQueryRequest`, `HistoryMessage`) in `infra_core/models.py`
- [x] Generate corresponding JSON schemas (`schemas/backend/`) using `scripts/generate_schemas.py`
- [x] Update backend OpenAI handler (`create_completion` in `infra_core/openai_handler.py`) to accept and process history.
- [x] Add unit tests for backend OpenAI handler (`tests/openai/test_openai_handler.py`).
- [x] Update backend API endpoint (`/chat` in `infra_core/cogni_api.py`) to accept `CompleteQueryRequest` and pass history to processing function (`send_message`).
- [x] Add detailed logging to backend API endpoint (`/chat`) for history tracking.
- [ ] Fix frontend proxy (`app/api/ai/chat/route.ts` in `cogniDAO-site` repo) to forward message history to the backend API. `task-fix-frontend-proxy-history`

## Success Criteria
- The `/chat` endpoint successfully receives and processes the `message_history` field sent by the frontend (via its proxy).
- Backend logs confirm that the history is being included in calls to the language model.
- Users experience stateful conversations where the AI remembers previous turns in the dialogue. 