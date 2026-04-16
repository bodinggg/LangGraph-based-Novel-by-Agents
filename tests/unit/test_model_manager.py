"""
Unit tests for src/model_manager.py
"""
import pytest
from unittest.mock import MagicMock, patch
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
        manager.client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            Exception("Temporary error"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))])
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
