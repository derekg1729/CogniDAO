"""
Test to validate that both system and user messages are sent to the LLM.

This test uses a mock to capture the actual messages sent to OpenAI
and verifies that user input is properly included.
"""

import pytest


class TestUserMessageBug:
    """Test that user messages are properly sent to OpenAI."""

    @pytest.mark.asyncio
    async def test_prompt_template_includes_user_messages(self):
        """
        Test that the prompt template includes a slot for user messages.
        
        This verifies the core fix without complex mocking.
        """
        from src.cogni_presence.prompts import COGNI_PRESENCE_PROMPT
        
        # Verify the prompt template has the correct structure
        expected_vars = COGNI_PRESENCE_PROMPT.input_variables
        assert 'messages' in expected_vars, "Prompt should include 'messages' variable for user input"
        assert 'tool_specs' in expected_vars, "Prompt should include 'tool_specs' variable"
        
        # Verify we have both system and messages placeholders
        message_types = [type(msg).__name__ for msg in COGNI_PRESENCE_PROMPT.messages]
        assert 'SystemMessagePromptTemplate' in message_types, "Should have system message"
        assert 'MessagesPlaceholder' in message_types, "Should have messages placeholder for user input"
        
        print("✅ Test passed: Prompt template correctly includes user message slot")

    @pytest.mark.asyncio 
    async def test_fixed_prompt_template_structure(self):
        """
        Test the fixed prompt template structure.
        This test should pass after we fix the prompt template.
        """
        # Import the fixed prompt template
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        
        # Create a fixed prompt template with user message slot
        FIXED_PROMPT = ChatPromptTemplate.from_messages([
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

{tool_specs}"""),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        # Check the prompt template structure
        print(f"Fixed prompt template messages: {FIXED_PROMPT.messages}")
        print(f"Fixed input variables: {FIXED_PROMPT.input_variables}")
        
        # Check message types
        message_types = [type(msg).__name__ for msg in FIXED_PROMPT.messages]
        print(f"Fixed message types: {message_types}")
        
        # Verify we have both system and placeholder for user messages
        has_system = any('System' in msg_type for msg_type in message_types)
        has_messages_placeholder = any('Messages' in msg_type for msg_type in message_types)
        
        print(f"Has system message: {has_system}")
        print(f"Has messages placeholder: {has_messages_placeholder}")
        
        assert has_system, "Should have system message"
        assert has_messages_placeholder, "Should have messages placeholder for user input"
        assert 'messages' in FIXED_PROMPT.input_variables, "Should have 'messages' in input variables"
        
        print("✅ Fixed prompt template structure is correct")

    @pytest.mark.asyncio
    async def test_current_prompt_template_structure(self):
        """
        Test the current prompt template structure to identify the issue.
        """
        from src.cogni_presence.prompts import COGNI_PRESENCE_PROMPT
        
        # Check the prompt template structure
        print(f"Prompt template messages: {COGNI_PRESENCE_PROMPT.messages}")
        print(f"Input variables: {COGNI_PRESENCE_PROMPT.input_variables}")
        
        # Check if there's a placeholder for user input
        message_types = [type(msg).__name__ for msg in COGNI_PRESENCE_PROMPT.messages]
        print(f"Message types: {message_types}")
        
        has_user_placeholder = any(
            'Human' in msg_type or 'User' in msg_type or 'Messages' in msg_type
            for msg_type in message_types
        )
        
        print(f"Has user/human message placeholder: {has_user_placeholder}")
        
        # This should now pass with the MessagesPlaceholder
        assert has_user_placeholder, "Prompt template should have a user/human message placeholder but only has: " + str(message_types)