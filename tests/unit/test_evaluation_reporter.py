"""
Unit tests for src/evaluation_reporter.py
"""
import pytest
from src.evaluation_reporter import EvaluationReporter
from src.model import QualityEvaluation, FeedbackItem


class TestEvaluationReporter:
    """Tests for EvaluationReporter"""

    def test_generate_evaluation_report(self, sample_quality_evaluation):
        """Test basic report generation"""
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(
            sample_quality_evaluation,
            chapter_info={"chapter_index": 0, "title": "第一章"}
        )
        assert "report_metadata" in report
        assert "evaluation_summary" in report
        assert "detailed_metrics" in report

    def test_report_text_format_no_keyerror(self):
        """Regression test: text format should not reference non-existent keys"""
        evaluation = QualityEvaluation(
            score=7,
            passes=True,
            length_check=True,
            plot_score=7,
            character_score=7,
            style_score=7,
            pacing_score=6
        )
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(evaluation, {})

        # This should not raise KeyError
        text_output = reporter.export_report(report, format_type="text")
        assert "扩展维度" not in text_output  # Bug was referencing extended_dimensions

    def test_export_report_json(self, sample_quality_evaluation):
        """Test JSON export format"""
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(sample_quality_evaluation, {})
        json_output = reporter.export_report(report, format_type="json")
        assert "{" in json_output
        assert "evaluation_summary" in json_output

    def test_export_report_text(self, sample_quality_evaluation):
        """Test text export format"""
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(sample_quality_evaluation, {})
        text_output = reporter.export_report(report, format_type="text")
        assert "评测摘要" in text_output
        assert "质量评测报告" in text_output

    def test_quality_assessment_levels(self):
        """Test quality level assessment based on score"""
        reporter = EvaluationReporter()

        # Excellent
        eval_8 = QualityEvaluation(score=8, passes=True, length_check=True)
        report = reporter.generate_evaluation_report(eval_8, {})
        assert report["quality_assessment"]["quality_level"] == "优秀"

        # Good
        eval_6 = QualityEvaluation(score=6, passes=True, length_check=True)
        report = reporter.generate_evaluation_report(eval_6, {})
        assert report["quality_assessment"]["quality_level"] == "良好"

        # Average
        eval_4 = QualityEvaluation(score=4, passes=False, length_check=True)
        report = reporter.generate_evaluation_report(eval_4, {})
        assert report["quality_assessment"]["quality_level"] == "一般"

        # Poor
        eval_3 = QualityEvaluation(score=3, passes=False, length_check=False)
        report = reporter.generate_evaluation_report(eval_3, {})
        assert report["quality_assessment"]["quality_level"] == "较差"

    def test_next_steps_when_passes(self):
        """Test next steps when evaluation passes"""
        evaluation = QualityEvaluation(score=8, passes=True, length_check=True)
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(evaluation, {})
        assert "进入下一环节" in report["quality_assessment"]["next_steps"][0]

    def test_next_steps_when_fails_with_high_priority(self):
        """Test next steps when evaluation fails with high priority issues"""
        evaluation = QualityEvaluation(
            score=4,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="问题", suggestion="建议")
            ]
        )
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(evaluation, {})
        next_steps = report["quality_assessment"]["next_steps"]
        assert "修订" in next_steps[0]
        assert "高优先级" in next_steps[1]

    def test_feedback_analysis_statistics(self):
        """Test feedback analysis generates correct statistics"""
        evaluation = QualityEvaluation(
            score=5,
            passes=False,
            length_check=True,
            feedback_items=[
                FeedbackItem(category="plot", priority="high", issue="问题1", suggestion="建议1"),
                FeedbackItem(category="plot", priority="medium", issue="问题2", suggestion="建议2"),
                FeedbackItem(category="character", priority="low", issue="问题3", suggestion="建议3"),
            ]
        )
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(evaluation, {})
        feedback_analysis = report["feedback_analysis"]
        assert feedback_analysis["total_issues"] == 3
        assert feedback_analysis["issue_distribution"]["plot"] == 2
        assert feedback_analysis["issue_distribution"]["character"] == 1
        assert feedback_analysis["priority_breakdown"]["high"] == 1
        assert len(feedback_analysis["critical_issues"]) == 1

    def test_improvement_recommendations(self):
        """Test improvement recommendations generation"""
        evaluation = QualityEvaluation(
            score=4,
            passes=False,
            length_check=True,
            plot_score=4,
            character_score=6
        )
        reporter = EvaluationReporter()
        report = reporter.generate_evaluation_report(evaluation, {})
        recommendations = report["improvement_recommendations"]
        assert len(recommendations) > 0
        # Should have recommendations for low plot score
        plot_recs = [r for r in recommendations if r["category"] == "plot"]
        assert len(plot_recs) > 0
