"""
Shared pytest fixtures for testing
"""
import pytest
from unittest.mock import MagicMock, patch
from src.model import NovelOutline, ChapterOutline, Character, QualityEvaluation, FeedbackItem
from src.storage import NovelStorage
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
