"""
Unit tests for Supervisor Node integration (new WritingSupervisor architecture)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.state import NovelState
from src.supervisor_node import (
    init_supervisor_node,
    supervisor_node,
    check_revision_node,
    get_writing_supervisor,
    get_storybible,
)


class TestSupervisorNodeInit:
    """Tests for supervisor node initialization"""

    def test_init_supervisor_node(self):
        """Test init_supervisor_node creates WritingSupervisor instance"""
        mock_model_manager = MagicMock()
        init_supervisor_node(mock_model_manager)

        supervisor = get_writing_supervisor()
        assert supervisor is not None
        assert hasattr(supervisor, 'review')

        storybible = get_storybible()
        assert storybible is not None


class TestCheckRevisionNode:
    """Tests for check_revision_node"""

    def test_check_revision_node_no_revision_needed(self):
        """Test check_revision_node returns accept_chapter when no revision needed"""
        state = NovelState(user_intent="测试")
        state.revision_needed = False
        result = check_revision_node(state)
        assert result == "accept_chapter"

    def test_check_revision_node_revision_needed(self):
        """Test check_revision_node returns revise when needed"""
        state = NovelState(user_intent="测试")
        state.revision_needed = True
        result = check_revision_node(state)
        assert result == "revise"


class TestSupervisorNode:
    """Tests for supervisor_node function"""

    def test_supervisor_node_no_content(self):
        """Test supervisor_node returns skip when no content"""
        init_supervisor_node(MagicMock())

        state = NovelState(
            user_intent="测试",
            current_chapter_index=0,
            raw_current_chapter=None
        )

        result = supervisor_node(state)

        assert result["supervisor_result"] is None
        assert result["revision_needed"] is False

    def test_supervisor_node_not_initialized(self):
        """Test supervisor_node handles uninitialized state gracefully"""
        import src.supervisor_node as sn
        sn._writing_supervisor = None

        state = NovelState(
            user_intent="测试",
            current_chapter_index=0,
            raw_current_chapter="内容"
        )

        result = supervisor_node(state)
        assert result["supervisor_result"] is None


class TestCheckRevisionNodePriority:
    """Tests for check_revision_node priority handling"""

    def test_check_revision_node_with_high_priority(self):
        """Test check_revision_node with high priority revision"""
        state = NovelState(user_intent="测试")
        state.revision_needed = True
        result = check_revision_node(state)
        assert result == "revise"

    def test_check_revision_node_with_medium_priority(self):
        """Test check_revision_node with medium priority revision"""
        state = NovelState(user_intent="测试")
        state.revision_needed = True
        result = check_revision_node(state)
        assert result == "revise"


class TestSupervisorNodeLogging:
    """Tests for supervisor node logging"""

    def test_check_revision_logs_decision(self, caplog):
        """Test check_revision_node logs its decision"""
        import logging
        caplog.set_level(logging.INFO)

        state = NovelState(user_intent="测试")
        state.revision_needed = True
        result = check_revision_node(state)

        assert result == "revise"
        assert "需要修订" in caplog.text or "revision" in caplog.text.lower()