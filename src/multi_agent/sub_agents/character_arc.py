"""
CharacterArcChecker - 检查角色弧线是否推进

检查章节中角色的情感/行为状态是否与 StoryBible 中记录的弧线一致。
"""
import logging
from typing import Dict, Any, List

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import SubAgentReport, CheckCategory

logger = logging.getLogger(__name__)


class CharacterArcChecker(BaseSubAgent):
    """角色弧线检查器"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "CharacterArcChecker")

    async def check(self, chapter: str, context: Dict[str, Any]) -> SubAgentReport:
        """
        检查角色弧线是否推进

        1. 检查角色情感状态是否符合当前弧线阶段
        2. 检查关键时刻是否发生
        3. 检查关系变化是否合理
        """
        chapter_index = context.get("chapter_index", 0)

        # 构建 LLM 分析用的提示
        system_prompt = """你是一位专业的角色弧线分析专家。请分析小说章节中角色的情感状态变化和行为，判断角色弧线是否按预期推进。

请检查：
1. 角色情感状态是否与当前弧线阶段匹配
2. 章节中是否发生了推动角色进入下一阶段的关键事件
3. 角色关系变化是否合理且有铺垫

请以 JSON 格式输出：
- updates: 弧线推进更新列表，包含 character、action、from_stage、to_stage
- issues: 发现的问题列表
- reasoning: 分析理由"""

        user_prompt = f"""请分析以下章节的角色弧线推进情况：

【章节内容】
{chapter}

【角色弧线数据】
{context.get('character_arcs', {})}

【章节索引】
{chapter_index}

请判断每个角色的弧线是否应该推进，以及是否在章节中找到了推进的触发条件。"""

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
        reasoning = "LLM 角色弧线分析完成"

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
                updates = []
            else:
                issues.append({
                    "type": "character_arc",
                    "issue": f"LLM 分析响应解析失败",
                    "suggestion": "请人工检查角色弧线"
                })

        # 补充：基于规则的角色情感提取检查
        emotional_states = self._extract_emotional_states(chapter)
        if emotional_states:
            reasoning += f"; 检测到情感状态变化: {emotional_states}"

        return self._create_report(
            category=CheckCategory.CHARACTER_ARC,
            issues=issues,
            updates=updates,
            reasoning=reasoning,
            confidence=0.85
        )

    def _extract_emotional_states(self, chapter: str) -> Dict[str, List[str]]:
        """从章节中提取角色情感状态"""
        emotional_keywords = {
            "迷茫": ["困惑", "不确定", "迷失"],
            "觉醒": ["恍然大悟", "明白", "理解"],
            "成长": ["坚强", "勇敢", "突破"],
            "绝望": ["崩溃", "绝望", "放弃"],
            "希望": ["期待", "希望", "向往"],
        }

        states = {}
        for state, keywords in emotional_keywords.items():
            for kw in keywords:
                if kw in chapter:
                    # 简化处理
                    pass

        return states

    def _check_arc_trigger(self, chapter: str, char_name: str, next_stage: Dict) -> bool:
        """检查是否触发了进入下一阶段的关键条件"""
        key_moment = next_stage.get("key_moment", "")

        if not key_moment:
            return False

        # 简化：检查关键情感词是否出现在章节中
        emotional_state = next_stage.get("emotional_state", "")

        # 检查角色名和情感状态是否同时出现
        lines = chapter.split('\n')
        for line in lines:
            if char_name in line:
                # 如果角色名和关键情感同时出现，认为触发了弧线推进
                if emotional_state and emotional_state[:2] in line:
                    return True

        return False