"""
Cogni API Data Models

This file contains Cogni's API data models (Pydantic). These models define the
request and response schemas for all API endpoints and are used for:
1. Input validation
2. Response serialization
3. Automatic documentation
4. TypeScript type generation for frontend

All models must inherit from Pydantic's BaseModel.
"""

from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    """Schema for a single message in the chat history."""

    role: Literal["user", "assistant", "system"] = Field(
        ..., description="The role of the message sender."
    )
    content: str = Field(..., description="The content of the message.")


class ChatMessage(BaseModel):
    """
    Schema for a chat message request.
    This is the primary schema used for the /chat endpoint.
    """

    message: str = Field(
        ...,  # ... means required
        description="The message content to send to the AI",
        examples=["What is CogniDAO?"],
    )


class BlockReference(BaseModel):
    """
    Schema for a reference to a memory block used as a source in a chat response.
    This provides essential metadata about the block without including all fields.
    """

    id: str = Field(..., description="Unique ID of the memory block")
    type: str = Field(..., description="Type of the memory block (e.g., doc, knowledge)")
    text: str = Field(..., description="Content of the memory block")
    title: Optional[str] = Field(None, description="Title of the block, if available")
    source_file: Optional[str] = Field(None, description="Source file or document")
    source_uri: Optional[str] = Field(None, description="URI or link to the source")
    tags: Optional[List[str]] = Field(None, description="Tags associated with the block")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    relevance_score: Optional[float] = Field(
        None, description="Relevance score of this block to the query (0.0-1.0)", ge=0.0, le=1.0
    )


class ChatResponse(BaseModel):
    """
    Schema for a chat message response.
    This is returned as a stream for the /chat endpoint.
    """

    content: str = Field(..., description="The AI-generated response content")
    source_blocks: Optional[List[BlockReference]] = Field(
        None, description="Memory blocks used as sources for the response"
    )


class CompleteQueryRequest(BaseModel):
    """
    Extended schema for a chat request with additional parameters.
    This can be used for more advanced chat endpoints.
    """

    message: str = Field(
        ..., description="The message content to send to the AI", examples=["What is CogniDAO?"]
    )
    model: str = Field(default="gpt-3.5-turbo", description="The AI model to use for generation")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Controls randomness in the response. Lower is more deterministic.",
    )
    system_message: Optional[str] = Field(
        default="You are a helpful AI assistant.",
        description="Instructions for the AI assistant's behavior",
    )
    message_history: Optional[List[HistoryMessage]] = Field(
        default=None, description="Optional list of previous messages in the conversation"
    )


class ErrorResponse(BaseModel):
    """
    Schema for error responses.
    """

    detail: str = Field(..., description="A human-readable error message")
    code: Optional[str] = Field(
        None, description="An optional error code for programmatic handling"
    )
