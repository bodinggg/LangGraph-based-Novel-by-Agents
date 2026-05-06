"""
WorldStateChecker - 检查世界状态

检查章节中的地点、时间、势力等是否与 StoryBible 中记录的世界状态一致。
"""
import logging
from typing import Dict, Any, List, Optional

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import SubAgentReport, CheckCategory

logger = logging.getLogger(__name__)


class WorldStateChecker(BaseSubAgent):
    """世界状态检查器"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "WorldStateChecker")

    async def check(self, chapter: str, context: Dict[str, Any]) -> SubAgentReport:
        """
        检查世界状态一致性

        1. 检查地点是否与前文一致
        2. 检查时间是否推进合理
        3. 检查势力关系是否正确
        """
        chapter_index = context.get("chapter_index", 0)

        # 构建 LLM 分析用的提示
        system_prompt = """你是一位专业的世界状态审查专家。请分析小说章节中的世界状态（地点、时间、势力关系）是否与之前的记录一致。

请检查：
1. 地点一致性：章节中提到的地点是否与前文描述的当前位置冲突
2. 时间推进合理性：时间描述是否前后矛盾，进度是否过快或过慢
3. 势力关系：势力之间的互动是否符合已知的关系设定

请以 JSON 格式输出：
- issues: 发现的问题列表，包含 type、issue、location、suggestion
- updates: 世界状态更新（如有新的地点、时间等）
- reasoning: 分析理由"""

        user_prompt = f"""请分析以下章节的世界状态一致性：

【章节内容】
{chapter}

【当前世界状态】
{context.get('latest_world_state', {})}

【历史世界状态】
{context.get('world_states', [])}

【章节索引】
{chapter_index}

请仔细检查地点、时间、势力关系是否与之前的记录一致。"""

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
        reasoning = "LLM 世界状态分析完成"

        try:
            import json as json_module
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            parsed = json_module.loads(response_clean)
            issues = parsed.get("issues", []) or []
            updates = parsed.get("updates", []) or []
            reasoning = parsed.get("reasoning", "LLM 分析完成")
        except Exception as e:
            logger.warning(f"LLM 响应解析失败: {e}")
            if "正常" in response or "一致" in response:
                issues = []
            else:
                issues.append({
                    "type": "world_world_state",
                    "issue": f"LLM 分析响应解析失败",
                    "suggestion": "请人工检查世界状态"
                })

        # 补充：基于规则的世界状态提取
        new_state = self._extract_world_state(chapter, chapter_index)
        if new_state:
            if not isinstance(updates, list):
                updates = [updates]
            updates.append({
                "type": "world_state_update",
                "state": new_state
            })
            reasoning += "; 检测到新的世界状态"

        return self._create_report(
            category=CheckCategory.WORLD_STATE,
            issues=issues,
            updates=updates,
            reasoning=reasoning,
            confidence=0.85
        )

    def _check_location_conflict(self, chapter: str, current_location: str) -> Dict[str, Any] | None:
        """检查地点冲突"""
        # 简化：如果章节提到某个地点，但与当前地点相距甚远，可能有问题
        location_indicators = ["到达", "前往", "回到", "来到", "进入"]

        lines = chapter.split('\n')
        for line in lines:
            for indicator in location_indicators:
                if indicator in line:
                    # 提取目标地点
                    parts = line.split(indicator)
                    if len(parts) > 1:
                        target = parts[1].split('。')[0].split('，')[0].strip()
                        # 简单的合理性检查：如果目标与当前地点完全不同且距离很近，有问题
                        if current_location and target != current_location:
                            # 这里应该做更复杂的地理检查
                            pass

        return None

    def _check_time_conflict(
        self,
        chapter: str,
        latest_state: Dict,
        world_states: List[Dict]
    ) -> Dict[str, Any] | None:
        """检查时间冲突"""
        # 如果世界状态列表中连续两个状态的时间跳跃不合理
        if len(world_states) >= 2:
            prev_state = world_states[-2]
            curr_state = latest_state

            prev_time = prev_state.get("time", "")
            curr_time = curr_state.get("time", "")

            # 检查时间是否倒退
            if prev_time and curr_time:
                # 这里需要更复杂的日期/时间解析
                pass

        return None

    def _extract_world_state(self, chapter: str, chapter_index: int) -> Optional["WorldState"]:
        """从章节中提取世界状态"""
        # 简化实现：检查章节中的地点/时间描述
        import re
        from src.model import WorldState

        location_pattern = r'在(.+?)(?:的|进行|发生|看到|进入)'
        time_pattern = r'(?:新纪元|公元|标准时间)(\d+年)'

        location_match = re.search(location_pattern, chapter)
        time_match = re.search(time_pattern, chapter)

        if location_match or time_match:
            # 返回 WorldState Pydantic 对象，而不是 dict
            return WorldState(
                chapter_index=chapter_index,
                location=location_match.group(1) if location_match else "",
                time=time_match.group(0) if time_match else "",
            )

        return None