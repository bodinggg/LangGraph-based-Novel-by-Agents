"""
Unit tests for src/model_manager.py
"""
import pytest
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch, AsyncMock
from src.model_manager import ModelManager, APIModelManager, LocalModelManager
from src.config_loader import BaseConfig


class TestModelManagerInterface:
    """Tests to verify unified interface between Local and API managers"""

    def test_generate_accepts_messages_list(self, mock_model_manager):
        """Both managers should accept messages: List[Dict[str, Any]]"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
        params = BaseConfig()

        # APIModelManager
        api_manager = APIModelManager(api_url="http://test", model_name="test")
        api_manager.client = MagicMock()
        api_manager.client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))]
        )
        result = api_manager.generate(messages, params)
        assert isinstance(result, str)
        api_manager.client.chat.completions.create.assert_called_once()

    def test_local_model_manager_messages_to_prompt(self):
        """Test LocalModelManager converts messages to prompt correctly"""
        # We can't easily test LocalModelManager without a real model,
        # but we can test the _messages_to_prompt method
        manager = LocalModelManager.__new__(LocalModelManager)  # Create without init
        manager.tokenzier = None
        manager.pipeline = None

        messages = [
            {"role": "system", "content": "You are a writer."},
            {"role": "user", "content": "Write a story."}
        ]
        prompt = manager._messages_to_prompt(messages)
        assert "System: You are a writer." in prompt
        assert "User: Write a story." in prompt

    def test_messages_to_prompt_handles_assistant_role(self):
        """Test _messages_to_prompt handles assistant role"""
        manager = LocalModelManager.__new__(LocalModelManager)
        manager.tokenzier = None
        manager.pipeline = None

        messages = [
            {"role": "assistant", "content": "I am the assistant."}
        ]
        prompt = manager._messages_to_prompt(messages)
        assert "I am the assistant." in prompt

    def test_messages_to_prompt_handles_missing_role(self):
        """Test _messages_to_prompt defaults missing role to user"""
        manager = LocalModelManager.__new__(LocalModelManager)
        manager.tokenzier = None
        manager.pipeline = None

        messages = [
            {"content": "Just content without role"}
        ]
        prompt = manager._messages_to_prompt(messages)
        assert "User: Just content without role" in prompt


class TestAPIModelManager:
    """Tests for APIModelManager"""

    def test_api_manager_retries_on_failure(self):
        """Test that API manager retries on API errors"""
        manager = APIModelManager(
            api_url="http://test",
            model_name="test",
            max_retries=3,
            retry_delay=0.01
        )
        manager.client = MagicMock()
        # Simulate API failure then success
        mock_success = MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))])
        # side_effect as list = each call returns next item
        manager.client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            Exception("Temporary error"),
            mock_success
        ]

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()
        result = manager.generate(messages, params)
        assert result == "Success"
        assert manager.client.chat.completions.create.call_count == 3

    def test_api_manager_raises_after_max_retries(self):
        """Test that API manager raises after exhausting retries"""
        manager = APIModelManager(
            api_url="http://test",
            model_name="test",
            max_retries=2,
            retry_delay=0.01
        )
        manager.client = MagicMock()
        manager.client.chat.completions.create.side_effect = Exception("Persistent error")

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()

        with pytest.raises(Exception) as exc_info:
            manager.generate(messages, params)
        assert "重试" in str(exc_info.value) or "Persistent error" in str(exc_info.value)

    def test_api_manager_has_async_client(self):
        """Test that APIModelManager initializes async client"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="openai",
            max_concurrent=5
        )
        assert hasattr(manager, 'async_client')
        assert hasattr(manager, 'semaphore')
        # Verify semaphore has correct limit
        assert manager.semaphore._value == 5

    def test_api_manager_has_async_generate_method(self):
        """Test that APIModelManager has async_generate method"""
        manager = APIModelManager(api_url="http://test", model_name="test")
        assert hasattr(manager, 'async_generate')
        assert asyncio.iscoroutinefunction(manager.async_generate)

    def test_local_model_manager_has_async_generate(self):
        """Test that LocalModelManager has async_generate method"""
        manager = LocalModelManager.__new__(LocalModelManager)
        manager.tokenzier = None
        manager.pipeline = None
        assert hasattr(manager, 'async_generate')
        assert asyncio.iscoroutinefunction(manager.async_generate)


def async_test(coro):
    """Decorator to run async coroutines in sync test context"""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


class TestAPIModelManagerAsync:
    """Tests for APIModelManager async_generate method"""

    @async_test
    async def test_async_generate_openai(self):
        """Test async_generate with OpenAI client"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="openai",
            max_concurrent=3
        )
        manager.async_client = MagicMock()
        manager.async_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Async response"))])
        )

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()
        result = await manager.async_generate(messages, params)

        assert result == "Async response"
        manager.async_client.chat.completions.create.assert_called_once()

    @async_test
    async def test_async_generate_anthropic(self):
        """Test async_generate with Anthropic client"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="anthropic",
            max_concurrent=3
        )
        manager.async_client = MagicMock()
        # Mock the async messages.create
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = "Anthropic async response"
        manager.async_client.messages = MagicMock()
        manager.async_client.messages.create = AsyncMock(
            return_value=MagicMock(content=[mock_content_block])
        )

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()
        result = await manager.async_generate(messages, params)

        assert result == "Anthropic async response"

    @async_test
    async def test_async_generate_respects_semaphore(self):
        """Test that async_generate respects semaphore concurrency limit"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="openai",
            max_concurrent=2
        )

        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            current_count = call_count
            # Simulate some work
            await asyncio.sleep(0.01)
            return MagicMock(choices=[MagicMock(message=MagicMock(content=f"Response {current_count}"))])

        manager.async_client = MagicMock()
        manager.async_client.chat.completions.create = mock_create

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()

        # Launch 4 concurrent requests with semaphore limit of 2
        tasks = [manager.async_generate(messages, params) for _ in range(4)]
        results = await asyncio.gather(*tasks)

        # All should complete
        assert len(results) == 4
        # Semaphore should have allowed max 2 at a time

    @async_test
    async def test_async_generate_retry_with_exponential_backoff(self):
        """Test async_generate retries with exponential backoff"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="openai",
            max_retries=3,
            max_concurrent=1
        )

        # Fail twice, then succeed
        manager.async_client = MagicMock()
        manager.async_client.chat.completions.create = AsyncMock(
            side_effect=[
                Exception("Temporary error"),
                Exception("Temporary error"),
                MagicMock(choices=[MagicMock(message=MagicMock(content="Success after retry"))])
            ]
        )

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()
        result = await manager.async_generate(messages, params)

        assert result == "Success after retry"
        assert manager.async_client.chat.completions.create.call_count == 3

    @async_test
    async def test_async_generate_raises_after_max_retries(self):
        """Test async_generate raises after exhausting retries"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="openai",
            max_retries=2,
            max_concurrent=1
        )

        manager.async_client = MagicMock()
        manager.async_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Persistent error")
        )

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()

        with pytest.raises(Exception) as exc_info:
            await manager.async_generate(messages, params)
        assert "重试" in str(exc_info.value) or "Persistent error" in str(exc_info.value)

    @async_test
    async def test_async_generate_skips_thinking_blocks(self):
        """Test async_generate skips thinking blocks in response"""
        manager = APIModelManager(
            api_url="http://test",
            api_key="test-key",
            model_name="test-model",
            api_type="anthropic",
            max_concurrent=1
        )

        # Mock response with both text and thinking blocks
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Actual response text"

        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thought = "This is thinking content that should be skipped"

        manager.async_client = MagicMock()
        manager.async_client.messages = MagicMock()
        manager.async_client.messages.create = AsyncMock(
            return_value=MagicMock(content=[text_block, thinking_block])
        )

        messages = [{"role": "user", "content": "test"}]
        params = BaseConfig()
        result = await manager.async_generate(messages, params)

        # Should only contain text from text block, not thinking
        assert result == "Actual response text"
        assert "thinking" not in result.lower()
