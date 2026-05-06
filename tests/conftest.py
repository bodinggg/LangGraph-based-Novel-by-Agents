"""
Shared pytest fixtures for testing
"""
import pytest
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from src.model import NovelOutline, ChapterOutline, Character, QualityEvaluation, FeedbackItem
from src.model import PlotThread, CharacterArc, CharacterArcStage, WorldState, StoryBibleContent
from src.storage import NovelStorage
from src.core.state_manager import StateManager
from src.thinking_logger import create_disabled_logger


@pytest.fixture
def disable_logging():
    """Disable logging during tests"""
    with patch('src.log_config.get_loggers') as mock_log:
        mock_logger = MagicMock()
        mock_log.return_value = {
            'workflow': mock_logger,
            'node': mock_logger,
            'main': mock_logger,
            'gradio': mock_logger,
            'feedback': mock_logger,
            'specialist': mock_logger,
        }
        yield mock_log


@pytest.fixture
def sample_chapter_outline():
    """Sample chapter outline for testing"""
    return ChapterOutline(
        title="第一章 测试章节",
        summary="这是测试章节的摘要",
        key_events=["事件1", "事件2"],
        characters_involved=["角色A", "角色B"],
        setting="测试场景"
    )


@pytest.fixture
def sample_novel_outline(sample_chapter_outline):
    """Sample novel outline for testing"""
    return NovelOutline(
        title="测试小说",
        genre="玄幻",
        theme="测试主题",
        setting="测试世界观",
        plot_summary="测试情节概要",
        chapters=[sample_chapter_outline],
        characters=["角色A", "角色B"]
    )


@pytest.fixture
def sample_character():
    """Sample character for testing"""
    return Character(
        name="测试角色",
        background="测试背景",
        personality="开朗",
        goals=["目标1", "目标2"],
        conflicts=["冲突1", "冲突2"],
        arc="角色成长弧线"
    )


@pytest.fixture
def sample_quality_evaluation():
    """Sample quality evaluation for testing"""
    return QualityEvaluation(
        score=7,
        passes=True,
        length_check=True,
        plot_score=7,
        character_score=8,
        style_score=7,
        pacing_score=7,
        overall_feedback="测试反馈",
        feedback_items=[
            FeedbackItem(
                category="plot",
                priority="medium",
                issue="测试问题",
                suggestion="测试建议"
            )
        ]
    )


@pytest.fixture
def mock_model_manager():
    """Mock model manager for testing"""
    mock = MagicMock()
    mock.generate.return_value = '{"result": "test output"}'
    return mock


@pytest.fixture
def disabled_thinking_logger():
    """Disabled thinking logger for testing"""
    return create_disabled_logger()


@pytest.fixture
def temp_state_manager():
    """Create a temporary state manager for testing"""
    temp_dir = tempfile.mkdtemp()
    manager = StateManager(storage_dir=temp_dir)
    yield manager
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============== StoryBible Fixtures ==============

@pytest.fixture
def sample_plot_thread():
    """Sample plot thread for testing"""
    return PlotThread(
        id="plot_1",
        name="主情节线",
        status="active",
        setup_chapter=1,
        key_events=["事件1", "事件2"],
        description="测试情节线"
    )


@pytest.fixture
def sample_character_arc():
    """Sample character arc for testing"""
    stage1 = CharacterArcStage(
        stage_name="迷茫",
        chapter_range="1-5",
        emotional_state="失落",
        key_moment="失去亲人"
    )
    stage2 = CharacterArcStage(
        stage_name="成长",
        chapter_range="6-10",
        emotional_state="坚定",
        key_moment="突破自我"
    )
    return CharacterArc(
        name="主角",
        arc_stages=[stage1, stage2],
        current_stage_index=0,
        emotional_state="失落",
        key_moments=["失去亲人"],
        relationships={"配角1": "师徒", "配角2": "竞争对手"}
    )


@pytest.fixture
def sample_world_state():
    """Sample world state for testing"""
    return WorldState(
        chapter_index=1,
        location="王城",
        time="第一年春天",
        active_factions=["王国", "公会"],
        weather="晴朗",
        mood="紧张",
        description="故事开始于王城"
    )


@pytest.fixture
def sample_story_bible(sample_plot_thread, sample_character_arc, sample_world_state):
    """Sample story bible for testing"""
    return StoryBibleContent(
        novel_title="测试小说",
        plot_threads=[sample_plot_thread],
        character_arcs=[sample_character_arc],
        world_states=[sample_world_state]
    )


# ============== Multi-Agent Fixtures ==============

@pytest.fixture
def fresh_blackboard():
    """Create a fresh SharedBlackboard for testing"""
    from src.multi_agent.blackboard import SharedBlackboard
    return SharedBlackboard("测试小说")


@pytest.fixture
def fresh_revision_queue():
    """Create a fresh RevisionQueue for testing"""
    from src.multi_agent.revision_queue import RevisionQueue
    return RevisionQueue(max_size=100)
