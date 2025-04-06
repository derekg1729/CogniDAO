"""
OpenAI API Handler

Handles communication with OpenAI API following their standards.
"""
import os
from typing import Dict, List, Optional, Union, Any
from prefect import task
from prefect.blocks.system import Secret

try:
    import openai
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI package not installed. Install with 'pip install openai'")

@task
def initialize_openai_client() -> OpenAI:
    """
    Initialize the OpenAI client with API key from Prefect Secret.
    
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
        raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or create a Prefect Secret.")
    
    return OpenAI(api_key=api_key)

@task
def create_completion(
    client: OpenAI,
    system_message: Union[str, Dict[str, str]],
    user_prompt: str,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    top_p: float = 1.0,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
) -> Dict[str, Any]:
    """
    Create a completion using OpenAI ChatCompletion API.
    
    Args:
        client: OpenAI client instance
        system_message: System message or context as string or dict
        user_prompt: User prompt/query
        model: OpenAI model to use
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens in response
        top_p: Nucleus sampling parameter
        frequency_penalty: Frequency penalty parameter
        presence_penalty: Presence penalty parameter
        
    Returns:
        Response from OpenAI API
    """
    # Format system message if provided as string
    if isinstance(system_message, str):
        system_message = {"role": "system", "content": system_message}
    
    # Create messages array
    messages = [
        system_message,
        {"role": "user", "content": user_prompt}
    ]
    
    # Call the API
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty
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