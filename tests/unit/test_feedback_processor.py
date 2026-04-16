"""
Unit tests for src/feedback_processor.py
"""
import pytest
from src.feedback_processor import ProcessedFeedback, FeedbackProcessor
from src.model import QualityEvaluation, FeedbackItem, ChapterContent


class TestProcessedFeedback:
    """Tests for ProcessedFeedback"""

    def test_generates_summary_for_passing_evaluation(self):
        """Test summary generation when evaluation passes"""
        evaluation = QualityEvaluation(
            score=8,
            passes=True,
            length_check=True
        )
        feedback = ProcessedFeedback(evaluation)
        assert "质量达标" in feedback.summary
        assert feedback.revision_strategy == "maintain_quality"

    def test_determines_expand_strategy_for_length_failure(self):
        """Test that length check failure triggers expand_content strategy"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=False
        )
        feedback = ProcessedFeedback(evaluation)
        assert feedback.revision_strategy == "expand_content"

    def test_identifies_high_priority_items(self):
        """Test that high priority items are correctly identified"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="问题1", suggestion="建议1"),
                FeedbackItem(category="style", priority="medium", issue="问题2", suggestion="建议2"),
            ]
        )
        feedback = ProcessedFeedback(evaluation)
        assert len(feedback.high_priority_items) == 1
        assert feedback.high_priority_items[0].priority == "high"

    def test_determines_plot_focused_strategy(self):
        """Test that plot issues trigger plot_focused strategy"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="情节不连贯", suggestion="加强过渡")
            ]
        )
        feedback = ProcessedFeedback(evaluation)
        assert feedback.revision_strategy == "plot_focused"

    def test_determines_character_focused_strategy(self):
        """Test that character issues trigger character_focused strategy"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="character", priority="medium", issue="角色表现不一致", suggestion="统一风格")
            ]
        )
        feedback = ProcessedFeedback(evaluation)
        assert feedback.revision_strategy == "character_focused"

    def test_fallback_to_targeted_revision_for_unknown_issue(self):
        """Test that style/pacing/logic issues fallback to targeted_revision"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="style", priority="low", issue="文笔问题", suggestion="改进")
            ]
        )
        feedback = ProcessedFeedback(evaluation)
        assert feedback.revision_strategy == "targeted_revision"


class TestFeedbackProcessor:
    """Tests for FeedbackProcessor"""

    def test_process_evaluation_basic(self, sample_quality_evaluation):
        """Test basic evaluation processing"""
        processor = FeedbackProcessor()
        processed = processor.process_evaluation(sample_quality_evaluation)
        assert processed.evaluation == sample_quality_evaluation
        assert processed.revision_strategy == "maintain_quality"

    def test_revision_count_overrides_strategy(self):
        """Test that revision_count >= 3 forces comprehensive_rewrite"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="问题", suggestion="建议")
            ]
        )
        processor = FeedbackProcessor()
        processed = processor.process_evaluation(evaluation, revision_count=3)
        assert processed.revision_strategy == "comprehensive_rewrite"

    def test_generate_revision_prompt_context_for_passing(self):
        """Test prompt context when evaluation passes"""
        evaluation = QualityEvaluation(
            score=8,
            passes=True,
            length_check=True
        )
        processor = FeedbackProcessor()
        processed = processor.process_evaluation(evaluation)
        context = processor.generate_revision_prompt_context(processed)
        assert "质量良好" in context

    def test_generate_revision_prompt_context_with_suggestions(self):
        """Test prompt context includes suggestions when present"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            overall_feedback="需要改进",
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="情节问题", suggestion="加强情节连贯性")
            ]
        )
        processor = FeedbackProcessor()
        processed = processor.process_evaluation(evaluation)
        context = processor.generate_revision_prompt_context(processed)
        assert "加强情节连贯性" in context

    def test_find_relevant_paragraph(self):
        """Test finding relevant paragraph by keyword matching"""
        processor = FeedbackProcessor()
        paragraphs = [
            "这是一个介绍段落。",
            "主角来到城市。",
            "遇到反派发生战斗。",
            "战斗结束后继续前进。"
        ]
        # Issue mentions "反派问题" - keywords are split by whitespace
        # So keywords = ["反派问题"] - "反派" alone won't match if exact phrase needed
        result = processor._find_relevant_paragraph("反派发生战斗", paragraphs)
        # Keywords: ["反派发生战斗"] - this phrase appears in para 2
        assert result == 2

    def test_find_relevant_paragraph_by_single_keyword(self):
        """Test finding paragraph with single matching keyword"""
        processor = FeedbackProcessor()
        paragraphs = [
            "这是一个介绍段落。",
            "主角来到城市。",
            "遇到反派发生战斗。",
            "战斗结束后继续前进。"
        ]
        # Use single keyword that appears in paragraph 2
        result = processor._find_relevant_paragraph("反派", paragraphs)
        assert result == 2

    def test_find_relevant_paragraph_no_match(self):
        """Test when no paragraph matches keywords"""
        processor = FeedbackProcessor()
        paragraphs = ["段落一", "段落二", "段落三"]
        result = processor._find_relevant_paragraph("完全不相关的关键词xyz", paragraphs)
        assert result is None


class TestContentReferencer:
    """Tests for ContentReferencer (compatibility class)"""

    def test_add_content_references(self):
        """Test adding content references to feedback"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="情节问题", suggestion="建议")
            ]
        )
        content = ChapterContent(
            title="测试章节",
            content="第一段内容。\n\n第二段包含情节问题。\n\n第三段内容。"
        )
        from src.feedback_processor import ContentReferencer
        referencer = ContentReferencer()
        processed = ProcessedFeedback(evaluation)
        result = referencer.add_content_references(processed, content)
        assert result.evaluation.feedback_items[0].location is not None
