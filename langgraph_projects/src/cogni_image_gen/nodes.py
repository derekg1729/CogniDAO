"""
CogniDAO Image Generation Nodes - Specialized nodes for image generation workflow.
"""

import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from langchain_openai import ChatOpenAI  # noqa: E402
from langchain_core.messages import HumanMessage, AIMessage  # noqa: E402
from src.shared_utils import get_logger  # noqa: E402
from src.shared_utils.tool_registry import get_tools  # noqa: E402
from .prompts import PLANNER_PROMPT, REVIEWER_PROMPT, RESPONDER_PROMPT  # noqa: E402

logger = get_logger(__name__)


async def create_planner_node():
    """Create planner node for intent classification and prompt crafting."""
    
    async def planner_node(state):
        """
        Parse user request → intent (generate | edit | variation)
        Draft + sanitize prompt (adds negative-prompt + seed if supplied)
        Decide which OpenAI image tool to invoke
        """
        # Extract user request from either direct field or last message
        user_request = state.get("user_request")
        if not user_request and state.get("messages"):
            # Get the last human message as the user request
            for msg in reversed(state["messages"]):
                if hasattr(msg, "content") and msg.content:
                    user_request = msg.content
                    break
        
        if not user_request:
            user_request = "Generate an image"  # fallback
        
        retry_count = state.get("retry_count", 0)
        
        # If retrying, incorporate previous critique
        context = ""
        if retry_count > 0 and state.get("critique"):
            context = f"Previous attempt critique: {state['critique']}\n\n"
        
        # Create planning prompt
        planning_input = f"{context}User request: {user_request}"
        
        model = ChatOpenAI(model_name='gpt-4o-mini', temperature=0.1)
        
        # Use the planner prompt to determine intent and craft prompt
        messages = [HumanMessage(content=f"{PLANNER_PROMPT}\n\n{planning_input}")]
        response = await model.ainvoke(messages)
        
        # Parse the response to extract intent and prompt
        # Simple parsing - in production, you'd use structured output
        response_text = response.content
        
        # Extract intent
        intent = "generate"  # default
        if "INTENT: edit" in response_text:
            intent = "edit"
        elif "INTENT: variation" in response_text:
            intent = "variation"
        elif "INTENT: generate" in response_text:
            intent = "generate"
        
        # Extract prompt (look for PROMPT: line)
        prompt = user_request  # fallback
        lines = response_text.split('\n')
        for line in lines:
            if line.startswith("PROMPT:"):
                prompt = line.replace("PROMPT:", "").strip()
                break
        
        # Increment retry count for next iteration
        new_retry_count = retry_count + 1 if retry_count > 0 else 0
        
        return {
            **state,
            "user_request": user_request,  # Ensure this field is set
            "intent": intent,
            "prompt": prompt,
            "retry_count": new_retry_count,
            "messages": state.get("messages", []) + [response]
        }
    
    return planner_node


async def create_image_tool_node():
    """Create image tool router node for OpenAI endpoints."""
    
    async def image_tool_node(state):
        """
        Invoke chosen endpoint: GenerateImage, EditImage, or CreateImageVariation.
        """
        intent = state.get("intent", "generate")
        prompt = state.get("prompt", "Generate an image")
        input_image = state.get("input_image")
        
        # Get OpenAI image generation tools
        tools = await get_tools("openai")  # Assuming OpenAI tools are available
        
        # Find the appropriate tool based on intent
        tool_map = {
            "generate": "GenerateImage",
            "edit": "EditImage", 
            "variation": "CreateImageVariation"
        }
        
        tool_name = tool_map.get(intent, "GenerateImage")
        
        # Find the tool
        selected_tool = None
        for tool in tools:
            if tool.name == tool_name:
                selected_tool = tool
                break
        
        if not selected_tool:
            logger.error(f"Tool {tool_name} not found")
            return {
                **state,
                "image_url": None,
                "messages": state.get("messages", []) + [AIMessage(content=f"Error: {tool_name} tool not available")]
            }
        
        # Prepare tool input based on intent
        tool_input = {"prompt": prompt}
        
        if intent == "edit" and input_image:
            tool_input["image"] = input_image
        elif intent == "variation" and input_image:
            tool_input["image"] = input_image
        
        try:
            # Invoke the tool
            result = await selected_tool.ainvoke(tool_input)
            
            # Extract image URL from result
            image_url = None
            if isinstance(result, dict):
                image_url = result.get("url") or result.get("image_url")
            elif isinstance(result, str):
                image_url = result
            
            return {
                **state,
                "image_url": image_url,
                "messages": state.get("messages", []) + [AIMessage(content=f"Generated image using {tool_name}")]
            }
            
        except Exception as e:
            logger.error(f"Tool invocation failed: {e}")
            return {
                **state,
                "image_url": None,
                "messages": state.get("messages", []) + [AIMessage(content=f"Error generating image: {str(e)}")]
            }
    
    return image_tool_node


async def create_reviewer_node():
    """Create reviewer node for quality/safety assessment."""
    
    async def reviewer_node(state):
        """
        Check image against original request (basic safety + quality)
        Emit score (0-1) and critique
        """
        user_request = state.get("user_request", "Generate an image")
        image_url = state.get("image_url")
        
        if not image_url:
            return {
                **state,
                "score": 0.0,
                "critique": "No image was generated to review"
            }
        
        model = ChatOpenAI(model_name='gpt-4o-mini', temperature=0.1)
        
        # Create review prompt
        review_input = f"""
        Original request: {user_request}
        Generated image URL: {image_url}
        
        Please review this image generation result and provide:
        1. A score from 0.0 to 1.0 (where 1.0 is perfect)
        2. A brief critique with specific feedback
        
        Format your response as:
        SCORE: [0.0-1.0]
        CRITIQUE: [your feedback]
        """
        
        messages = [HumanMessage(content=f"{REVIEWER_PROMPT}\n\n{review_input}")]
        response = await model.ainvoke(messages)
        
        # Parse response
        response_text = response.content
        
        # Extract score
        score = 0.8  # default decent score
        lines = response_text.split('\n')
        for line in lines:
            if line.startswith("SCORE:"):
                try:
                    score = float(line.replace("SCORE:", "").strip())
                    score = max(0.0, min(1.0, score))  # Clamp between 0-1
                except ValueError:
                    pass
                break
        
        # Extract critique
        critique = "Image generated successfully"
        for line in lines:
            if line.startswith("CRITIQUE:"):
                critique = line.replace("CRITIQUE:", "").strip()
                break
        
        return {
            **state,
            "score": score,
            "critique": critique,
            "messages": state.get("messages", []) + [response]
        }
    
    return reviewer_node


async def create_responder_node():
    """Create responder node for final output formatting."""
    
    async def responder_node(state):
        """
        Compose final assistant message with image_url, alt-text, and any notes.
        """
        user_request = state.get("user_request", "Generate an image")
        image_url = state.get("image_url")
        critique = state.get("critique", "No critique available")
        retry_count = state.get("retry_count", 0)
        
        model = ChatOpenAI(model_name='gpt-4o-mini', temperature=0.3)
        
        # Create response prompt
        response_input = f"""
        User request: {user_request}
        Generated image URL: {image_url}
        Quality assessment: {critique}
        Retry attempts: {retry_count}
        
        Please compose a helpful final response that includes:
        1. The image URL
        2. Alt-text description
        3. Any relevant notes about the generation process
        """
        
        messages = [HumanMessage(content=f"{RESPONDER_PROMPT}\n\n{response_input}")]
        response = await model.ainvoke(messages)
        
        return {
            **state,
            "assistant_response": response.content,
            "messages": state.get("messages", []) + [response]
        }
    
    return responder_node