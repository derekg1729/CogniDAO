# Task: Integrate Charter Memory with Cogni API (MVP - Lifespan Indexing)
:type: Task
:status: Deployment
:project: []
:owner: 

## Description
Implement a basic Retrieval-Augmented Generation (RAG) pipeline for the Cogni API `/chat` endpoint. This involves indexing the `CHARTER.md` file using `CogniMemoryClient.index_from_logseq` during API startup via FastAPI's lifespan events and enabling the API to query this index to provide context for answering user questions about the charter. This approach is compatible with the Docker deployment which bypasses `run_cogni_api.py`.

## Action Items
- [x] Create a dedicated directory `./charter_source/`.
- [x] Place `CHARTER.md` inside `./charter_source/`.
- [x] Modify `infra_core/cogni_api.py`:
    - [x] Define paths: `CHARTER_SOURCE_DIR = "./charter_source"`, `MEMORY_CHROMA_PATH = "infra_core/memory/chroma"`, `MEMORY_ARCHIVE_PATH = "infra_core/memory/archive"`.
    - [x] Import `CogniMemoryClient`, `os`, `contextlib.asynccontextmanager`.
    - [x] Define an `async` lifespan manager function using `@asynccontextmanager`:
        - [x] **Startup Phase (before `yield`):**
            - [x] Ensure Chroma and Archive directories exist (`os.makedirs`).
            - [x] Instantiate `CogniMemoryClient` using Chroma and Archive paths.
            - [x] Call `memory_client.index_from_logseq(logseq_dir=CHARTER_SOURCE_DIR, tag_filter=set())` to index the charter. Log success or errors.
            - [x] Store the `memory_client` instance directly on `app.state`.
        - [x] **`yield`:** Yield nothing.
        - [x] **Shutdown Phase (after `yield`):** Clean up `app.state`.
    - [x] Pass the lifespan manager function to the `FastAPI` app instance: `app = FastAPI(..., lifespan=lifespan_manager)`.
    - [x] Modify the `/chat` endpoint (`stream_chat` function):
        - [x] Access the `memory_client` from `fastapi_request.app.state.memory_client`.
        - [x] Query `memory_client.query()` with the user's message.
        - [x] Format retrieved `MemoryBlock` objects into a context string.
        - [x] Create an `augmented_message` string including the context and the original user question.
        - [x] Pass the `augmented_message` (and history) to the `send_message` function.
- [x] Start API (e.g., `python run_cogni_api.py` locally or via Docker) and test `/chat` endpoint with charter-related questions.

## Success Criteria
- [x] API starts successfully, indexing `CHARTER.md` from `./charter_source/` during the lifespan startup phase.
- [x] API `/chat` endpoint successfully retrieves relevant blocks from the charter index via the client stored in app state.
- [x] API `/chat` endpoint responds to charter-related questions using the retrieved context.
- [x] API logs show memory client initialization, indexing completion, query execution, and the augmented prompt being sent to the LLM.

## Notes
- This MVP uses FastAPI lifespan events for setup, making it compatible with direct `gunicorn`/`uvicorn` execution (like in Docker).
- Indexing occurs once during API startup.
- Uses the default 'bge' embedder and 'cogni-memory' collection name.
- Requires storing/accessing the `memory_client` instance via application state managed by the lifespan context.
- **MVP Test successful. See log summary: `infra_core/docs/logs/log-IntegrateCharterMemoryWithAPI-MVP-Test-01.json`**

## Dependencies
- `infra_core/memory/memory_client.py`
- `infra_core/cogni_api.py`
- `CHARTER.md` 