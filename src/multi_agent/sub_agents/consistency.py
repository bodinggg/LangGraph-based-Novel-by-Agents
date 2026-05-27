"""
ConsistencyChecker - 检查章节内部一致性（时间线、角色行为）

只检查章节内部一致性，不检查角色档案匹配。
角色档案是设定，章节不需要显式提及所有设定值。
"""
import re
import logging
from typing import Dict, Any, List

from src.multi_agent.sub_agents.base import BaseSubAgent
from src.multi_agent.types import SubAgentReport, CheckCategory, Suggestion, Priority

logger = logging.getLogger(__name__)


class ConsistencyChecker(BaseSubAgent):
    """章节内部一致性检查器"""

    def __init__(self, model_manager=None):
        super().__init__(model_manager, "ConsistencyChecker")

    async def check(self, chapter: str, context_text: str, chapter_index: int) -> SubAgentReport:
        """
        检查章节内部一致性

        1. 时间线一致性：检查章节内的时间描述是否矛盾
        2. 角色行为一致性：检查角色行为是否符合已有设定
        3. 地点一致性：检查角色移动是否合理
        """
        # 构建 LLM 分析用的提示
        system_prompt = """你是一位专业的章节一致性审查专家。请仔细分析给定的小说章节，检查以下方面的一致性问题：

1. 时间线一致性：检查章节内的时间描述是否矛盾（如第3天后突然出现第1天）
2. 角色行为一致性：检查角色行为是否符合性格设定和已知背景
3. 地点一致性：检查角色移动是否合理，是否有突兀的地点跳跃

请以 JSON 格式输出，包含以下字段：
- issues: 问题列表，每个问题包含 type(问题类型)、issue(问题描述)、location(位置)、suggestion(修改建议)
- reasoning: 分析理由

如果没有发现问题，issues 为空数组。"""

        user_prompt = f"""请分析以下章节的一致性问题：

【章节内容】
{chapter}

【上下文信息】
{context_text}

请仔细检查时间线、角色行为和地点的一致性，并给出具体的问题位置和修改建议。输出 JSON 格式。"""

        # 调用 LLM 进行分析
        response = await self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            chapter_index=chapter_index,
            require_json=True
        )

        # 解析 LLM 响应
        issues = []
        reasoning = "LLM 分析完成"

        try:
            import json as json_module
            # 尝试从响应中提取 JSON
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            parsed = json_module.loads(response_clean)
            issues = parsed.get("issues", [])
            reasoning = parsed.get("reasoning", "LLM 分析完成")
        except Exception as e:
            # JSON 解析失败，记录警告但继续处理
            logger.warning(f"LLM 响应 JSON 解析失败: {e}, 原始响应: {response[:200]}")
            # 尝试简单解析
            if "未发现" in response or "没有问题" in response:
                issues = []
            else:
                issues.append({
                    "type": "consistency",
                    "issue": f"LLM 分析响应解析失败: {response[:100]}",
                    "location": "",
                    "suggestion": "请人工检查"
                })

        # 额外的时间线检查（基于规则的补充检查）
        timeline_issues = self._check_timeline_consistency(chapter)
        if timeline_issues:
            issues.extend(timeline_issues)
            reasoning += f"; 发现 {len(timeline_issues)} 个时间线问题"

        reasoning = reasoning if reasoning else "未发现一致性问题"

        confidence = 0.85  # LLM 分析的置信度

        return self._create_report(
            category=CheckCategory.CONSISTENCY,
            issues=issues,
            reasoning=reasoning,
            confidence=confidence
        )

    def _check_timeline_consistency(self, chapter: str) -> List[Dict[str, Any]]:
        """检查时间线一致性"""
        issues = []

        # 提取时间表达
        time_patterns = [
            r'(第[一二三四五六七八九十\d]+天)',
            r'(昨天|今天|明天|后天)',
            r'(早晨|上午|中午|下午|傍晚|晚上|深夜|凌晨)',
            r'(新纪元\d+年)',
            r'(\d+小时前|\d+天后)',
        ]

        time_refs = []
        for pattern in time_patterns:
            matches = re.findall(pattern, chapter)
            time_refs.extend(matches)

        # 检查连续的时间描述矛盾
        # 例如：先说"第3天"，后说"第1天"
        chapter_lines = chapter.split('\n')
        day_sequence = []
        for i, line in enumerate(chapter_lines):
            day_matches = re.findall(r'第([一二三四五六七八九十\d]+)天', line)
            if day_matches:
                day_sequence.append((i + 1, day_matches[0]))

        # 检查序列矛盾
        for i in range(len(day_sequence) - 1):
            curr_line, curr_day = day_sequence[i]
            next_line, next_day = day_sequence[i + 1]

            # 转换中文数字为阿拉伯数字
            curr_num = self._cn_to_num(curr_day)
            next_num = self._cn_to_num(next_day)

            if curr_num and next_num:
                # 如果后面的天数突然变小（忽略相邻天数的正常叙述）
                if next_num < curr_num - 1:
                    issues.append({
                        "type": "timeline",
                        "issue": f"时间线矛盾: 第{curr_day}天后突然出现第{next_day}",
                        "location": f"第{curr_line}行",
                        "suggestion": f"检查时间顺序是否正确，确保时间推进逻辑一致"
                    })

        return issues

    def _check_character_behavior(self, chapter: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查角色行为一致性（基于 StoryBible 中的角色设定）"""
        issues = []

        character_arcs = context.get("character_arcs", {})

        # 简化检查：如果章节提到角色死亡/离开，但没有交代原因
        death_mentions = []
        for name, arc in character_arcs.items():
            current_stage = arc.current_stage_index
            # 如果角色处于"死亡"或"消失"阶段，但章节提到他出现
            # 这需要更复杂的逻辑，这里简化处理

        return issues

    def _check_location_consistency(self, chapter: str) -> List[Dict[str, Any]]:
        """检查地点一致性"""
        issues = []

        # 提取地点变化
        location_patterns = [
            r'从(.+)来到(.+)',
            r'前往(.+)',
            r'到达(.+)',
            r'在(.+)的(.+?)',
        ]

        locations = []
        chapter_lines = chapter.split('\n')
        for i, line in enumerate(chapter_lines):
            for pattern in location_patterns:
                matches = re.findall(pattern, line)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            locations.append((i + 1, match[0], match[-1]))
                        else:
                            locations.append((i + 1, match, match))

        # 检查不合理的地点跳跃（比如上一秒还在旧城区，下一秒就到了诊所）
        # 简化：检查相邻两行的地点是否在同一个区域
        for i in range(len(locations) - 1):
            curr_line, curr_loc, curr_detail = locations[i]
            next_line, next_loc, next_detail = locations[i + 1]

            # 如果距离太近但地点完全不同，可能有问题
            if abs(next_line - curr_line) <= 3 and curr_loc != next_loc:
                # 这里可以添加更复杂的地理合理性检查
                pass

        return issues

    def _cn_to_num(self, cn: str) -> int:
        """中文数字转阿拉伯数字"""
        cn_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        try:
            if '十' in cn:
                if cn == '十':
                    return 10
                parts = cn.split('十')
                if parts[0]:
                    return cn_map.get(parts[0], 1) * 10 + cn_map.get(parts[1], 0)
                else:
                    return 10 + cn_map.get(parts[1], 0)
            return cn_map.get(cn, int(cn) if cn.isdigit() else 0)
        except:
            return 0