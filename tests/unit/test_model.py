"""
Unit tests for src/model.py - Pydantic models
"""
import pytest
from pydantic import ValidationError
from src.model import (
    Character,
    ChapterOutline,
    NovelOutline,
    QualityEvaluation,
    FeedbackItem,
    EntityContent
)


class TestCharacter:
    """Tests for Character model"""

    def test_valid_character(self, sample_character):
        """Test creating a valid character"""
        assert sample_character.name == "测试角色"
        assert sample_character.personality == "开朗"
        assert len(sample_character.goals) == 2

    def test_missing_required_field_raises(self):
        """Test that missing required field raises ValidationError"""
        with pytest.raises(ValidationError):
            Character(name="Test")  # missing background, personality, goals, conflicts, arc

    def test_character_with_all_fields(self):
        """Test character with all required fields"""
        char = Character(
            name="完整角色",
            background="完整背景",
            personality="阴沉",
            goals=["目标1"],
            conflicts=["冲突1"],
            arc="成长弧线"
        )
        assert char.name == "完整角色"
        assert len(char.goals) == 1


class TestChapterOutline:
    """Tests for ChapterOutline model"""

    def test_valid_chapter_outline(self, sample_chapter_outline):
        """Test creating a valid chapter outline"""
        assert sample_chapter_outline.title == "第一章 测试章节"
        assert len(sample_chapter_outline.characters_involved) == 2

    def test_chapter_missing_required_field(self):
        """Test that missing required field raises ValidationError"""
        with pytest.raises(ValidationError):
            ChapterOutline(title="Test")  # missing summary, key_events, characters_involved, setting

    def test_chapter_with_required_fields_only(self):
        """Test chapter with all required fields"""
        chapter = ChapterOutline(
            title="Test",
            summary="Summary",
            key_events=["event1"],
            characters_involved=["char1"],
            setting="setting"
        )
        assert chapter.title == "Test"


class TestNovelOutline:
    """Tests for NovelOutline model"""

    def test_valid_novel_outline(self, sample_novel_outline):
        """Test creating a valid novel outline"""
        assert sample_novel_outline.title == "测试小说"
        assert len(sample_novel_outline.chapters) == 1

    def test_novel_with_multiple_chapters(self, sample_chapter_outline):
        """Test novel with multiple chapters"""
        chapters = [
            sample_chapter_outline,
            ChapterOutline(
                title="第二章",
                summary="Second chapter",
                key_events=["event1"],
                characters_involved=["char1"],
                setting="setting"
            )
        ]
        outline = NovelOutline(
            title="多章节小说",
            genre="奇幻",
            theme="主题",
            setting="世界观",
            plot_summary="概要",
            chapters=chapters,
            characters=["char1"]
        )
        assert len(outline.chapters) == 2

    def test_novel_missing_required_title(self):
        """Test that missing title raises ValidationError"""
        with pytest.raises(ValidationError):
            NovelOutline(
                genre="奇幻",
                theme="主题",
                setting="世界观",
                plot_summary="概要",
                chapters=[],
                characters=[]
            )


class TestQualityEvaluation:
    """Tests for QualityEvaluation model"""

    def test_evaluation_with_feedback_items(self, sample_quality_evaluation):
        """Test evaluation containing feedback items"""
        assert sample_quality_evaluation.passes is True
        assert len(sample_quality_evaluation.feedback_items) == 1

    def test_evaluation_defaults(self):
        """Test default values for optional fields"""
        eval = QualityEvaluation(
            score=5,
            passes=False,
            length_check=False
        )
        assert eval.plot_score is None
        assert eval.character_score is None
        assert eval.feedback_items == []
        assert eval.overall_feedback == ""

    def test_evaluation_with_all_scores(self):
        """Test evaluation with all score fields"""
        eval = QualityEvaluation(
            score=8,
            passes=True,
            length_check=True,
            plot_score=8,
            character_score=8,
            style_score=7,
            pacing_score=8
        )
        assert eval.plot_score == 8
        assert eval.character_score == 8


class TestFeedbackItem:
    """Tests for FeedbackItem model"""

    def test_valid_feedback_item(self):
        """Test creating a valid feedback item"""
        item = FeedbackItem(
            category="plot",
            priority="high",
            issue="情节不连贯",
            suggestion="加强过渡"
        )
        assert item.category == "plot"
        assert item.priority == "high"

    def test_feedback_item_with_optional_location(self):
        """Test feedback item with optional location"""
        item = FeedbackItem(
            category="style",
            priority="medium",
            issue="文笔问题",
            suggestion="改进建议",
            location="段落1"
        )
        assert item.location == "段落1"

    def test_feedback_item_category_literal(self):
        """Test that category must be a valid literal"""
        with pytest.raises(ValidationError):
            FeedbackItem(
                category="invalid_category",  # Must be one of plot, character, style, dialogue, pacing, description, logic
                priority="high",
                issue="问题",
                suggestion="建议"
            )


class TestEntityContent:
    """Tests for EntityContent model"""

    def test_valid_entity_content(self):
        """Test creating entity content"""
        entities = EntityContent(
            characters=["角色A"],
            organizations=["组织A"],
            locations=["城市A"],
            events=["事件1"],
            entities=["实体1"]
        )
        assert len(entities.locations) == 1

    def test_entity_content_with_any_types(self):
        """Test entity content accepts Any types"""
        entities = EntityContent(
            characters={"main": "主角A"},
            organizations=["组织1"],
            locations=["地点1"],
            events="单一事件",
            entities=None
        )
        assert entities.characters == {"main": "主角A"}
        assert entities.entities is None
