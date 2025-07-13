"""
CogniDAO Image Generation Nodes - Specialized nodes for image generation workflow.
"""

import sys
from pathlib import Path
from langchain_openai import ChatOpenAI  
from langchain_core.messages import HumanMessage, AIMessage  
from langgraph.types import interrupt  

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.shared_utils import get_logger  # noqa: E402
from src.shared_utils.tool_registry import get_tools  # noqa: E402
from .prompts import PLANNER_PROMPT, COGNI_IMAGE_PROFILE_TEMPLATE, PLAN_REVIEWER_PROMPT  # noqa: E402

logger = get_logger(__name__)

# Module-level singletons for heavy objects
_llm = ChatOpenAI(model_name='gpt-4o-mini', temperature=0.1)
_tools_cache = None

async def _get_openai_tools():
    """Cache OpenAI tools to avoid repeated lookups."""
    global _tools_cache
    if _tools_cache is None:
        _tools_cache = await get_tools("openai")
    return _tools_cache


def create_planner_node():
    """Create planner node for defining template variables."""
    
    async def planner_node(state):
        """
        Parse user request and define the 2 template variables:
        1. agents_with_roles - Agent configurations for the prompt template
        2. scene_focus - Team activity/background context
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
        
        from pydantic import BaseModel
        from typing import List
        
        class Agent(BaseModel):
            role_name: str
            pose: str
            prop: str
            extra_details: str
            
        class PlannerOutput(BaseModel):
            agents_with_roles: List[Agent]
            scene_focus: str
        
        structured_model = _llm.with_structured_output(PlannerOutput)
        
        # Check for reviewer feedback and human feedback, prepend if retry is needed
        needs_retry = state.get("needs_retry", False)
        suggestions = state.get("suggestions", [])
        planner_feedback = state.get("planner_feedback")
        
        feedback_sections = []
        
        # Add human feedback if present (highest priority)
        if planner_feedback:
            feedback_sections.append(f"<HUMAN_FEEDBACK>\n{planner_feedback}\n</HUMAN_FEEDBACK>")
        
        # Add reviewer suggestions if retry is needed
        if needs_retry and suggestions:
            feedback_sections.append(f"<critique>\n{chr(10).join(suggestions)}\n</critique>")
        
        if feedback_sections:
            feedback_content = "\n\n".join(feedback_sections)
            prompt_content = f"{feedback_content}\n\n{PLANNER_PROMPT}\n\nUser request: {user_request}"
        else:
            prompt_content = f"{PLANNER_PROMPT}\n\nUser request: {user_request}"
        
        # Use the planner prompt to define template variables
        messages = [AIMessage(content=prompt_content)]
        response = await structured_model.ainvoke(messages)
        
        # Direct structured output - no parsing needed!
        agents_with_roles = [agent.dict() for agent in response.agents_with_roles]
        scene_focus = response.scene_focus
        
        return {
            **state,
            "user_request": user_request,
            "agents_with_roles": agents_with_roles,
            "scene_focus": scene_focus,
            "messages": state.get("messages", []) + [AIMessage(content=f"Planned: {len(agents_with_roles)} agents for {scene_focus}")]
        }
    
    return planner_node


def create_image_tool_node():
    """Create image tool node using template variables."""
    
    async def image_tool_node(state):
        """
        Build final prompt from template variables and generate image.
        """
        agents_with_roles = state.get("agents_with_roles", [])
        scene_focus = state.get("scene_focus", "collaborative development")
        
        # Build final prompt using template
        agents_description = ", ".join([
            f"{agent.get('role_name', 'Agent')} {agent.get('pose', 'working')} with {agent.get('prop', 'tools')}"
            for agent in agents_with_roles
        ])
        
        final_prompt = COGNI_IMAGE_PROFILE_TEMPLATE.format(
            agents_with_roles=agents_description,
            scene_focus=scene_focus
        )
        
        # Debug: Log what we're sending to the MCP tool
        logger.info(f"Final prompt being sent to MCP tool: {final_prompt[:500]}...")
        
        # Get OpenAI image generation tools
        tools = await _get_openai_tools()
        
        # Find GenerateImage tool
        selected_tool = None
        for tool in tools:
            if tool.name == "GenerateImage":
                selected_tool = tool
                break
        
        if not selected_tool:
            logger.error("GenerateImage tool not found")
            return {
                **state,
                "image_url": None,
                "messages": state.get("messages", []) + [AIMessage(content="Error: GenerateImage tool not available")]
            }
        
        try:
            # Invoke the tool with final prompt
            result = await selected_tool.ainvoke({"prompt": final_prompt})
            
            # Extract image URL from result
            image_url = None
            if isinstance(result, dict):
                image_url = result.get("url") or result.get("image_url")
            elif isinstance(result, str):
                image_url = result
            
            return {
                **state,
                "image_url": image_url,
                "final_prompt": final_prompt,
                "messages": state.get("messages", []) + [AIMessage(content="Generated Cogni team image")]
            }
            
        except Exception as e:
            logger.error(f"Tool invocation failed: {e}")
            return {
                **state,
                "image_url": None,
                "final_prompt": final_prompt,
                "messages": state.get("messages", []) + [AIMessage(content=f"Error generating image: {str(e)}")]
            }
    
    return image_tool_node


def create_reviewer_node():
    """Create reviewer node to validate agents_with_roles and scene_focus before image creation."""
    
    async def reviewer_node(state):
        """
        Review the planner output (agents_with_roles and scene_focus) for quality.
        Returns structured JSON with score, needs_retry, issues, and suggestions.
        """
        agents_with_roles = state.get("agents_with_roles", [])
        scene_focus = state.get("scene_focus", "")
        user_request = state.get("user_request", "Generate an image")
        
        from pydantic import BaseModel
        from typing import List
        
        class ReviewerOutput(BaseModel):
            score: float
            needs_retry: bool
            issues: List[str]
            suggestions: List[str]
        
        structured_model = _llm.with_structured_output(ReviewerOutput)
        
        # Use the reviewer prompt from prompts.py with user_request
        reviewer_prompt = PLAN_REVIEWER_PROMPT.format(
            user_request=user_request,
            agents_with_roles=agents_with_roles,
            scene_focus=scene_focus
        )
        
        messages = [HumanMessage(content=reviewer_prompt)]
        response = await structured_model.ainvoke(messages)
        
        # Create feedback message
        if response.needs_retry:
            feedback_msg = f"Plan needs improvement (score: {response.score:.2f}). Issues: {', '.join(response.issues)}"
        else:
            feedback_msg = f"Plan approved (score: {response.score:.2f}). Ready for image generation."
        
        return {
            "attempt": 1,  # This will be added to existing attempt via operator.add
            "needs_retry": response.needs_retry,
            "score": response.score,
            "issues": response.issues,
            "suggestions": response.suggestions,
            "messages": state.get("messages", []) + [AIMessage(content=feedback_msg)]
        }
    
    return reviewer_node


def create_responder_node():
    """Create responder node for final output formatting."""
    
    async def responder_node(state):
        """
        Compose final assistant message with image_url and details.
        """
        user_request = state.get("user_request", "Generate an image")
        image_url = state.get("image_url")
        
        if image_url:
            assistant_response = f"I've generated a Cogni team image for your request: '{user_request}'\n\nImage URL: {image_url}\n\nThis image features the signature Cogni aesthetic with neon outlines, cosmic circuit backdrop, and team collaboration theme."
        else:
            assistant_response = f"I wasn't able to generate an image for your request: '{user_request}'. Please try again."
        
        return {
            **state,
            "assistant_response": assistant_response,
            "messages": state.get("messages", []) + [AIMessage(content=assistant_response)]
        }
    
    return responder_node


def create_hil_node():
    """Create human-in-the-loop checkpoint node for review after image generation."""
    
    async def hil_node(state):
        """
        Interrupt execution to allow human review of generated image and plan.
        
        On first run: Returns Interrupt object to pause execution.
        On resume: Processes human decision and updates state for conditional routing.
        """
        hil_response = interrupt(
            {
                "question": "Is this approved?",
                # Surface the output that should be
                # reviewed and approved by the human.
                "image_url": state.get("image_url")
            }
        )

        print("---human_feedback---")
        print(f"{hil_response}")
        # Example output:
        # ---human_feedback---
        # {'902425cf-9a94-de8c-c5b1-ae3b41be47de': 'hi'}

        return {"human_input": hil_response}
    
    return hil_node