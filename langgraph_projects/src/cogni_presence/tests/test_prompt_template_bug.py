"""
Test for the INVALID_PROMPT_INPUT bug with ChatPromptTemplate.

This test reproduces the KeyError that occurs when LangGraph tries to use
a ChatPromptTemplate that expects 'task_context' but receives LangGraph's
standard variables: ['messages', 'is_last_step', 'remaining_steps'].
"""

import pytest
from langchain_core.messages import HumanMessage

from src.cogni_presence.agent import create_agent_node


class TestPromptTemplateBug:
    """Test cases for the ChatPromptTemplate variable mismatch bug."""

    @pytest.mark.asyncio
    async def test_agent_creation_with_missing_task_context(self):
        """
        Test that reproduces the INVALID_PROMPT_INPUT error.
        
        This test should FAIL until the prompt template is fixed to work
        with LangGraph's expected input variables.
        """
        # Mock tools are not needed for this test
        
        # Create the agent node (this should work)
        agent_node = await create_agent_node()
        assert agent_node is not None
        
        # Simulate LangGraph calling the agent with its standard state variables
        # This is where the bug occurs - LangGraph passes these variables:
        langgraph_state = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False,
            'remaining_steps': 10
        }
        
        # This should fail with KeyError about missing 'task_context'
        with pytest.raises(KeyError) as exc_info:
            # Try to invoke the agent with LangGraph's state
            await agent_node.ainvoke(langgraph_state)
        
        # Verify it's the specific error we expect
        error_message = str(exc_info.value)
        assert "task_context" in error_message
        assert "INVALID_PROMPT_INPUT" in error_message or "Input to ChatPromptTemplate is missing variables" in error_message

    @pytest.mark.asyncio 
    async def test_prompt_template_expects_task_context(self):
        """
        Test that verifies our prompt template requires task_context.
        
        This demonstrates the root cause - our template has {task_context}
        but LangGraph doesn't provide it.
        """
        from src.cogni_presence.prompts import COGNI_PRESENCE_PROMPT
        from src.shared_utils.tool_specs import generate_tool_specs_from_mcp_tools
        
        # Create a partial prompt like our agent does
        tool_specs = generate_tool_specs_from_mcp_tools([])
        partial_prompt = COGNI_PRESENCE_PROMPT.partial(tool_specs=tool_specs)
        
        # Try to format with LangGraph's variables (should fail)
        langgraph_variables = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False, 
            'remaining_steps': 10
        }
        
        with pytest.raises(KeyError) as exc_info:
            partial_prompt.format(**langgraph_variables)
            
        error_message = str(exc_info.value)
        assert "task_context" in error_message

    def test_prompt_template_structure_analysis(self):
        """
        Analyze what variables our prompt template actually expects.
        
        This helps us understand what needs to be fixed.
        """
        from src.cogni_presence.prompts import COGNI_PRESENCE_PROMPT
        
        # Get the input variables that the template expects
        expected_vars = COGNI_PRESENCE_PROMPT.input_variables
        print(f"Prompt expects these variables: {expected_vars}")
        
        # This should include 'task_context' and 'tool_specs'
        assert 'task_context' in expected_vars
        assert 'tool_specs' in expected_vars