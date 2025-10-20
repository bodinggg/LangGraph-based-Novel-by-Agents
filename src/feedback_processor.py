"""
简化的反馈处理器 - 直接使用结构化的QualityEvaluation结果
"""
from typing import List, Optional
from src.model import QualityEvaluation, FeedbackItem, ChapterContent

class ProcessedFeedback:
    """处理后的反馈结果"""
    def __init__(self, evaluation: QualityEvaluation):
        self.evaluation = evaluation
        self.summary = self._generate_summary()
        self.high_priority_items = self._get_high_priority_items()
        self.revision_strategy = self._determine_strategy()
    
    def _generate_summary(self) -> str:
        """生成反馈摘要"""
        if self.evaluation.passes:
            return f"评分{self.evaluation.score}/10，质量达标，无需修改"
        
        if not self.evaluation.feedback_items:
            return f"评分{self.evaluation.score}/10，{self.evaluation.overall_feedback}"
        
        # 按类别统计问题
        category_counts = {}
        for item in self.evaluation.feedback_items:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        # 生成摘要
        category_names = {
            'plot': '情节', 'character': '角色', 'style': '文笔', 
            'dialogue': '对话', 'pacing': '节奏', 'description': '描写', 
            'logic': '逻辑'
        }
        
        summary_parts = [f"评分{self.evaluation.score}/10"]
        for category, count in category_counts.items():
            name = category_names.get(category)
            summary_parts.append(f"{name}问题{count}项")
        
        return "，".join(summary_parts)
    
    def _get_high_priority_items(self) -> List[FeedbackItem]:
        """获取高优先级反馈项"""
        return [item for item in self.evaluation.feedback_items 
                if item.priority == 'high']
    
    def _determine_strategy(self) -> str:
        """确定修改策略"""
        if self.evaluation.passes:
            return "maintain_quality"
        
        if not self.evaluation.feedback_items:
            return "general_improvement"
        
        # 根据主要问题类型确定策略
        categories = [item.category for item in self.evaluation.feedback_items]
        category_counts = {cat: categories.count(cat) for cat in set(categories)}
        main_category = max(category_counts.items(), key=lambda x: x[1])[0]
        
        strategy_map = {
            'plot': 'plot_focused',
            'character': 'character_focused', 
            'style': 'style_focused',
            'dialogue': 'dialogue_focused',
            'pacing': 'pacing_focused',
            'description': 'description_focused',
            'logic': 'logic_focused'
        }
        
        return strategy_map.get(main_category, 'comprehensive_revision')

class FeedbackProcessor:
    """简化的反馈处理器"""
    
    def __init__(self, max_feedback_tokens: int = 800):
        self.max_feedback_tokens = max_feedback_tokens
    
    def process_evaluation(self, evaluation: QualityEvaluation, 
                          current_content: ChapterContent = None,
                          revision_count: int = 0) -> ProcessedFeedback:
        """
        处理结构化的评估结果
        
        Args:
            evaluation: 结构化的质量评估结果
            current_content: 当前章节内容（可选）
            revision_count: 修改次数
            
        Returns:
            ProcessedFeedback: 处理后的反馈
        """
        processed = ProcessedFeedback(evaluation)
        
        # 如果有内容引用需求，添加位置信息
        if current_content and evaluation.feedback_items:
            self._add_content_references(evaluation.feedback_items, current_content)
        
        # 根据修改次数调整策略
        if revision_count >= 3:
            processed.revision_strategy = "comprehensive_rewrite"
        
        return processed
    
    def _add_content_references(self, feedback_items: List[FeedbackItem], 
                               content: ChapterContent):
        """为反馈项添加内容位置引用"""
        paragraphs = content.content.split('\n\n')
        
        for item in feedback_items:
            if not item.location:
                # 简单的关键词匹配找到相关段落
                relevant_para = self._find_relevant_paragraph(item.issue, paragraphs)
                if relevant_para:
                    item.location = f"段落{relevant_para + 1}"
    
    def _find_relevant_paragraph(self, issue_text: str, paragraphs: List[str]) -> Optional[int]:
        """找到与问题相关的段落索引"""
        # 提取关键词
        keywords = [word for word in issue_text.split() if len(word) > 1]
        
        best_match = -1
        best_score = 0
        
        for i, para in enumerate(paragraphs):
            score = sum(1 for keyword in keywords if keyword in para)
            if score > best_score:
                best_score = score
                best_match = i
        
        return best_match if best_match >= 0 and best_score > 0 else None
    
    def generate_revision_prompt_context(self, processed_feedback: ProcessedFeedback) -> str:
        """生成用于修改提示的上下文"""
        if processed_feedback.evaluation.passes:
            return "当前内容质量良好，请保持现有水准。"
        
        context_parts = [processed_feedback.summary]
        
        # 添加具体的修改建议
        if processed_feedback.evaluation.feedback_items:
            context_parts.append("\n具体修改建议：")
            for i, item in enumerate(processed_feedback.evaluation.feedback_items[:5], 1):
                location_info = f"（{item.location}）" if item.location else ""
                context_parts.append(f"{i}. {item.suggestion}{location_info}")
        
        # 添加整体评价
        if processed_feedback.evaluation.overall_feedback:
            context_parts.append(f"\n整体评价：{processed_feedback.evaluation.overall_feedback}")
        
        return "\n".join(context_parts)

class ContentReferencer:
    """内容引用器 - 兼容性保持"""
    
    def __init__(self):
        self.processor = FeedbackProcessor()
    
    def add_content_references(self, processed_feedback: ProcessedFeedback, 
                             content: ChapterContent) -> ProcessedFeedback:
        """为反馈添加内容引用（兼容性方法）"""
        self.processor._add_content_references(
            processed_feedback.evaluation.feedback_items, content
        )
        return processed_feedback
