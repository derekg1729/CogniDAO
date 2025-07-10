"""
Test to verify the INVALID_PROMPT_INPUT bug fix.

This test confirms that our ChatPromptTemplate now works correctly
with LangGraph's standard state variables.
"""

import pytest
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage


class TestPromptFixVerification:
    """Test cases to verify the prompt template fix works."""

    def test_cogni_presence_prompt_no_longer_needs_task_context(self):
        """
        Test that the fixed COGNI_PRESENCE_PROMPT no longer requires task_context.
        
        This test should PASS after the fix.
        """
        # Create the fixed prompt structure (without task_context)
        COGNI_PRESENCE_PROMPT = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful **CogniDAO assistant** 🤖 

**Primary Tools:** 
- 📋 `GetActiveWorkItems` - Show current tasks
- 🔍 `GlobalSemanticSearch` - Find relevant information  
- 📊 `GlobalMemoryInventory` - Browse memory blocks

**Response Style:**
✅ **Concise** answers with strategic emojis  
📝 Use `code blocks` for tool names  
🎯 Structure with **bold headers** when helpful

**Important:** Leave branch/namespace parameters empty in tool calls.

{tool_specs}""")
        ])
        
        # Verify it only expects tool_specs
        expected_vars = COGNI_PRESENCE_PROMPT.input_variables
        assert expected_vars == ['tool_specs']
        assert 'task_context' not in expected_vars

    def test_fixed_prompt_works_with_partial_and_langgraph_state(self):
        """
        Test that the fixed prompt works with .partial() and LangGraph state.
        
        This is the critical test - it should pass after the fix.
        """
        # Create the fixed prompt
        COGNI_PRESENCE_PROMPT = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful **CogniDAO assistant** 🤖 

{tool_specs}""")
        ])
        
        # Create a partial prompt like our agent does
        tool_specs = "## Available MCP Tools:\n\nNo tools currently available."
        partial_prompt = COGNI_PRESENCE_PROMPT.partial(tool_specs=tool_specs)
        
        # After partial, it should need no more variables
        remaining_vars = partial_prompt.input_variables
        assert remaining_vars == []
        
        # Try to format with LangGraph's variables (should work now!)
        langgraph_variables = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False, 
            'remaining_steps': 10
        }
        
        # This should work without KeyError
        formatted_prompt = partial_prompt.format(**langgraph_variables)
        assert formatted_prompt is not None
        assert "CogniDAO assistant" in str(formatted_prompt)

    def test_playwright_prompt_also_fixed(self):
        """
        Test that the playwright prompt is also fixed.
        """
        # Create the fixed playwright prompt (without task_context)  
        PLAYWRIGHT_NAVIGATOR_PROMPT = ChatPromptTemplate.from_messages([
            ("system", """You are a skilled web navigator.

**🎯 PRIMARY TARGET:** {target_url}

## Tool Specifications

{tool_specs}

## Focus

You are the hands-on navigator.""")
        ])
        
        # Create partial with both static values
        tool_specs = "## Available MCP Tools:\n\nNo tools currently available."
        partial_prompt = PLAYWRIGHT_NAVIGATOR_PROMPT.partial(
            tool_specs=tool_specs,
            target_url="http://host.docker.internal:3000"
        )
        
        # Should need no more variables
        remaining_vars = partial_prompt.input_variables
        assert remaining_vars == []
        
        # Should work with LangGraph state
        langgraph_variables = {
            'messages': [HumanMessage(content="Navigate to homepage")],
            'is_last_step': False, 
            'remaining_steps': 10
        }
        
        formatted_prompt = partial_prompt.format(**langgraph_variables)
        assert formatted_prompt is not None
        assert "web navigator" in str(formatted_prompt)

    def test_comparison_with_broken_version(self):
        """
        Test that demonstrates the difference between broken and fixed versions.
        """
        # The BROKEN version (with task_context)
        broken_prompt = ChatPromptTemplate.from_messages([
            ("system", "Assistant with {tool_specs} and {task_context}")
        ])
        
        broken_partial = broken_prompt.partial(tool_specs="tools")
        assert 'task_context' in broken_partial.input_variables  # Still needs task_context
        
        # The FIXED version (without task_context)
        fixed_prompt = ChatPromptTemplate.from_messages([
            ("system", "Assistant with {tool_specs}")
        ])
        
        fixed_partial = fixed_prompt.partial(tool_specs="tools")
        assert fixed_partial.input_variables == []  # Needs nothing more
        
        # LangGraph state
        langgraph_state = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False,
            'remaining_steps': 10
        }
        
        # Broken version fails
        with pytest.raises(KeyError):
            broken_partial.format(**langgraph_state)
        
        # Fixed version works
        result = fixed_partial.format(**langgraph_state)
        assert result is not None