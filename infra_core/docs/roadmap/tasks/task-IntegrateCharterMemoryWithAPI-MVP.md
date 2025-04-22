# Task: Integrate Charter Memory with Cogni API (MVP - Lifespan Indexing)
:type: Task
:status: todo
:project: []
:owner: 

## Description
Implement a basic Retrieval-Augmented Generation (RAG) pipeline for the Cogni API `/chat` endpoint. This involves indexing the `CHARTER.md` file using `CogniMemoryClient.index_from_logseq` during API startup via FastAPI's lifespan events and enabling the API to query this index to provide context for answering user questions about the charter. This approach is compatible with the Docker deployment which bypasses `run_cogni_api.py`.

## Action Items
- [ ] Create a dedicated directory `./charter_source/`.
- [ ] Place `CHARTER.md` inside `./charter_source/`.
- [ ] Modify `infra_core/cogni_api.py`:
    - Define paths: `CHARTER_SOURCE_DIR = "./charter_source"`, `MEMORY_CHROMA_PATH = "infra_core/memory/chroma"`, `MEMORY_ARCHIVE_PATH = "infra_core/memory/archive"`.
    - Import `CogniMemoryClient`, `os`, `contextlib.asynccontextmanager`.
    - Define an `async` lifespan manager function using `@asynccontextmanager`:
        - **Startup Phase (before `yield`):**
            - Ensure Chroma and Archive directories exist (`os.makedirs`).
            - Instantiate `CogniMemoryClient` using Chroma and Archive paths.
            - Call `memory_client.index_from_logseq(logseq_dir=CHARTER_SOURCE_DIR, tag_filter=set())` to index the charter. Log success or errors.
            - Store the `memory_client` instance (e.g., in a dictionary or simple state object) that will be `yield`ed.
        - **`yield`:** Yield the dictionary/object containing the `memory_client`.
        - **Shutdown Phase (after `yield`):** (Optional for MVP - can be empty) Clean up resources if needed.
    - Pass the lifespan manager function to the `FastAPI` app instance: `app = FastAPI(..., lifespan=lifespan_manager)`.
    - Modify the `/chat` endpoint (`stream_chat` function):
        - Access the `memory_client` from the application state passed by the lifespan manager (e.g., `request.app.state.memory_client`).
        - Query `memory_client.query()` with the user's message.
        - Format retrieved `MemoryBlock` objects into a context string.
        - Create an `augmented_message` string including the context and the original user question.
        - Pass the `augmented_message` (and history) to the `send_message` function.
- [ ] Start API (e.g., `python run_cogni_api.py` locally or via Docker) and test `/chat` endpoint with charter-related questions.

## Success Criteria
- [ ] API starts successfully, indexing `CHARTER.md` from `./charter_source/` during the lifespan startup phase.
- [ ] API `/chat` endpoint successfully retrieves relevant blocks from the charter index via the client stored in app state.
- [ ] API `/chat` endpoint responds to charter-related questions using the retrieved context.
- [ ] API logs show memory client initialization, indexing completion, query execution, and the augmented prompt being sent to the LLM.

## Notes
- This MVP uses FastAPI lifespan events for setup, making it compatible with direct `gunicorn`/`uvicorn` execution (like in Docker).
- Indexing occurs once during API startup.
- Uses the default 'bge' embedder and 'cogni-memory' collection name.
- Requires storing/accessing the `memory_client` instance via application state managed by the lifespan context.

## Dependencies
- `infra_core/memory/memory_client.py`
- `infra_core/cogni_api.py`
- `CHARTER.md` 