"""
Test for the INVALID_PROMPT_INPUT bug with ChatPromptTemplate.

This test reproduces the KeyError that occurs when LangGraph tries to use
a ChatPromptTemplate that expects 'task_context' but receives LangGraph's
standard variables: ['messages', 'is_last_step', 'remaining_steps'].
"""

import pytest
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage


class TestPromptInputBug:
    """Test cases for the ChatPromptTemplate variable mismatch bug."""

    def test_cogni_presence_prompt_expects_task_context(self):
        """
        Test that verifies our prompt template requires task_context.
        
        This demonstrates the root cause - our template has {task_context}
        but LangGraph doesn't provide it.
        """
        # Create the same prompt structure as in cogni_presence/prompts.py
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

{tool_specs}

{task_context}""")
        ])
        
        # Get the input variables that the template expects
        expected_vars = COGNI_PRESENCE_PROMPT.input_variables
        print(f"Prompt expects these variables: {expected_vars}")
        
        # This should include 'task_context' and 'tool_specs'
        assert 'task_context' in expected_vars
        assert 'tool_specs' in expected_vars

    def test_prompt_with_partial_still_needs_task_context(self):
        """
        Test that even after using .partial(), the template still expects task_context.
        
        This is the exact scenario that causes the bug in our agent.
        """
        # Create the same prompt structure as in cogni_presence/prompts.py
        COGNI_PRESENCE_PROMPT = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful **CogniDAO assistant** 🤖 

{tool_specs}

{task_context}""")
        ])
        
        # Create a partial prompt like our agent does
        tool_specs = "## Available MCP Tools:\n\nNo tools currently available."
        partial_prompt = COGNI_PRESENCE_PROMPT.partial(tool_specs=tool_specs)
        
        # Check what variables are still needed
        remaining_vars = partial_prompt.input_variables
        print(f"After partial, still needs: {remaining_vars}")
        assert 'task_context' in remaining_vars
        
        # Try to format with LangGraph's variables (should fail)
        langgraph_variables = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False, 
            'remaining_steps': 10
        }
        
        # This should fail because LangGraph doesn't provide 'task_context'
        with pytest.raises(KeyError) as exc_info:
            partial_prompt.format(**langgraph_variables)
            
        error_message = str(exc_info.value)
        assert "task_context" in error_message

    def test_langgraph_expected_variables_demonstration(self):
        """
        Demonstrate what variables LangGraph actually provides to prompts.
        
        Based on the error message, LangGraph provides:
        ['messages', 'is_last_step', 'remaining_steps']
        """
        # Create a prompt that expects LangGraph's variables
        langgraph_compatible_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant. Current step: {remaining_steps} left, last step: {is_last_step}"),
            ("placeholder", "{messages}")
        ])
        
        # These are the variables LangGraph actually provides
        langgraph_state = {
            'messages': [HumanMessage(content="Hello")],
            'is_last_step': False,
            'remaining_steps': 10
        }
        
        # This should work fine
        result = langgraph_compatible_prompt.format(**langgraph_state)
        assert result is not None
        
        # Show what LangGraph expects
        expected_by_langgraph = langgraph_compatible_prompt.input_variables
        print(f"LangGraph-compatible prompt expects: {expected_by_langgraph}")
        
        # Our prompt expects different variables - this is the mismatch!
        our_prompt_vars = ['task_context', 'tool_specs']
        langgraph_vars = ['messages', 'is_last_step', 'remaining_steps']
        
        print(f"Our prompt expects: {our_prompt_vars}")
        print(f"LangGraph provides: {langgraph_vars}")
        print(f"Mismatch: {set(our_prompt_vars) - set(langgraph_vars)}")
        
        # The problem: 'task_context' is not provided by LangGraph
        assert 'task_context' not in langgraph_vars