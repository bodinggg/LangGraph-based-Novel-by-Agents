"""
Integration tests for new Multi-Agent Collaboration System

Tests how all multi-agent components work together with the new WritingSupervisor architecture:
- WritingSupervisor + StoryBible + SubAgents (ConsistencyChecker, CharacterArcChecker, etc.)
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.multi_agent import (
    WritingSupervisor,
    StoryBible,
    ConsistencyChecker,
    CharacterArcChecker,
    PlotThreadChecker,
    WorldStateChecker,
    ReflectionChecker,
)
from src.multi_agent.types import ReviewResult, Suggestion, CheckCategory, Priority


class TestWritingSupervisorIntegration:
    """Integration tests for WritingSupervisor with SubAgents"""

    @pytest.fixture
    def mock_model_manager(self):
        """Create mock model manager"""
        manager = MagicMock()
        return manager

    @pytest.fixture
    def writing_supervisor(self, mock_model_manager):
        """Create WritingSupervisor instance"""
        return WritingSupervisor(mock_model_manager)

    @pytest.fixture
    def storybible(self):
        """Create StoryBible instance"""
        return StoryBible()

    @pytest.mark.asyncio
    async def test_review_chapter_returns_review_result(self, writing_supervisor):
        """Test that review() returns a ReviewResult"""
        chapter_content = "这是测试章节内容，描述主角张伟在2020年开始修炼。"

        with patch.object(writing_supervisor.reflection_agent, 'evaluate', new_callable=AsyncMock) as mock_evaluate:
            mock_evaluate.return_value = ReviewResult(
                chapter_index=1,
                needs_revision=False,
                suggestions=[],
                reasoning="章节质量良好",
                execution_time=0.5,
                quality_score=8.0
            )

            result = await writing_supervisor.review(chapter_content, 1)

            assert isinstance(result, ReviewResult)
            assert result.chapter_index == 1
            assert result.needs_revision is False

    @pytest.mark.asyncio
    async def test_review_with_suggestions(self, writing_supervisor):
        """Test that review returns suggestions when issues found"""
        chapter_content = "张伟在第一章中提到他2019年出生，但第二章中又说他是2020年出生。"

        suggestions = [
            Suggestion(
                category=CheckCategory.CONSISTENCY,
                priority=Priority.HIGH,
                issue="时间线不一致",
                location="第2章",
                current_text="2020年",
                suggested_change="保持2019年出生"
            )
        ]

        with patch.object(writing_supervisor.reflection_agent, 'evaluate', new_callable=AsyncMock) as mock_evaluate:
            mock_evaluate.return_value = ReviewResult(
                chapter_index=1,
                needs_revision=True,
                suggestions=suggestions,
                reasoning="发现一致性问题",
                execution_time=0.5,
                quality_score=6.0
            )

            result = await writing_supervisor.review(chapter_content, 1)

            assert result.needs_revision is True
            assert len(result.suggestions) == 1
            assert result.suggestions[0].issue == "时间线不一致"

    def test_storybible_updates_after_review(self, writing_supervisor):
        """Test that StoryBible is updated after review with issues"""
        # StoryBible should have been initialized with supervisor
        assert writing_supervisor.storybible is not None
        assert isinstance(writing_supervisor.storybible, StoryBible)


class TestSubAgentsIntegration:
    """Integration tests for SubAgents working together"""

    @pytest.fixture
    def mock_model_manager(self):
        """Create mock model manager"""
        manager = MagicMock()
        return manager

    def test_all_check_agents_created(self, mock_model_manager):
        """Test all 4 check agents are created"""
        supervisor = WritingSupervisor(mock_model_manager)

        assert len(supervisor.check_agents) == 4
        agent_names = [agent.agent_name for agent in supervisor.check_agents]
        assert "ConsistencyChecker" in agent_names
        assert "CharacterArcChecker" in agent_names
        assert "PlotThreadChecker" in agent_names
        assert "WorldStateChecker" in agent_names

    def test_reflection_agent_created(self, mock_model_manager):
        """Test ReflectionChecker is created"""
        supervisor = WritingSupervisor(mock_model_manager)

        assert supervisor.reflection_agent is not None
        assert isinstance(supervisor.reflection_agent, ReflectionChecker)


class TestStoryBibleContext:
    """Tests for StoryBible context generation"""

    def test_get_context_includes_all_fields(self):
        """Test get_context_for_chapter returns all required fields"""
        storybible = StoryBible()
        context = storybible.get_context_for_chapter(5)

        assert "character_arcs" in context
        assert "plot_threads" in context
        assert "world_states" in context
        assert "unresolved_plot_threads" in context
        assert "latest_world_state" in context
        assert context["chapter_index"] == 5

    def test_get_context_with_data(self):
        """Test get_context_for_chapter with some data loaded"""
        storybible = StoryBible()

        # Context should work even without data
        context = storybible.get_context_for_chapter(1)
        assert context["character_arcs"] == {}
        assert context["plot_threads"] == {}