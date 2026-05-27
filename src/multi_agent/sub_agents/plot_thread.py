"""
PlotThreadChecker - 检查伏笔是否回收

检查章节中之前埋下的伏笔是否被合理回收。
"""
import logging

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import SubAgentReport, CheckCategory

logger = logging.getLogger(__name__)


class PlotThreadChecker(BaseSubAgent):
    """情节线/伏笔检查器"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "PlotThreadChecker")

    async def check(self, chapter: str, context_text: str, chapter_index: int) -> SubAgentReport:
        """
        检查伏笔回收情况

        1. 检查之前埋下的伏笔是否在预期章节范围内回收
        2. 检查新埋下的伏笔是否有预期回收时间
        3. 检查伏笔回收是否合理（不能太突兀）
        """
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

【上下文信息】
{context_text}

请检查伏笔回收、新伏笔埋设、回收合理性，输出 JSON 格式。"""

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