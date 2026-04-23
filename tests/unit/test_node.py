"""
Tests for src/node.py - TDD RED phase
"""
import pytest
from unittest.mock import MagicMock, patch
import json

from src.node import (
    validate_outline_node,
    validate_characters_node,
    accept_chapter_node,
    validate_master_outline_node,
    validate_volume_outline_node,
    validate_chapter_node,
    validate_evaluate_node,
    validate_entities_node,
    check_outline_node,
    check_characters_node,
    check_chapter_node,
    check_evaluation_node,
    check_entities_node,
    check_chapter_completion_node,
    accept_outline_node,
    check_outline_completion_node,
    volume2character,
    evaluation_to_chapter_node,
)
from src.state import NovelState
from src.model import (
    NovelOutline,
    ChapterOutline,
    Character,
    ChapterContent,
    QualityEvaluation,
    FeedbackItem,
    VolumeOutline,
    EntityContent
)
from src.storage import NovelStorage


@pytest.fixture
def mock_novel_storage():
    """Create a mock NovelStorage with valid data"""
    storage = MagicMock(spec=NovelStorage)

    outline = NovelOutline(
        title="测试小说",
        genre="玄幻",
        theme="测试主题",
        setting="测试世界观",
        plot_summary="测试情节概要",
        master_outline=[
            VolumeOutline(
                title="第一卷",
                chapters_range="1-10",
                theme="起始",
                key_turning_points=["转折点1"]
            )
        ],
        chapters=[
            ChapterOutline(
                title="第一章 测试章节",
                summary="这是测试章节的摘要",
                key_events=["事件1", "事件2"],
                characters_involved=["角色A", "角色B"],
                setting="测试场景"
            )
        ],
        characters=["角色A", "角色B"]
    )
    storage.load_outline.return_value = outline

    characters = [
        Character(
            name="角色A",
            background="测试背景",
            personality="开朗",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="成长弧线"
        )
    ]
    storage.load_characters.return_value = characters

    storage.load_chapter.return_value = ChapterContent(
        title="第一章 测试章节",
        content="测试内容"
    )

    return storage


@pytest.fixture
def valid_outline_state(mock_novel_storage):
    """Create a NovelState with valid outline data"""
    return NovelState(
        novel_storage=mock_novel_storage,
        user_intent="创作一个玄幻小说",
        min_chapters=10,
        attempt=0,
        max_attempts=10,
        raw_outline=json.dumps({
            "title": "测试小说",
            "genre": "玄幻",
            "theme": "测试主题",
            "setting": "测试世界观",
            "plot_summary": "测试情节概要",
            "chapters": [
                {
                    "title": "第一章 测试章节",
                    "summary": "这是测试章节的摘要",
                    "key_events": ["事件1", "事件2"],
                    "characters_involved": ["角色A", "角色B"],
                    "setting": "测试场景"
                }
            ] * 10,  # 10 chapters to meet min_chapters
            "characters": ["角色A", "角色B"]
        }),
        validated_outline=None,
        outline_validated_error=None
    )


@pytest.fixture
def valid_characters_state(mock_novel_storage):
    """Create a NovelState with valid characters data"""
    return NovelState(
        novel_storage=mock_novel_storage,
        user_intent="创作一个玄幻小说",
        min_chapters=10,
        attempt=0,
        max_attempts=10,
        row_characters=json.dumps([
            {
                "name": "角色A",
                "background": "测试背景",
                "personality": "开朗",
                "goals": ["目标1"],
                "conflicts": ["冲突1"],
                "arc": "成长弧线"
            },
            {
                "name": "角色B",
                "background": "测试背景2",
                "personality": "沉稳",
                "goals": ["目标2"],
                "conflicts": ["冲突2"],
                "arc": "转变弧线"
            }
        ]),
        validated_characters=None,
        characters_validated_error=None
    )


@pytest.fixture
def valid_chapter_state(mock_novel_storage):
    """Create a NovelState with valid chapter data"""
    return NovelState(
        novel_storage=mock_novel_storage,
        user_intent="创作一个玄幻小说",
        min_chapters=10,
        attempt=0,
        max_attempts=10,
        current_chapter_index=0,
        raw_current_chapter=json.dumps({
            "title": "第一章 测试章节",
            "content": "这是测试章节的内容"
        }),
        validated_chapter_draft=None,
        current_chapter_validated_error=None
    )


@pytest.fixture
def valid_evaluation_state(mock_novel_storage):
    """Create a NovelState with valid evaluation data"""
    return NovelState(
        novel_storage=mock_novel_storage,
        user_intent="创作一个玄幻小说",
        min_chapters=10,
        attempt=0,
        max_attempts=10,
        current_chapter_index=0,
        raw_chapter_evaluation=json.dumps({
            "score": 7,
            "passes": True,
            "length_check": True,
            "feedback_items": [],
            "overall_feedback": "测试反馈"
        }),
        validated_evaluation=None,
        evaluation_validated_error=None
    )


class TestValidateOutlineNode:
    """Test validate_outline_node function"""

    def test_validate_outline_node_success(self, valid_outline_state, mock_novel_storage):
        """Test successful outline validation"""
        result = validate_outline_node(valid_outline_state)

        assert result is not None
        assert "validated_outline" in result
        assert "outline_validated_error" in result
        assert result["outline_validated_error"] is None

    def test_validate_outline_node_invalid_json(self, valid_outline_state):
        """Test outline validation with invalid JSON"""
        valid_outline_state.raw_outline = "not valid json"

        result = validate_outline_node(valid_outline_state)

        assert result is not None
        assert result["outline_validated_error"] is not None
        assert "JSON" in result["outline_validated_error"] or "json" in result["outline_validated_error"].lower()

    def test_validate_outline_node_missing_chapters(self, valid_outline_state):
        """Test outline validation with insufficient chapters"""
        invalid_outline = json.dumps({
            "title": "测试小说",
            "genre": "玄幻",
            "theme": "测试主题",
            "setting": "测试世界观",
            "plot_summary": "测试情节概要",
            "chapters": [{"title": "第一章", "summary": "test", "key_events": [], "characters_involved": [], "setting": "test"}],
            "characters": ["角色A"]
        })
        valid_outline_state.raw_outline = invalid_outline

        result = validate_outline_node(valid_outline_state)

        assert result is not None
        assert result["outline_validated_error"] is not None


class TestValidateCharactersNode:
    """Test validate_characters_node function"""

    def test_validate_characters_node_success(self, valid_characters_state, mock_novel_storage):
        """Test successful characters validation"""
        result = validate_characters_node(valid_characters_state)

        assert result is not None
        assert "validated_characters" in result
        assert "characters_validated_error" in result
        assert result["characters_validated_error"] is None

    def test_validate_characters_node_invalid_json(self, valid_characters_state):
        """Test characters validation with invalid JSON"""
        valid_characters_state.row_characters = "not valid json"

        result = validate_characters_node(valid_characters_state)

        assert result is not None
        assert result["characters_validated_error"] is not None


class TestAcceptChapterNode:
    """Test accept_chapter_node function"""

    def test_accept_chapter_node_success(self, valid_chapter_state, mock_novel_storage):
        """Test successful chapter acceptance"""
        valid_chapter_state.validated_chapter_draft = ChapterContent(
            title="第一章 测试章节",
            content="这是测试章节的内容"
        )

        result = accept_chapter_node(valid_chapter_state)

        assert result is not None
        assert "current_chapter_index" in result
        assert result["current_chapter_index"] == 1  # Should increment


class TestCheckOutlineNode:
    """Test check_outline_node function"""

    def test_check_outline_node_success(self, valid_outline_state):
        """Test check when outline validation is successful"""
        valid_outline_state.outline_validated_error = None

        result = check_outline_node(valid_outline_state)

        assert result == "success"

    def test_check_outline_node_retry(self, valid_outline_state):
        """Test check when retry is needed"""
        valid_outline_state.outline_validated_error = "Some error"
        valid_outline_state.attempt = 0

        result = check_outline_node(valid_outline_state)

        assert result == "retry"

    def test_check_outline_node_failure(self, valid_outline_state):
        """Test check when max attempts reached"""
        valid_outline_state.outline_validated_error = "Some error"
        valid_outline_state.attempt = 10  # >= max_attempts

        result = check_outline_node(valid_outline_state)

        assert result == "failure"


class TestCheckCharactersNode:
    """Test check_characters_node function"""

    def test_check_characters_node_success(self, valid_characters_state):
        """Test check when characters validation is successful"""
        valid_characters_state.characters_validated_error = None

        result = check_characters_node(valid_characters_state)

        assert result == "success"

    def test_check_characters_node_retry(self, valid_characters_state):
        """Test check when retry is needed"""
        valid_characters_state.characters_validated_error = "Some error"
        valid_characters_state.attempt = 0

        result = check_characters_node(valid_characters_state)

        assert result == "retry"


class TestCheckChapterNode:
    """Test check_chapter_node function"""

    def test_check_chapter_node_success(self, valid_chapter_state):
        """Test check when chapter validation is successful"""
        valid_chapter_state.current_chapter_validated_error = None

        result = check_chapter_node(valid_chapter_state)

        assert result == "success"

    def test_check_chapter_node_retry(self, valid_chapter_state):
        """Test check when retry is needed"""
        valid_chapter_state.current_chapter_validated_error = "Some error"
        valid_chapter_state.attempt = 0

        result = check_chapter_node(valid_chapter_state)

        assert result == "retry"


class TestCheckChapterCompletionNode:
    """Test check_chapter_completion_node function"""

    def test_check_chapter_completion_continue(self, mock_novel_storage):
        """Test check when more chapters remain"""
        state = NovelState(
            novel_storage=mock_novel_storage,
            user_intent="test",
            current_chapter_index=0,
            attempt=0,
            max_attempts=10
        )

        result = check_chapter_completion_node(state)

        assert result == "continue"

    def test_check_chapter_completion_complete(self, mock_novel_storage):
        """Test check when all chapters are done"""
        state = NovelState(
            novel_storage=mock_novel_storage,
            user_intent="test",
            current_chapter_index=1,  # Equal to total chapters
            attempt=0,
            max_attempts=10
        )

        result = check_chapter_completion_node(state)

        assert result == "complete"


class TestValidateMasterOutlineNode:
    """Test validate_master_outline_node function"""

    def test_validate_master_outline_node_success(self, mock_novel_storage):
        """Test successful master outline validation"""
        state = NovelState(
            novel_storage=mock_novel_storage,
            user_intent="test",
            min_chapters=10,
            attempt=0,
            max_attempts=10,
            raw_master_outline=json.dumps({
                "title": "测试小说",
                "genre": "玄幻",
                "theme": "测试主题",
                "setting": "测试世界观",
                "plot_summary": "测试情节概要",
                "master_outline": [
                    {
                        "title": "第一卷",
                        "chapters_range": "1-10",
                        "theme": "起始",
                        "key_turning_points": ["转折点1"]
                    }
                ],
                "chapters": [],
                "characters": ["角色A"]
            })
        )

        result = validate_master_outline_node(state)

        assert result is not None
        assert "validated_outline" in result
        assert result["outline_validated_error"] is None

    def test_validate_master_outline_node_insufficient_chapters(self, mock_novel_storage):
        """Test master outline validation with insufficient total chapters"""
        state = NovelState(
            novel_storage=mock_novel_storage,
            user_intent="test",
            min_chapters=100,  # Require 100 chapters
            attempt=0,
            max_attempts=10,
            raw_master_outline=json.dumps({
                "title": "测试小说",
                "genre": "玄幻",
                "theme": "测试主题",
                "setting": "测试世界观",
                "plot_summary": "测试情节概要",
                "master_outline": [
                    {
                        "title": "第一卷",
                        "chapters_range": "1-5",  # Only 5 chapters
                        "theme": "起始",
                        "key_turning_points": ["转折点1"]
                    }
                ],
                "chapters": [],
                "characters": ["角色A"]
            })
        )

        result = validate_master_outline_node(state)

        assert result is not None
        assert result["outline_validated_error"] is not None
