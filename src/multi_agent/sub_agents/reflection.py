"""
ReflectionChecker - 综合决策 + 质量评估 + 修改建议

整合 4 个检查型 SubAgent 的结果，给出：
1. 质量评分 (0-10)
2. 是否需要修订
3. 具体修改建议（带位置和原文）
"""
import logging
import time
from typing import Dict, Any, List

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import (
    SubAgentReport, ReviewResult, Suggestion,
    CheckCategory, Priority
)

logger = logging.getLogger(__name__)


class ReflectionChecker(BaseSubAgent):
    """综合评估器 - 整合所有检查结果做最终决策"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "ReflectionChecker")

    async def evaluate(
        self,
        chapter: str,
        chapter_index: int,
        check_results: List[SubAgentReport],
        context: Dict[str, Any]
    ) -> ReviewResult:
        """
        综合所有 SubAgent 的检查结果，给出最终评估

        Args:
            chapter: 章节内容
            chapter_index: 章节索引
            check_results: 4 个检查型 SubAgent 的结果
            context: StoryBible 上下文

        Returns:
            ReviewResult: 包含质量评分、是否需要修订、具体修改建议
        """
        start_time = time.time()

        # 构建 LLM 综合分析用的提示
        system_prompt = """你是一位专业的小说质量评审专家。请综合多个专业审查 Agent 的检查结果，对章节进行最终质量评估。

你将收到：
1. 章节内容摘要
2. 多个专业 Agent 的检查结果（一致性、角色弧线、伏笔、世界状态）
3. 各 Agent 发现的问题列表

请以 JSON 格式输出最终评估：
- quality_score: 质量评分 (0-10)
- needs_revision: 是否需要修订 (true/false)
- suggestions: 具体修改建议列表，每个建议包含 category、priority、issue、location、current_text、suggested_change
- reasoning: 决策理由

评分标准：
- 8.5-10: 优秀，无需修订
- 7.0-8.5: 良好，小幅改进空间
- 6.0-7.0: 合格，明显问题需修改
- <6.0: 不合格，需要大幅修订

【重要】suggestions 数组中的每个对象必须严格使用以下枚举值：
- category: "consistency" | "character_arc" | "plot_thread" | "world_state" | "quality"（必须使用英文小写）
- priority: "high" | "medium" | "low"（必须使用英文小写）
- 不要使用中文、不要使用大写、不要使用其他值"""

        # 收集各 Agent 的检查结果摘要
        agent_results_summary = []
        for report in check_results:
            agent_results_summary.append({
                "agent": report.agent_name,
                "category": report.category.value if hasattr(report.category, 'value') else str(report.category),
                "issues_count": len(report.issues),
                "issues": report.issues,
                "updates_count": len(report.updates),
                "reasoning": report.reasoning,
                "confidence": report.confidence
            })

        user_prompt = f"""请综合以下专业审查 Agent 的检查结果，对章节进行最终评估：

【章节索引】
{chapter_index}

【章节内容摘要】
{chapter[:1500]}...

【专业 Agent 检查结果】
{agent_results_summary}

【上下文信息】
{context}

请综合分析，给出最终的质量评分、是否需要修订、以及具体的修改建议。"""

        # 调用 LLM 进行综合评估
        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            chapter_index=chapter_index,
            require_json=True
        )

        # 解析 LLM 响应
        quality_score = 7.0
        needs_revision = False
        suggestions = []
        reasoning = "LLM 综合评估完成"

        try:
            import json as json_module
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            parsed = json_module.loads(response_clean)
            quality_score = parsed.get("quality_score", 7.0)
            needs_revision = parsed.get("needs_revision", False)
            suggestions_raw = parsed.get("suggestions", [])

            # 转换 suggestions 格式
            for s in suggestions_raw:
                # 映射 LLM 返回的 category 名称到 CheckCategory
                category_str = s.get("category", "quality")
                category = self._map_category(category_str)

                suggestions.append(Suggestion(
                    category=category,
                    priority=Priority(s.get("priority", "medium")),
                    issue=s.get("issue", ""),
                    location=s.get("location", ""),
                    current_text=s.get("current_text", ""),
                    suggested_change=s.get("suggested_change", "")
                ))

            reasoning = parsed.get("reasoning", "LLM 综合评估完成")
        except Exception as e:
            logger.warning(f"LLM 响应解析失败: {e}")
            # 回退到基于规则的方法
            reasoning = f"LLM 解析失败，使用规则评估: {response[:100]}"

        # 如果 LLM 解析失败或没有建议，使用基于规则的方法补充
        if not suggestions:
            all_issues = []
            for report in check_results:
                all_issues.extend(report.issues)

            suggestions = self._generate_suggestions(chapter, all_issues, context)
            reasoning += f"; 补充规则检查: 发现 {len(suggestions)} 个建议"

        # 如果 LLM 没有给出评分，使用规则计算
        if quality_score == 7.0:
            quality_score = self._calculate_quality_score(chapter, [], suggestions)
            needs_revision = len(suggestions) > 0 or quality_score < 7.0

        execution_time = time.time() - start_time

        return ReviewResult(
            chapter_index=chapter_index,
            needs_revision=needs_revision,
            suggestions=suggestions,
            reasoning=reasoning,
            execution_time=execution_time,
            quality_score=quality_score
        )

    def _generate_suggestions(
        self,
        chapter: str,
        issues: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Suggestion]:
        """从问题列表生成具体修改建议"""
        suggestions = []

        # 按优先级分类
        high_priority = [i for i in issues if i.get("type") in ["timeline", "consistency"]]
        medium_priority = [i for i in issues if i.get("type") in ["arc", "plot_thread"]]
        low_priority = [i for i in issues if i.get("type") not in ["timeline", "consistency", "arc", "plot_thread"]]

        # 处理高优先级问题
        for issue in high_priority[:3]:  # 最多 3 个高优先级建议
            location = issue.get("location", "")
            # 尝试获取原文片段
            current_text = self._extract_text_at_location(chapter, location, issue.get("issue", ""))

            suggestions.append(Suggestion(
                category=self._get_category_from_issue(issue),
                priority=Priority.HIGH,
                issue=issue.get("issue", "发现一致性问题"),
                location=location,
                current_text=current_text,
                suggested_change=issue.get("suggestion", "请修正此问题")
            ))

        # 处理中优先级问题
        for issue in medium_priority[:2]:
            location = issue.get("location", "")
            current_text = self._extract_text_at_location(chapter, location, issue.get("issue", ""))

            suggestions.append(Suggestion(
                category=self._get_category_from_issue(issue),
                priority=Priority.MEDIUM,
                issue=issue.get("issue", "需要关注"),
                location=location,
                current_text=current_text,
                suggested_change=issue.get("suggestion", "建议优化")
            ))

        return suggestions

    def _extract_text_at_location(self, chapter: str, location: str, fallback: str) -> str:
        """根据位置信息提取原文片段"""
        if not location:
            return fallback[:100] if len(fallback) > 100 else fallback

        # 解析位置，如 "第5行"
        import re
        line_match = re.search(r'第(\d+)行', location)
        if line_match:
            line_num = int(line_match.group(1))
            lines = chapter.split('\n')
            if 0 < line_num <= len(lines):
                return lines[line_num - 1].strip()[:200]

        return fallback[:100] if len(fallback) > 100 else fallback

    def _get_category_from_issue(self, issue: Dict) -> CheckCategory:
        """根据问题类型确定类别"""
        type_map = {
            "timeline": CheckCategory.CONSISTENCY,
            "consistency": CheckCategory.CONSISTENCY,
            "arc": CheckCategory.CHARACTER_ARC,
            "plot_thread": CheckCategory.PLOT_THREAD,
            "world_state": CheckCategory.WORLD_STATE,
        }
        return type_map.get(issue.get("type", ""), CheckCategory.QUALITY)

    def _map_category(self, category_str: str) -> CheckCategory:
        """将 LLM 返回的 category 字符串映射到 CheckCategory 枚举值

        LLM 可能返回: 'plot', 'character', 'timeline', 'world', 'consistency' 等
        需要映射到: CheckCategory.PLOT_THREAD, CheckCategory.CHARACTER_ARC 等
        """
        category_lower = category_str.lower().strip()

        # 映射表
        mapping = {
            # 时间线/一致性
            "timeline": CheckCategory.CONSISTENCY,
            "time": CheckCategory.CONSISTENCY,
            "consistency": CheckCategory.CONSISTENCY,
            "consistency_check": CheckCategory.CONSISTENCY,

            # 角色弧线
            "character": CheckCategory.CHARACTER_ARC,
            "character_arc": CheckCategory.CHARACTER_ARC,
            "arc": CheckCategory.CHARACTER_ARC,
            "role": CheckCategory.CHARACTER_ARC,

            # 伏笔
            "plot": CheckCategory.PLOT_THREAD,
            "plot_thread": CheckCategory.PLOT_THREAD,
            "foreshadow": CheckCategory.PLOT_THREAD,

            # 世界状态
            "world": CheckCategory.WORLD_STATE,
            "world_state": CheckCategory.WORLD_STATE,
            "setting": CheckCategory.WORLD_STATE,
            "location": CheckCategory.WORLD_STATE,

            # 质量（默认）
            "quality": CheckCategory.QUALITY,
            "style": CheckCategory.QUALITY,
            "writing": CheckCategory.QUALITY,
        }

        return mapping.get(category_lower, CheckCategory.QUALITY)

    def _calculate_quality_score(
        self,
        chapter: str,
        issues: List[Dict[str, Any]],
        suggestions: List[Suggestion]
    ) -> float:
        """计算质量评分 (0-10)"""
        base_score = 8.0

        # 减分项
        high_count = sum(1 for s in suggestions if s.priority == Priority.HIGH)
        medium_count = sum(1 for s in suggestions if s.priority == Priority.MEDIUM)

        # 高优先级问题每个扣 1.5 分
        base_score -= high_count * 1.5
        # 中优先级问题每个扣 0.8 分
        base_score -= medium_count * 0.8

        # 章节过短扣分
        if len(chapter) < 500:
            base_score -= 0.5

        # 章节过长扣分（超过 5000 字）
        if len(chapter) > 5000:
            base_score -= 0.3

        return max(0.0, min(10.0, base_score))

    def _generate_reasoning(
        self,
        chapter_index: int,
        issues: List[Dict[str, Any]],
        suggestions: List[Suggestion],
        quality_score: float
    ) -> str:
        """生成决策理由"""
        parts = [f"第 {chapter_index} 章质量评估"]

        if quality_score >= 8.5:
            parts.append("整体质量良好")
        elif quality_score >= 7.0:
            parts.append("质量合格，有小幅改进空间")
        else:
            parts.append("需要修订")

        high_count = sum(1 for s in suggestions if s.priority == Priority.HIGH)
        if high_count > 0:
            parts.append(f"发现 {high_count} 个高优先级问题需要修正")

        return "; ".join(parts)

    # 兼容 BaseSubAgent 的接口
    async def check(self, chapter: str, context: Dict[str, Any]) -> SubAgentReport:
        """ReflectionChecker 不做单独检查，只是综合决策"""
        return SubAgentReport(
            agent_name=self.agent_name,
            category=CheckCategory.QUALITY,
            issues=[],
            reasoning="ReflectionChecker 综合决策，不单独输出问题",
            confidence=1.0
        )