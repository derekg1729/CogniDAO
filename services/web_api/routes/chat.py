from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import asyncio
import logging
from typing import AsyncIterable, List, Dict, Optional

from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage, AIMessage, SystemMessage

# Imports from infra_core (adjust paths if necessary based on project structure)
from services.web_api.models import CompleteQueryRequest
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool import (
    query_doc_memory_block,
    QueryDocMemoryBlockInput,
)

# Import verify_auth from auth_utils.py
from ..auth_utils import verify_auth

# Set up logger for this router
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Chat"],
)


# Helper function moved from main.py
async def send_message(
    message: str,
    memory_blocks: Optional[List[MemoryBlock]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> AsyncIterable[str]:
    logger.info(f"⚙️ Processing message: '{message}' with history: {history}")

    callback = AsyncIteratorCallbackHandler()
    model = ChatOpenAI(
        streaming=True,
        verbose=True,
        callbacks=[callback],
    )

    # Construct LangChain message list
    lc_messages = []
    # Convert history from List[Dict] to LangChain message objects.
    if history:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if not role or not content:
                logger.warning(f"Skipping history message due to missing role/content: {msg}")
                continue
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                logger.warning(f"Skipping history message due to unknown role: {role}")

    # Prepare context from memory blocks if available
    if memory_blocks and len(memory_blocks) > 0:
        # Convert memory blocks to a context string
        context_blocks = []
        logger.info("📚 Preparing context from memory blocks:")
        for i, block in enumerate(memory_blocks):
            # Extract title from metadata if it exists
            title = block.metadata.get("title", "Memory Block")
            logger.info(f"  📄 Block {i + 1}: {title}")

            # Format the block text for the context
            formatted_block = f"--- {title} ---\n{block.text}"
            context_blocks.append(formatted_block)

            # Log a preview of what we're adding to the context
            preview = block.text.replace("\n", " ")[:100]
            if len(block.text) > 100:
                preview += "..."
            logger.info(f"    Preview: {preview}")

        context_str = "\n\n".join(context_blocks)

        # Create augmented message with context
        augmented_message = (
            f"Based on the following context information:\n\n"
            f"---CONTEXT START---\n{context_str}\n---CONTEXT END---\n\n"
            f"Please answer the user's question: {message}"
        )

        logger.info(f"📝 Created augmented message with {len(memory_blocks)} memory blocks")
        logger.info(f"❓ Original user question: {message}")

        # Add as a user message
        lc_messages.append(HumanMessage(content=augmented_message))
    else:
        # No context available, use original message
        logger.info("⚠️ No memory blocks available, using original message without context")
        lc_messages.append(HumanMessage(content=message))

    logger.info(f"📡 Sending {len(lc_messages)} messages to LangChain model")
    logger.info("▶️ Creating task with LangChain model")
    task = asyncio.create_task(model.agenerate(messages=[lc_messages]))

    # Stream tokens directly without including source blocks in the response
    token_count = 0
    full_response = ""
    try:
        logger.info("✉️ Starting token streaming...")
        async for token in callback.aiter():
            token_count += 1
            # Log important tokens for debugging
            if (
                token_count <= 5
                or token_count % 20 == 0
                or token_count >= 80
                and token_count % 10 == 0
            ):
                logger.info(f"📤 Token {token_count}: {token}")
            full_response += token
            # Simply yield the token text directly
            yield token
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        print(f"Caught exception: {e}")
    finally:
        callback.done.set()
        logger.info(f"🏁 Completed streaming {token_count} tokens")
        # Log a truncated version of the full response
        truncated_response = full_response
        if len(full_response) > 300:
            truncated_response = full_response[:150] + " ... " + full_response[-150:]
        logger.info(f"📄 Response summary: {truncated_response}")

    await task
    logger.info("✅ Task completed")


@router.post("/chat")  # Path is now the full "/chat" without a prefix
async def stream_chat(
    body: CompleteQueryRequest, fastapi_request: Request, auth=Depends(verify_auth)
):
    logger.info("✅ Received streaming chat request.")
    logger.info(f"✨ Message: {body.message}")
    logger.info(f"✨ History: {body.message_history}")

    # Access memory bank from app state
    memory_bank = None
    try:
        memory_bank = fastapi_request.app.state.memory_bank
    except AttributeError:
        logger.warning("🧠 Memory bank not found in app state.")

    # Variable to store retrieved memory blocks
    memory_blocks = []

    # Query the memory system if available
    if memory_bank:
        try:
            logger.info(f"🧠 Querying memory for: '{body.message}'")

            # Use the doc-specific query tool instead of query_semantic
            query_input = QueryDocMemoryBlockInput(
                query_text=body.message,
                top_k=3,  # Return top 3 documents
                tag_filters=["core-document"],  # Add tag filter to get core documentation
                # Explicitly set type filter to "doc" - this is handled by the tool but being explicit
                # The underlying QueryDocMemoryBlockTool forces type="doc"
            )

            # Log the input parameters
            logger.info(f"🧠 Calling query_doc_memory_block with input: {query_input}")

            # Execute the query for document blocks only
            query_result = query_doc_memory_block(query_input, memory_bank)

            # Log the query result
            logger.info(
                f"🧠 Doc query result success: {query_result.success}, blocks count: {len(query_result.blocks) if query_result.blocks else 0}"
            )

            if query_result.success and query_result.blocks:
                logger.info(f"🧠 Found {len(query_result.blocks)} relevant document blocks.")
                memory_blocks = query_result.blocks

                # Log what was found - with detailed information
                logger.info("🧠 Retrieved blocks details:")
                for i, block in enumerate(memory_blocks):
                    # Extract meaningful information for logging
                    title = block.metadata.get("title", "[No Title]")
                    doc_type = block.type
                    tags_str = ", ".join(block.tags) if block.tags else "None"

                    # Format preview with line breaks replaced
                    preview = (
                        block.text.replace("\n", " ")[:100] + "..."
                        if len(block.text) > 100
                        else block.text.replace("\n", " ")
                    )

                    # Log comprehensive information about each block
                    logger.info(f"  🔖 Block {i + 1}: {title}")
                    logger.info(f"    📋 ID: {block.id}")
                    logger.info(f"    📚 Type: {doc_type}")
                    logger.info(f"    🏷️ Tags: {tags_str}")
                    logger.info(f"    📄 Preview: {preview}")

                    # Log additional metadata if available
                    if block.metadata:
                        metadata_str = ", ".join(
                            [f"{k}: {v}" for k, v in block.metadata.items() if k != "title"]
                        )
                        logger.info(f"    ℹ️ Other Metadata: {metadata_str}")
            else:
                logger.info("🧠 No relevant document blocks found.")
                if query_result.error:
                    logger.error(f"🧠 Query error: {query_result.error}")

        except Exception as e:
            logger.error(f"🧠 Memory query failed: {e}", exc_info=True)
    else:
        logger.warning("🧠 Memory bank not available. Proceeding without memory augmentation.")

    # Pass memory blocks to the message handler
    generator = send_message(
        message=body.message, memory_blocks=memory_blocks, history=body.message_history
    )

    logger.info("▶️ Returning streaming response.")
    return StreamingResponse(generator, media_type="text/event-stream")
