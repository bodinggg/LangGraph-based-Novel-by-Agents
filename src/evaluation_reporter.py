"""
评测报告生成器 - 增强项目的智能化评测体系
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from src.model import QualityEvaluation, FeedbackItem


class EvaluationReporter:
    """评测报告生成器 - 生成标准化的评测报告"""
    
    def __init__(self):
        self.report_version = "v1.0"
    
    def generate_evaluation_report(self, evaluation: QualityEvaluation, 
                                 chapter_info: Dict[str, Any]) -> Dict[str, Any]:
        """生成标准化评测报告"""
        
        report = {
            "report_metadata": self._generate_report_metadata(),
            "evaluation_summary": self._generate_evaluation_summary(evaluation),
            "detailed_metrics": self._generate_detailed_metrics(evaluation),
            "feedback_analysis": self._generate_feedback_analysis(evaluation.feedback_items),
            "improvement_recommendations": self._generate_improvement_recommendations(evaluation),
            "chapter_info": chapter_info,
            "quality_assessment": self._generate_quality_assessment(evaluation)
        }
        
        return report

    def save_report(self, report: Dict[str, Any], report_path: str) -> None:
        """保存评测报告"""
        report = self.export_report(report)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
    
    def _generate_report_metadata(self) -> Dict[str, Any]:
        """生成报告元数据"""
        return {
            "report_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "report_version": self.report_version,
            "generation_timestamp": datetime.now().isoformat(),
            "evaluation_standard": "标准化内容质量评测框架 v1.0"
        }
    
    def _generate_evaluation_summary(self, evaluation: QualityEvaluation) -> Dict[str, Any]:
        """生成评测摘要"""
        return {
            "overall_score": evaluation.score,
            "pass_status": evaluation.passes,
            "length_check": evaluation.length_check,
            "overall_feedback": evaluation.overall_feedback,
            "confidence_score": evaluation.confidence_score or 0.8
        }
    
    def _generate_detailed_metrics(self, evaluation: QualityEvaluation) -> Dict[str, Any]:
        """生成详细指标"""
        metrics = {
            "core_dimensions": {
                "plot_quality": evaluation.plot_score or 0,
                "character_consistency": evaluation.character_score or 0,
                "writing_style": evaluation.style_score or 0,
                "pacing_control": evaluation.pacing_score or 0
            },
            "extended_dimensions": {
                "consistency": evaluation.consistency_score or 0,
                "coherence": evaluation.coherence_score or 0,
                "completeness": evaluation.completeness_score or 0,
                "correctness": evaluation.correctness_score or 0
            }
        }
        
        # 计算综合评分
        all_scores = [
            evaluation.plot_score or 0,
            evaluation.character_score or 0, 
            evaluation.style_score or 0,
            evaluation.pacing_score or 0,
            evaluation.consistency_score or 0,
            evaluation.coherence_score or 0,
            evaluation.completeness_score or 0,
            evaluation.correctness_score or 0
        ]
        metrics["composite_score"] = sum(all_scores) / len(all_scores) if all_scores else 0
        
        return metrics
    
    def _generate_feedback_analysis(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """生成反馈分析"""
        if not feedback_items:
            return {"total_issues": 0, "issue_distribution": {}, "priority_breakdown": {}}
        
        # 按类别统计
        category_dist = {}
        priority_dist = {"high": 0, "medium": 0, "low": 0}
        
        for item in feedback_items:
            category_dist[item.category] = category_dist.get(item.category, 0) + 1
            priority_dist[item.priority] = priority_dist.get(item.priority, 0) + 1
        
        return {
            "total_issues": len(feedback_items),
            "issue_distribution": category_dist,
            "priority_breakdown": priority_dist,
            "critical_issues": [item for item in feedback_items if item.priority == "high"]
        }
    
    def _generate_improvement_recommendations(self, evaluation: QualityEvaluation) -> List[Dict[str, Any]]:
        """生成改进建议"""
        recommendations = []
        
        # 基于评分生成建议
        if evaluation.plot_score and evaluation.plot_score < 7:
            recommendations.append({
                "category": "plot",
                "priority": "high" if evaluation.plot_score < 5 else "medium",
                "suggestion": "加强情节逻辑性和冲突设计",
                "action_items": ["检查关键事件是否完整呈现", "确保情节发展符合大纲要求"]
            })
        
        if evaluation.character_score and evaluation.character_score < 7:
            recommendations.append({
                "category": "character", 
                "priority": "high" if evaluation.character_score < 5 else "medium",
                "suggestion": "提升角色表现一致性",
                "action_items": ["检查角色言行是否符合设定", "加强角色互动描写"]
            })
        
        if evaluation.consistency_score and evaluation.consistency_score < 7:
            recommendations.append({
                "category": "consistency",
                "priority": "medium",
                "suggestion": "提高内容前后一致性",
                "action_items": ["检查与前文情节的衔接", "验证角色设定的延续性"]
            })
        
        # 基于反馈项生成具体建议
        for item in evaluation.feedback_items[:3]:  # 取前3个重要反馈
            recommendations.append({
                "category": item.category,
                "priority": item.priority,
                "suggestion": item.suggestion,
                "action_items": [f"针对'{item.issue}'进行改进"]
            })
        
        return recommendations
    
    def _generate_quality_assessment(self, evaluation: QualityEvaluation) -> Dict[str, Any]:
        """生成质量评估"""
        overall_score = evaluation.score
        
        if overall_score >= 8:
            quality_level = "优秀"
            risk_level = "低"
        elif overall_score >= 6:
            quality_level = "良好" 
            risk_level = "中"
        elif overall_score >= 4:
            quality_level = "一般"
            risk_level = "高"
        else:
            quality_level = "较差"
            risk_level = "极高"
        
        return {
            "quality_level": quality_level,
            "risk_assessment": risk_level,
            "acceptance_criteria": "通过" if evaluation.passes else "不通过",
            "next_steps": self._get_next_steps(evaluation)
        }
    
    def _get_next_steps(self, evaluation: QualityEvaluation) -> List[str]:
        """根据评估结果确定下一步行动"""
        if evaluation.passes:
            return ["内容质量达标，可进入下一环节"]
        else:
            steps = ["需要根据反馈进行内容修订"]
            if any(item.priority == "high" for item in evaluation.feedback_items):
                steps.append("优先处理高优先级问题")
            if evaluation.score < 5:
                steps.append("建议进行较大幅度的重写")
            return steps
    
    def export_report(self, report: Dict[str, Any], format_type: str = "json") -> str:
        """导出评测报告"""
        if format_type == "json":
            # 将Pydantic模型转换为字典
            serializable_report = self._make_serializable(report)
            return json.dumps(serializable_report, ensure_ascii=False, indent=2)
        elif format_type == "text":
            return self._format_text_report(report)
        else:
            serializable_report = self._make_serializable(report)
            return json.dumps(serializable_report, ensure_ascii=False, indent=2)
    
    def _make_serializable(self, obj: Any) -> Any:
        """将对象转换为可JSON序列化的格式"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, 'dict'):
            # 处理Pydantic模型
            return self._make_serializable(obj.dict())
        else:
            return obj
    
    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """格式化文本报告"""
        text = "=== 标准化内容质量评测报告 ===\n\n"
        
        # 摘要部分
        summary = report["evaluation_summary"]
        text += f"【评测摘要】\n"
        text += f"综合评分: {summary['overall_score']}/10\n"
        text += f"通过状态: {'通过' if summary['pass_status'] else '不通过'}\n"
        text += f"长度检查: {'符合' if summary['length_check'] else '不符合'}\n"
        text += f"总体评价: {summary['overall_feedback']}\n\n"
        
        # 详细指标
        metrics = report["detailed_metrics"]
        text += f"【详细指标】\n"
        text += f"核心维度: 情节({metrics['core_dimensions']['plot_quality']}) | "
        text += f"角色({metrics['core_dimensions']['character_consistency']}) | "
        text += f"文笔({metrics['core_dimensions']['writing_style']}) | "
        text += f"节奏({metrics['core_dimensions']['pacing_control']})\n"
        text += f"扩展维度: 一致性({metrics['extended_dimensions']['consistency']}) | "
        text += f"连贯性({metrics['extended_dimensions']['coherence']}) | "
        text += f"完整性({metrics['extended_dimensions']['completeness']}) | "
        text += f"正确性({metrics['extended_dimensions']['correctness']})\n"
        text += f"综合评分: {metrics['composite_score']:.1f}/10\n\n"
        
        # 质量评估
        quality = report["quality_assessment"]
        text += f"【质量评估】\n"
        text += f"质量等级: {quality['quality_level']}\n"
        text += f"风险等级: {quality['risk_assessment']}\n"
        text += f"验收标准: {quality['acceptance_criteria']}\n"
        text += f"后续步骤: {'; '.join(quality['next_steps'])}\n\n"
        
        # 改进建议
        recommendations = report["improvement_recommendations"]
        if recommendations:
            text += f"【改进建议】\n"
            for i, rec in enumerate(recommendations, 1):
                text += f"{i}. [{rec['category']}] {rec['suggestion']} (优先级: {rec['priority']})\n"
        
        return text
