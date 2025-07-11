"""
Integration tests for Redis checkpointer with LangGraph agents
"""

import pytest
from datetime import datetime
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis import AsyncRedisSaver

from src.simple_cogni_agent.graph import build_graph as build_simple_graph
from src.cogni_presence.graph import build_graph as build_supervisor_graph


class TestRedisCheckpointer:
    """Test Redis checkpointer integration with simple_cogni_agent"""
    
    @pytest.fixture
    def redis_uri(self):
        """Redis connection URI"""
        return "redis://localhost:6379"
    
    @pytest.fixture
    def thread_id(self):
        """Unique thread ID for each test"""
        return f"test_thread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    @pytest.mark.asyncio
    async def test_simple_cogni_agent_without_checkpointer(self):
        """Test simple_cogni_agent works without checkpointer"""
        workflow = await build_simple_graph()
        graph = workflow.compile()
        
        result = await graph.ainvoke({"messages": [HumanMessage("Hello")]})
        
        assert "messages" in result
        assert len(result["messages"]) >= 1
        assert result["messages"][-1].content
    
    @pytest.mark.asyncio
    async def test_simple_cogni_agent_with_redis_checkpointer(self, redis_uri, thread_id):
        """Test simple_cogni_agent works with Redis checkpointer"""
        workflow = await build_simple_graph()
        
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": thread_id}}
            result = await graph.ainvoke(
                {"messages": [HumanMessage("Hello from Redis test")]},
                config=config
            )
            
            assert "messages" in result
            assert len(result["messages"]) >= 1
            assert result["messages"][-1].content
    
    @pytest.mark.asyncio
    async def test_redis_thread_persistence(self, redis_uri, thread_id):
        """Test that Redis checkpointer persists conversation history"""
        workflow = await build_simple_graph()
        
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            
            # First message
            result1 = await graph.ainvoke(
                {"messages": [HumanMessage("Hello, please remember this conversation.")]},
                config=config
            )
            
            first_message_count = len(result1["messages"])
            assert first_message_count >= 2  # At least user message + response
            
            # Second message to same thread
            result2 = await graph.ainvoke(
                {"messages": [HumanMessage("Do you remember our previous conversation?")]},
                config=config
            )
            
            second_message_count = len(result2["messages"])
            
            # Should have more messages in second result (accumulated history)
            assert second_message_count > first_message_count
            assert second_message_count >= 4  # 2 original + 2 new
            
            # Verify the first message is still in history
            message_contents = [msg.content for msg in result2["messages"]]
            assert any("remember this conversation" in content for content in message_contents)
    
    @pytest.mark.asyncio
    async def test_different_threads_are_isolated(self, redis_uri):
        """Test that different thread IDs maintain separate conversation histories"""
        workflow = await build_simple_graph()
        
        thread_id_1 = f"thread_1_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        thread_id_2 = f"thread_2_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph = workflow.compile(checkpointer=checkpointer)
            
            # Send message to thread 1
            config_1 = {"configurable": {"thread_id": thread_id_1}}
            result1 = await graph.ainvoke(
                {"messages": [HumanMessage("I am in thread 1")]},
                config=config_1
            )
            
            # Send message to thread 2
            config_2 = {"configurable": {"thread_id": thread_id_2}}
            result2 = await graph.ainvoke(
                {"messages": [HumanMessage("I am in thread 2")]},
                config=config_2
            )
            
            # Thread 1 should not see thread 2's messages
            thread1_contents = [msg.content for msg in result1["messages"]]
            assert any("thread 1" in content for content in thread1_contents)
            assert not any("thread 2" in content for content in thread1_contents)
            
            # Thread 2 should not see thread 1's messages
            thread2_contents = [msg.content for msg in result2["messages"]]
            assert any("thread 2" in content for content in thread2_contents)
            assert not any("thread 1" in content for content in thread2_contents)


class TestCogniPresenceSupervisor:
    """Test Redis checkpointer integration with CogniDAO supervisor"""
    
    @pytest.fixture
    def redis_uri(self):
        """Redis connection URI"""
        return "redis://localhost:6379"
    
    @pytest.fixture
    def thread_id(self):
        """Unique thread ID for each test"""
        return f"supervisor_test_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    @pytest.mark.asyncio
    async def test_supervisor_without_checkpointer(self):
        """Test cogni_presence supervisor works without checkpointer"""
        supervisor = await build_supervisor_graph()
        graph = supervisor.compile()
        
        result = await graph.ainvoke({"messages": [HumanMessage("Hello")]})
        
        assert "messages" in result
        assert len(result["messages"]) >= 1
        assert result["messages"][-1].content
    
    @pytest.mark.asyncio
    async def test_supervisor_with_redis_checkpointer(self, redis_uri, thread_id):
        """Test cogni_presence supervisor works with Redis checkpointer"""
        supervisor = await build_supervisor_graph()
        
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph = supervisor.compile(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": thread_id}}
            result = await graph.ainvoke(
                {"messages": [HumanMessage("Hello from the supervisor test")]},
                config=config
            )
            
            assert "messages" in result
            assert len(result["messages"]) >= 1
            assert result["messages"][-1].content
    
    @pytest.mark.asyncio
    async def test_supervisor_thread_persistence(self, redis_uri, thread_id):
        """Test that supervisor persists conversation history across invocations"""
        supervisor = await build_supervisor_graph()
        
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph = supervisor.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}
            
            # First message
            result1 = await graph.ainvoke(
                {"messages": [HumanMessage("Hello, I'm testing supervisor persistence.")]},
                config=config
            )
            
            first_message_count = len(result1["messages"])
            assert first_message_count >= 2  # At least user message + response
            
            # Second message to same thread
            result2 = await graph.ainvoke(
                {"messages": [HumanMessage("Do you remember our previous conversation?")]},
                config=config
            )
            
            second_message_count = len(result2["messages"])
            
            # Should have more messages in second result (accumulated history)
            assert second_message_count > first_message_count
            assert second_message_count >= 4  # 2 original + 2 new
            
            # Verify the first message is still in history
            message_contents = [msg.content for msg in result2["messages"]]
            assert any("supervisor persistence" in content for content in message_contents)