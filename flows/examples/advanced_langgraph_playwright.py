#!/usr/bin/env python3
"""
Advanced LangGraph with Playwright MCP
======================================

Demonstrates advanced LangGraph patterns with custom graph building, state management,
and multi-step workflows using playwright MCP tools.

This example shows:
1. Custom StateGraph with typed state
2. Multiple specialized nodes
3. Conditional edges and routing
4. Error handling and retry logic
5. Structured output and validation

Usage:
    python flows/examples/advanced_langgraph_playwright.py

Prerequisites:
    - Playwright MCP server running at http://127.0.0.1:58462/sse
    - OPENAI_API_KEY environment variable set
    - langgraph and langchain-mcp-adapters packages installed
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional, Literal
from typing_extensions import TypedDict
from datetime import datetime

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define structured state for the graph
class BrowserAutomationState(TypedDict):
    """State for browser automation workflows."""

    messages: List[AnyMessage]
    current_url: Optional[str]
    task_type: Optional[str]
    screenshots_taken: List[str]
    errors: List[str]
    retry_count: int
    max_retries: int
    status: Literal["pending", "in_progress", "completed", "failed"]


class AutomationTask(BaseModel):
    """Structured task definition for browser automation."""

    task_id: str = Field(..., description="Unique task identifier")
    task_type: str = Field(..., description="Type of automation task")
    description: str = Field(..., description="Human-readable task description")
    target_url: Optional[str] = Field(None, description="Target URL if applicable")
    expected_elements: List[str] = Field(
        default_factory=list, description="Expected elements to find"
    )
    success_criteria: str = Field(..., description="How to determine if task succeeded")


class PlaywrightWorkflow:
    """Advanced LangGraph workflow for browser automation."""

    def __init__(self):
        self.client = None
        self.tools = []
        self.graph = None
        self.llm = None

    async def initialize(self):
        """Initialize the MCP client and LangGraph workflow."""

        logger.info("🔧 Initializing advanced playwright workflow...")

        # Setup MCP client
        self.client = MultiServerMCPClient(
            {
                "playwright": {
                    "url": "http://127.0.0.1:58462/sse",
                    "transport": "streamable_http",
                }
            }
        )

        # Get tools
        self.tools = await self.client.get_tools()
        logger.info(f"✅ Connected to playwright MCP with {len(self.tools)} tools")

        # Setup LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
        )

        # Build the graph
        self.graph = self._build_workflow_graph()
        logger.info("🔗 Advanced workflow graph built successfully")

    def _build_workflow_graph(self) -> StateGraph:
        """Build the custom LangGraph workflow."""

        # Create the graph with our custom state
        workflow = StateGraph(BrowserAutomationState)

        # Add nodes
        workflow.add_node("plan_task", self._plan_task_node)
        workflow.add_node("execute_automation", self._execute_automation_node)
        workflow.add_node("validate_result", self._validate_result_node)
        workflow.add_node("handle_error", self._handle_error_node)
        workflow.add_node("finalize", self._finalize_node)

        # Add tool node for playwright tools
        workflow.add_node("tools", ToolNode(self.tools))

        # Define the flow
        workflow.add_edge(START, "plan_task")
        workflow.add_edge("plan_task", "execute_automation")

        # Conditional routing from execute_automation
        workflow.add_conditional_edges(
            "execute_automation",
            self._route_after_execution,
            {
                "tools": "tools",
                "validate": "validate_result",
                "error": "handle_error",
                "complete": "finalize",
            },
        )

        # Tool execution routing
        workflow.add_edge("tools", "validate_result")

        # Validation routing
        workflow.add_conditional_edges(
            "validate_result",
            self._route_after_validation,
            {"retry": "execute_automation", "error": "handle_error", "complete": "finalize"},
        )

        # Error handling routing
        workflow.add_conditional_edges(
            "handle_error",
            self._route_after_error,
            {"retry": "execute_automation", "abort": "finalize"},
        )

        workflow.add_edge("finalize", END)

        # Compile with checkpointer for state persistence
        return workflow.compile(checkpointer=MemorySaver())

    def _plan_task_node(self, state: BrowserAutomationState) -> BrowserAutomationState:
        """Analyze the user request and plan the automation task."""

        logger.info("📋 Planning automation task...")

        # Extract the latest user message
        user_message = None
        for msg in reversed(state["messages"]):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break

        if not user_message:
            user_message = "No specific task provided"

        # Use LLM to analyze and plan
        planning_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a browser automation planner. Analyze the user's request and determine:
1. What type of automation task this is (navigation, screenshot, interaction, etc.)
2. What steps need to be taken
3. What the success criteria should be

Respond with a clear plan in a structured format.""",
                ),
                ("human", "{user_request}"),
            ]
        )

        chain = planning_prompt | self.llm
        plan_response = chain.invoke({"user_request": user_message})

        # Determine task type
        task_type = "general"
        if "screenshot" in user_message.lower():
            task_type = "screenshot"
        elif "navigate" in user_message.lower() or "visit" in user_message.lower():
            task_type = "navigation"
        elif "click" in user_message.lower() or "interact" in user_message.lower():
            task_type = "interaction"

        # Update state
        updated_state = {
            **state,
            "task_type": task_type,
            "status": "in_progress",
            "retry_count": 0,
            "max_retries": 3,
            "messages": state["messages"] + [plan_response],
        }

        logger.info(f"📝 Task planned: {task_type}")
        return updated_state

    def _execute_automation_node(self, state: BrowserAutomationState) -> BrowserAutomationState:
        """Execute the automation using LLM reasoning and tool selection."""

        logger.info(f"🤖 Executing automation (attempt {state['retry_count'] + 1})")

        # Create execution prompt with available tools
        execution_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"""You are a browser automation executor with access to playwright tools.
Current task type: {state["task_type"]}
Status: {state["status"]}
Previous attempts: {state["retry_count"]}

Available tools: {[tool.name for tool in self.tools]}

Execute the automation step by step. Use the appropriate tools to accomplish the task.
If you need to take screenshots, use the screenshot tool.
If you need to navigate, use the navigation tools.
Always explain what you're doing.""",
                ),
                MessagesPlaceholder("messages"),
            ]
        )

        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        chain = execution_prompt | llm_with_tools

        try:
            response = chain.invoke({"messages": state["messages"]})

            # Update state with response
            updated_state = {
                **state,
                "messages": state["messages"] + [response],
                "retry_count": state["retry_count"] + 1,
            }

            return updated_state

        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            return {
                **state,
                "errors": state["errors"] + [str(e)],
                "retry_count": state["retry_count"] + 1,
            }

    def _validate_result_node(self, state: BrowserAutomationState) -> BrowserAutomationState:
        """Validate the automation result."""

        logger.info("✅ Validating automation result...")

        # Simple validation logic
        last_message = state["messages"][-1] if state["messages"] else None

        # Check if the task appears successful
        if last_message and hasattr(last_message, "content"):
            content = str(last_message.content)
            if "error" in content.lower() or "failed" in content.lower():
                logger.warning("⚠️ Validation detected possible error")
                return {**state, "status": "failed"}
            else:
                logger.info("✅ Validation passed")
                return {**state, "status": "completed"}

        return {**state, "status": "pending"}

    def _handle_error_node(self, state: BrowserAutomationState) -> BrowserAutomationState:
        """Handle errors and decide on retry strategy."""

        logger.warning(f"⚠️ Handling error (attempt {state['retry_count']}/{state['max_retries']})")

        if state["retry_count"] >= state["max_retries"]:
            logger.error("❌ Max retries exceeded, aborting")
            return {**state, "status": "failed"}

        # Add error handling message
        error_msg = f"Error occurred, retrying (attempt {state['retry_count']})..."
        updated_state = {
            **state,
            "messages": state["messages"] + [{"role": "assistant", "content": error_msg}],
        }

        return updated_state

    def _finalize_node(self, state: BrowserAutomationState) -> BrowserAutomationState:
        """Finalize the automation workflow."""

        logger.info(f"🏁 Finalizing workflow with status: {state['status']}")

        # Generate summary
        if state["status"] == "completed":
            summary = "✅ Automation completed successfully!"
        elif state["status"] == "failed":
            summary = f"❌ Automation failed after {state['retry_count']} attempts"
        else:
            summary = "⚠️ Automation ended with unclear status"

        final_message = {
            "role": "assistant",
            "content": f"{summary}\n\nTask type: {state['task_type']}\nRetries: {state['retry_count']}",
        }

        return {
            **state,
            "messages": state["messages"] + [final_message],
            "status": state["status"] or "completed",
        }

    # Routing functions
    def _route_after_execution(self, state: BrowserAutomationState) -> str:
        """Route after execution based on the response."""

        last_message = state["messages"][-1] if state["messages"] else None

        # Check if LLM wants to use tools
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # Check for errors
        if state["errors"]:
            return "error"

        # Default to validation
        return "validate"

    def _route_after_validation(self, state: BrowserAutomationState) -> str:
        """Route after validation."""

        if state["status"] == "completed":
            return "complete"
        elif state["status"] == "failed" and state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "error"

    def _route_after_error(self, state: BrowserAutomationState) -> str:
        """Route after error handling."""

        if state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "abort"

    async def run_automation(self, user_request: str) -> Dict[str, Any]:
        """Run an automation workflow."""

        if not self.graph:
            raise RuntimeError("Workflow not initialized. Call initialize() first.")

        # Initialize state
        initial_state = BrowserAutomationState(
            messages=[{"role": "human", "content": user_request}],
            current_url=None,
            task_type=None,
            screenshots_taken=[],
            errors=[],
            retry_count=0,
            max_retries=3,
            status="pending",
        )

        # Run the workflow
        config = {"configurable": {"thread_id": f"automation_{datetime.now().isoformat()}"}}

        try:
            result = await self.graph.ainvoke(initial_state, config=config)

            return {
                "success": result["status"] == "completed",
                "status": result["status"],
                "task_type": result["task_type"],
                "retry_count": result["retry_count"],
                "final_message": result["messages"][-1]["content"] if result["messages"] else None,
                "errors": result["errors"],
            }

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            return {"success": False, "status": "failed", "error": str(e)}


async def main():
    """Main function demonstrating advanced LangGraph workflow."""

    logger.info("🚀 Starting Advanced LangGraph Playwright Workflow")

    # Check environment
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY environment variable is required")
        return

    try:
        # Initialize workflow
        workflow = PlaywrightWorkflow()
        await workflow.initialize()

        # Example automations
        example_tasks = [
            "Take a screenshot of the current page and save it",
            "Navigate to https://example.com and take a screenshot",
            "Open a new browser tab and navigate to https://httpbin.org/get",
        ]

        logger.info("🧪 Running example automations...")

        for i, task in enumerate(example_tasks, 1):
            logger.info(f"\n📋 Task {i}: {task}")

            result = await workflow.run_automation(task)

            if result["success"]:
                logger.info(f"✅ Task {i} completed successfully")
                logger.info(f"   Final result: {result['final_message']}")
            else:
                logger.error(f"❌ Task {i} failed: {result.get('error', 'Unknown error')}")

            # Small delay between tasks
            await asyncio.sleep(2)

        # Interactive mode
        logger.info("\n🎮 Interactive mode - Enter your automation requests (type 'quit' to exit)")

        while True:
            try:
                user_input = input("\n👤 You: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    logger.info("👋 Goodbye!")
                    break

                if not user_input:
                    continue

                result = await workflow.run_automation(user_input)

                if result["success"]:
                    print(f"✅ Success: {result['final_message']}")
                else:
                    print(f"❌ Failed: {result.get('error', 'Unknown error')}")

            except KeyboardInterrupt:
                logger.info("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"❌ Error: {e}")

    except Exception as e:
        logger.error(f"❌ Application failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
