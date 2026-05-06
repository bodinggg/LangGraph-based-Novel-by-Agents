"""
Unit tests for WritingSupervisor
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
    ReviewResult,
)
from src.multi_agent.types import CheckCategory, Priority, Suggestion
from src.model import NovelOutline, Character
from src.state import NovelState


class TestWritingSupervisorInit:
    """Tests for WritingSupervisor initialization"""

    def test_init_writing_supervisor(self):
        """Test WritingSupervisor initializes correctly"""
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        assert supervisor.storybible is not None
        assert hasattr(supervisor, 'check_agents')
        assert hasattr(supervisor, 'reflection_agent')
        assert len(supervisor.check_agents) == 4

    def test_init_with_model_manager(self):
        """Test WritingSupervisor with model manager"""
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        for agent in supervisor.check_agents:
            assert agent.model_manager is mock_manager
        assert supervisor.reflection_agent.model_manager is mock_manager


class TestStoryBible:
    """Tests for StoryBible"""

    def test_init_storybible(self):
        """Test StoryBible initializes correctly"""
        storybible = StoryBible()
        assert storybible._character_arcs == {}
        assert storybible._plot_threads == {}
        assert storybible._world_states == []

    def test_get_context_for_chapter(self):
        """Test get_context_for_chapter returns correct structure"""
        storybible = StoryBible()
        context = storybible.get_context_for_chapter(1)

        assert "character_arcs" in context
        assert "plot_threads" in context
        assert "chapter_index" in context
        assert context["chapter_index"] == 1


class TestReviewResult:
    """Tests for ReviewResult"""

    def test_review_result_creation(self):
        """Test creating a ReviewResult"""
        result = ReviewResult(
            chapter_index=1,
            needs_revision=True,
            suggestions=[
                Suggestion(
                    category=CheckCategory.CONSISTENCY,
                    priority=Priority.HIGH,
                    issue="时间线不一致",
                    location="第3段",
                    current_text="他2019年出生",
                    suggested_change="他2020年出生"
                )
            ],
            reasoning="发现时间线问题",
            execution_time=1.5,
            quality_score=7.0
        )

        assert result.chapter_index == 1
        assert result.needs_revision is True
        assert len(result.suggestions) == 1
        assert result.quality_score == 7.0

    def test_review_result_to_dict(self):
        """Test ReviewResult.to_dict() conversion"""
        result = ReviewResult(
            chapter_index=1,
            needs_revision=False,
            suggestions=[],
            reasoning="无需修订",
            execution_time=1.0,
            quality_score=9.0
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["chapter_index"] == 1
        assert result_dict["needs_revision"] is False
        assert result_dict["quality_score"] == 9.0


class TestCheckCategory:
    """Tests for CheckCategory enum"""

    def test_check_category_values(self):
        """Test CheckCategory enum values"""
        assert CheckCategory.CONSISTENCY.value == "consistency"
        assert CheckCategory.CHARACTER_ARC.value == "character_arc"
        assert CheckCategory.PLOT_THREAD.value == "plot_thread"
        assert CheckCategory.WORLD_STATE.value == "world_state"


class TestPriority:
    """Tests for Priority enum"""

    def test_priority_values(self):
        """Test Priority enum values"""
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"


class TestWritingSupervisorInitStoryBible:
    """Tests for WritingSupervisor.init_storybible() method

    RED Phase: These tests define the expected behavior of init_storybible()
    """

    def _create_mock_outline(self):
        """Create a mock NovelOutline for testing"""
        from src.model import NovelOutline, ChapterOutline
        return NovelOutline(
            title="测试小说",
            genre="科幻",
            theme="成长",
            setting="未来都市",
            plot_summary="一个关于成长的故事",
            chapters=[
                ChapterOutline(
                    title="第一章",
                    summary="初始章节",
                    key_events=["事件1", "事件2"],
                    characters_involved=["林远"],
                    setting="未来都市·旧城区"
                ),
                ChapterOutline(
                    title="第二章",
                    summary="发展阶段",
                    key_events=["事件3", "事件4"],
                    characters_involved=["林远", "苏晴"],
                    setting="未来都市·市中心"
                )
            ],
            characters=["林远", "苏晴"]
        )

    def _create_mock_characters(self):
        """Create mock character data for testing

        Note: The Character model uses 'arc: str' not 'character_arc: CharacterArc'.
        This test verifies the init_storybible method handles characters that have
        a character_arc attribute (for backward compatibility or future use).
        """
        from src.model import CharacterArc, CharacterArcStage

        # Create a mock object that has character_arc attribute
        # (as expected by init_storybible implementation)
        class MockCharacterWithArc:
            name = "林远"
            character_arc = CharacterArc(
                name="林远",
                arc_stages=[CharacterArcStage(
                    stage_name="迷茫",
                    chapter_range="1-3",
                    emotional_state="困惑",
                    key_moment="获得能力"
                )],
                current_stage_index=0,
                emotional_state="困惑"
            )

        return [MockCharacterWithArc()]

    def test_init_storybible_method_exists(self):
        """Test that init_storybible method exists on WritingSupervisor"""
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)
        assert hasattr(supervisor, 'init_storybible'), "init_storybible method should exist"
        assert callable(getattr(supervisor, 'init_storybible')), "init_storybible should be callable"

    def test_init_storybible_from_outline(self):
        """Test init_storybible populates StoryBible from outline

        RED: This test should FAIL until we implement init_storybible()
        """
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        outline = self._create_mock_outline()

        # Call init_storybible - should populate storybible with data from outline
        supervisor.init_storybible(outline, characters=None)

        # Verify StoryBible was populated
        assert len(supervisor.storybible._character_arcs) > 0, "Should have character arcs from outline"
        assert len(supervisor.storybible._plot_threads) > 0, "Should have plot threads from outline"

    def test_init_storybible_idempotent(self):
        """Test init_storybible only initializes once

        RED: This test should FAIL until we implement the idempotency check
        """
        from src.model import ChapterOutline
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        outline1 = self._create_mock_outline()
        supervisor.init_storybible(outline1, characters=None)

        # Get the first arc's name
        first_arc_name = list(supervisor.storybible._character_arcs.keys())[0]

        # Try to init again with different data
        outline2 = NovelOutline(
            title="different",
            genre="different",
            theme="different",
            setting="different",
            plot_summary="different",
            chapters=[
                ChapterOutline(
                    title="不同章节",
                    summary="不同摘要",
                    key_events=["不同事件"],
                    characters_involved=["不同角色"],
                    setting="不同地点"
                )
            ],
            characters=["不同角色"]
        )
        supervisor.init_storybible(outline2, characters=None)

        # Should still have the original data, not overwritten
        assert first_arc_name in supervisor.storybible._character_arcs
        assert supervisor.storybible._character_arcs[first_arc_name].name == "林远"

    def test_init_storybible_with_characters(self):
        """Test init_storybible also loads character arcs from Character objects

        RED: This test should FAIL until we implement character arc loading
        """
        mock_manager = MagicMock()
        supervisor = WritingSupervisor(mock_manager)

        outline = self._create_mock_outline()
        characters = self._create_mock_characters()

        supervisor.init_storybible(outline, characters)

        # Should have character arc from the Character object
        assert "林远" in supervisor.storybible._character_arcs
        arc = supervisor.storybible._character_arcs["林远"]
        assert arc.emotional_state == "困惑"


class TestSupervisorNodeStoryBibleInitialization:
    """Tests for StoryBible initialization in supervisor_node

    RED Phase: Tests for the initialization-from-outline when storage is empty
    """

    def test_supervisor_node_initializes_from_outline_when_storage_empty(self):
        """Test supervisor_node initializes StoryBible from outline when story_bible.json is empty

        RED: This test should FAIL until we implement initialization in supervisor_node
        """
        from src.storage import NovelStorage
        import src.supervisor_node as sn

        # Reset global state
        sn._writing_supervisor = None
        sn._storybible = None

        # Create mock storage that returns empty story_bible but has outline/characters
        # Use spec to make it pass isinstance check
        mock_storage = MagicMock(spec=NovelStorage)
        mock_storage.load_story_bible.return_value = None  # No existing story_bible
        mock_storage.load_outline.return_value = NovelOutline(
            title="测试",
            genre="科幻",
            theme="成长",
            setting="未来",
            plot_summary="测试",
            chapters=[],
            characters=["林远"]
        )
        mock_storage.load_characters.return_value = []

        # Create state
        state = NovelState(
            user_intent="测试",
            current_chapter_index=1,
            raw_current_chapter="测试内容",
            novel_storage=mock_storage
        )

        # Initialize
        sn.init_supervisor_node(MagicMock())

        # Call supervisor_node - should trigger initialization
        sn.supervisor_node(state)

        # Verify StoryBible was initialized from outline
        supervisor = sn._writing_supervisor
        assert supervisor is not None
        # Should have character arcs from outline (even without characters file)
        assert len(supervisor.storybible._character_arcs) > 0, "Should initialize from outline"

    def test_storybible_global_synced_with_writing_supervisor(self):
        """Test that _storybible global is synced with _writing_supervisor.storybible

        RED: This test should FAIL until we implement the sync logic
        """
        import src.supervisor_node as sn

        # Reset and initialize
        sn._writing_supervisor = None
        sn._storybible = None

        sn.init_supervisor_node(MagicMock())

        # After init, they should be the same object
        assert sn._storybible is sn._writing_supervisor.storybible, \
            "_storybible should reference the same StoryBible instance as _writing_supervisor.storybible"