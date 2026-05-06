"""
PlotThreadChecker - 检查伏笔是否回收

检查章节中之前埋下的伏笔是否被合理回收。
"""
import logging
from typing import Dict, Any, List

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import SubAgentReport, CheckCategory

logger = logging.getLogger(__name__)


class PlotThreadChecker(BaseSubAgent):
    """情节线/伏笔检查器"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "PlotThreadChecker")

    async def check(self, chapter: str, context: Dict[str, Any]) -> SubAgentReport:
        """
        检查伏笔回收情况

        1. 检查之前埋下的伏笔是否在预期章节范围内回收
        2. 检查新埋下的伏笔是否有预期回收时间
        3. 检查伏笔回收是否合理（不能太突兀）
        """
        chapter_index = context.get("chapter_index", 0)

        # 构建 LLM 分析用的提示
        system_prompt = """你是一位专业的伏笔审查专家。请分析小说章节中的伏笔回收情况。

请检查：
1. 逾期伏笔：之前埋下的伏笔是否在预期章节范围内已回收
2. 逾期预警：超出预期范围仍未回收的伏笔
3. 新伏笔：章节中新埋下的伏笔是否有关键词和预期回收时间
4. 回收合理性：伏笔回收是否自然合理，不能太突兀

请以 JSON 格式输出：
- updates: 伏笔回收更新列表，包含 thread_id、action、chapter
- issues: 发现的问题列表
- reasoning: 分析理由"""

        user_prompt = f"""请分析以下章节的伏笔回收情况：

【章节内容】
{chapter}

【未解决的伏笔列表】
{context.get('unresolved_plot_threads', [])}

【章节索引】
{chapter_index}

请判断：
1. 哪些伏笔在本章被回收了
2. 哪些伏笔已经逾期未回收
3. 是否有新伏笔被埋下"""

        # 调用 LLM 进行分析
        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            chapter_index=chapter_index,
            require_json=True
        )

        # 解析 LLM 响应
        updates = []
        issues = []
        reasoning = "LLM 伏笔分析完成"

        try:
            import json as json_module
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            parsed = json_module.loads(response_clean)
            updates = parsed.get("updates", [])
            issues = parsed.get("issues", [])
            reasoning = parsed.get("reasoning", "LLM 分析完成")
        except Exception as e:
            logger.warning(f"LLM 响应解析失败: {e}")
            if "正常" in response or "没有" in response:
                issues = []
            else:
                issues.append({
                    "type": "plot_thread",
                    "issue": f"LLM 分析响应解析失败",
                    "suggestion": "请人工检查伏笔状态"
                })

        # 补充：基于规则的伏笔检查
        unresolved = context.get("unresolved_plot_threads", [])
        for thread in unresolved:
            # 使用 Pydantic 属性访问，不再使用 .get()
            thread_id = thread.id
            expected_range = thread.expected_payoff_range or ""

            if expected_range:
                try:
                    parts = expected_range.split("-")
                    if len(parts) == 2:
                        min_ch = int(parts[0].strip())
                        max_ch = int(parts[1].strip())

                        if chapter_index > max_ch:
                            # 逾期未回收的伏笔
                            overdue = True
                            for issue in issues:
                                if issue.get("thread_id") == thread_id:
                                    overdue = False
                                    break
                            if overdue:
                                issues.append({
                                    "type": "overdue_plot_thread",
                                    "thread_id": thread_id,
                                    "issue": f"伏笔预期在第 {min_ch}-{max_ch} 章回收，但当前已是第 {chapter_index} 章",
                                    "suggestion": "考虑在本章或下章回收该伏笔"
                                })
                except (ValueError, IndexError):
                    pass

        return self._create_report(
            category=CheckCategory.PLOT_THREAD,
            issues=issues,
            updates=updates,
            reasoning=reasoning,
            confidence=0.85
        )

    def _check_payoff(self, chapter: str, thread) -> bool:
        """检查章节是否回收了指定伏笔"""
        # thread 可能是 Pydantic 对象或 dict，使用 getattr 处理两种情况
        thread_keywords = getattr(thread, 'foreshadow_keywords', []) or []
        if not thread_keywords:
            # 如果没有关键词，检查是否有与 thread 名称相关的描述
            thread_name = getattr(thread, 'name', '') or ''
            return thread_name in chapter

        # 检查关键词是否出现
        for keyword in thread_keywords:
            if keyword in chapter:
                return True

        return False