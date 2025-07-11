"""
OpenAI API Handler

Handles communication with OpenAI API following their standards.
"""

import os
from typing import Dict, Optional, Union, Any, Tuple, List
from prefect import task
from prefect.blocks.system import Secret
from prefect.tasks import NO_CACHE  # correct import path for Prefect 3.3.3
import time
import random

try:
    import openai  # noqa: F401
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI package not installed. Install with 'pip install openai'")

# # Try to import Anthropic as fallback
# try:
#     import anthropic

#     ANTHROPIC_AVAILABLE = True
# except ImportError:
#     ANTHROPIC_AVAILABLE = False
#     print(
#         "Warning: Anthropic not available. Install with 'pip install anthropic' for fallback support."
#     )


@task
def initialize_openai_client() -> OpenAI:
    """
    Initialize the OpenAI client with API key from Prefect Secret.
    Optionally uses Helicone proxy for observability if HELICONE_API_KEY is set.

    Returns:
        OpenAI client instance
    """
    try:
        # Try to get API key from Prefect Secret
        api_key = Secret.load("OPENAI_API_KEY").get()
    except Exception:
        # Fallback to environment variable
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Set OPENAI_API_KEY environment variable or create a Prefect Secret."
        )

    # Lightweight client - sitecustomize.py handles Helicone automatically
    return OpenAI(api_key=api_key)


@task(cache_policy=NO_CACHE)  # Disable caching to prevent serialization errors
def create_completion(
    client: OpenAI,
    system_message: Union[str, Dict[str, str]],
    user_prompt: str,
    message_history: Optional[List[Dict[str, str]]] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    top_p: float = 1.0,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    # Helicone observability headers
    helicone_user_id: Optional[str] = None,
    helicone_session_id: Optional[str] = None,
    helicone_cache_enabled: Optional[bool] = None,
    helicone_properties: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a completion using OpenAI ChatCompletion API.

    Args:
        client: OpenAI client instance
        system_message: System message or context as string or dict
        user_prompt: User prompt/query
        message_history: Optional list of previous messages
        model: OpenAI model to use
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens in response
        top_p: Nucleus sampling parameter
        frequency_penalty: Frequency penalty parameter
        presence_penalty: Presence penalty parameter
        helicone_user_id: User ID for Helicone observability
        helicone_session_id: Session ID for Helicone observability
        helicone_cache_enabled: Cache enabled flag for Helicone observability
        helicone_properties: Properties for Helicone observability

    Returns:
        Response from OpenAI API
    """
    # Create messages array
    messages = []
    if isinstance(system_message, str):
        messages.append({"role": "system", "content": system_message})
    elif system_message:  # Assuming it's already a dict if not a string
        messages.append(system_message)

    # Add history if provided
    if message_history:
        messages.extend(message_history)

    # Add the current user prompt
    messages.append({"role": "user", "content": user_prompt})

    # Build extra headers for Helicone observability (if enabled)
    extra_headers = {}
    if helicone_user_id:
        extra_headers["Helicone-User-Id"] = helicone_user_id
    if helicone_session_id:
        extra_headers["Helicone-Session-Id"] = helicone_session_id
    if helicone_cache_enabled is not None:
        extra_headers["Helicone-Cache-Enabled"] = str(helicone_cache_enabled).lower()
    if helicone_properties:
        for key, value in helicone_properties.items():
            extra_headers[f"Helicone-Property-{key}"] = value

    # Call the API
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        extra_headers=extra_headers if extra_headers else None,
    )

    return response.model_dump()


@task
def extract_content(response: Dict[str, Any]) -> str:
    """
    Extract content from OpenAI API response.

    Args:
        response: Response from OpenAI API

    Returns:
        Extracted content as string
    """
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Could not extract content from response: {e}")


@task(cache_policy=NO_CACHE)
def create_thread(client: OpenAI, instructions: str, model: str = "gpt-4o-mini") -> Tuple[str, str]:
    """
    Create a thread and assistant for reuse across multiple completion calls.

    Args:
        client: OpenAI client instance
        instructions: System instructions for the assistant (like system message)
        model: Model to use for the assistant

    Returns:
        Tuple of (thread_id, assistant_id)
    """
    # Create a thread
    thread = client.beta.threads.create()

    # Create an assistant
    assistant = client.beta.assistants.create(
        name="ThreadedCompletion", instructions=instructions, model=model
    )

    return thread.id, assistant.id


@task(cache_policy=NO_CACHE)
def thread_completion(
    client: OpenAI,
    thread_id: str,
    assistant_id: str,
    user_prompt: str,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Send a message to a thread and get the assistant's response.

    Args:
        client: OpenAI client instance
        thread_id: ID of the thread to use
        assistant_id: ID of the assistant to use
        user_prompt: User message to send
        max_retries: Maximum number of retries for rate limit errors

    Returns:
        Response in the same format as create_completion
    """
    # Add message to thread
    client.beta.threads.messages.create(thread_id=thread_id, role="user", content=user_prompt)

    # Run the assistant
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

    retry_count = 0
    while retry_count <= max_retries:
        # Poll for completion
        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

            if run_status.status == "completed":
                break
            elif run_status.status in ["failed", "cancelled", "expired"]:
                # Check if this is a rate limit error
                if (
                    run_status.status == "failed"
                    and run_status.last_error
                    and run_status.last_error.code == "rate_limit_exceeded"
                ):
                    if retry_count < max_retries:
                        # Calculate exponential backoff with jitter
                        wait_time = (2**retry_count) + random.uniform(0, 1)
                        print(
                            f"Rate limit hit, retrying in {wait_time:.1f}s (attempt {retry_count + 1}/{max_retries + 1})"
                        )
                        time.sleep(wait_time)
                        retry_count += 1

                        # Create a new run for the retry
                        run = client.beta.threads.runs.create(
                            thread_id=thread_id, assistant_id=assistant_id
                        )
                        break  # Break inner loop to retry
                    else:
                        # Max retries reached, raise the error
                        raise ValueError(
                            f"OpenAI rate limit exceeded after {max_retries} retries. Error: {run_status.last_error.message}"
                        )
                else:
                    # Non-rate-limit failure, raise immediately
                    raise ValueError(f"Assistant run failed with status: {run_status}")

            # Wait before polling again
            time.sleep(0.5)

        # If we reach here and the run completed successfully, break out of retry loop
        if run_status.status == "completed":
            break

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)

    for message in messages.data:
        if message.role == "assistant":
            # Format response to match the structure expected by extract_content
            content = (
                message.content[0].text.value
                if hasattr(message.content[0], "text")
                else str(message.content[0])
            )
            return {"choices": [{"message": {"content": content}}]}

    # No assistant message found
    return {"choices": [{"message": {"content": ""}}]}
