"""
增强的提示词模板, 用于基于反馈的智能写作策略
"""
from src.prompt import WRITER_PROMPT

# 针对性修改提示词
ENHANCED_WRITER_REVISION_PROMPT = """你是专业的小说章节修改专家。基于评估反馈，对现有章节进行针对性改进：

## 原始内容
标题：{original_title}
内容：{original_content}

## 评估反馈摘要
{feedback_summary}

## 关键改进点
{key_improvements}

## 修改策略：{revision_strategy}

## 核心依据（保持一致）
1. 大纲内容：小说标题【{outline_title}】, 类型【{genre}】, 主题【{outline_theme}】
2. 章节要求：标题【{chapter_outline_title}】；关键事件【{chapter_outline_key_events}】
3. 角色信息：【{character}】
4. 上下文：前文【{pre_context}】，后文【{post_summary}】

## 修改要求
1. 重点解决反馈中提到的问题
2. 保持原有优秀部分不变
3. 确保修改后内容达到 {word_count} 字符以上
4. 维持与前后文的连贯性
5. 保持角色一致性和情节逻辑

## 输出格式
请用```json和```包裹JSON内容：
{{
  "title": "章节标题",
  "content": "修改后的完整内容",
  "notes": "主要修改说明"
}}
只输出JSON内容，不要添加其他解释或说明。"""

# 扩展内容提示词（针对长度不足）
ENHANCED_WRITER_EXPAND_PROMPT = """你是专业的小说内容扩展专家。当前章节内容不足，需要在保持质量的前提下扩展内容：

## 当前内容
标题：{original_title}
内容：{original_content}
当前长度：{current_length}字符

## 扩展要求
目标长度：{word_count}字符以上
需要增加：约{expansion_needed}字符

## 扩展策略
{expansion_strategy}

## 核心依据
1. 章节大纲：【{chapter_outline_title}】；关键事件【{chapter_outline_key_events}】
2. 角色信息：【{character}】
3. 上下文连贯：前文【{pre_context}】，后文【{post_summary}】

## 扩展方向
1. 丰富场景描写和环境细节
2. 深化角色心理活动和情感表达
3. 增加对话的层次和深度
4. 补充关键事件的过程细节
5. 加强情节转折的铺垫和渲染

## 输出格式
请用```json和```包裹JSON内容：
{{
  "title": "章节标题",
  "content": "扩展后的完整内容",
  "notes": "扩展说明"
}}
只输出JSON内容，不要添加其他解释或说明。"""

# 角色专注修改提示词
ENHANCED_WRITER_CHARACTER_FOCUSED_PROMPT = """你是专业的角色塑造专家。当前章节在角色表现方面存在问题，需要重点改进角色的一致性和表现力：

## 原始内容
{original_content}

## 角色问题反馈
{character_feedback}

## 角色档案参考
{character_profiles}

## 角色改进重点
1. 确保每个角色的对话符合其性格特点
2. 角色行为要体现其背景和动机
3. 角色间的互动要自然且有层次
4. 角色的情感变化要合理渐进
5. 角色的成长弧线要有所体现

## 核心依据
章节要求：【{chapter_outline_title}】；关键事件【{chapter_outline_key_events}】
上下文：前文【{pre_context}】，后文【{post_summary}】

## 输出格式
请用```json和```包裹JSON内容：
{{
  "title": "章节标题",
  "content": "角色优化后的完整内容",
  "notes": "角色改进说明"
}}
只输出JSON内容，不要添加其他解释或说明。"""

# 情节专注修改提示词
ENHANCED_WRITER_PLOT_FOCUSED_PROMPT = """你是专业的情节构建专家。当前章节在情节逻辑方面存在问题，需要重点改进情节的合理性和连贯性：

## 原始内容
{original_content}

## 情节问题反馈
{plot_feedback}

## 情节改进重点
1. 确保事件发展的逻辑合理性
2. 加强因果关系的清晰表达
3. 优化情节节奏和张力控制
4. 完善关键转折点的铺垫
5. 强化与前后章节的连接

## 核心依据
1. 章节大纲：【{chapter_outline_title}】；关键事件【{chapter_outline_key_events}】
2. 整体情节：【{outline_plot_summary}】
3. 上下文：前文【{pre_context}】，后文【{post_summary}】

## 输出格式
请用```json和```包裹JSON内容：
{{
  "title": "章节标题", 
  "content": "情节优化后的完整内容",
  "notes": "情节改进说明"
}}
只输出JSON内容，不要添加其他解释或说明。"""

# 全面重写提示词（多次修改后使用）
ENHANCED_WRITER_COMPREHENSIVE_REWRITE_PROMPT = """你是资深小说创作专家。经过多次修改，现需要对章节进行全面重写，综合考虑所有反馈意见：

## 历史反馈汇总
{feedback_history}

## 重写策略
基于多次反馈，采用全新视角重新构思和撰写本章节，确保：
1. 完全符合章节大纲要求
2. 解决所有已识别的问题
3. 保持高质量的写作水准
4. 与整体故事架构完美融合

## 核心依据
1. 大纲内容：小说标题【{outline_title}】, 类型【{genre}】, 主题【{outline_theme}】
2. 章节要求：【{chapter_outline_title}】；关键事件【{chapter_outline_key_events}】
3. 角色信息：【{character}】
4. 上下文：前文【{pre_context}】，后文【{post_summary}】

## 重写要求
1. 从全新角度构思章节结构
2. 确保内容达到 {word_count} 字符以上
3. 综合解决历史反馈中的所有问题
4. 追求更高的文学质量和可读性

## 输出格式
请用```json和```包裹JSON内容：
{{
  "title": "章节标题",
  "content": "全面重写后的完整内容", 
  "notes": "重写说明和改进点"
}}
只输出JSON内容，不要添加其他解释或说明。"""

# 提示词模板与策略建立映射关系
PROMPT_STRATEGY_MAP = {
    "maintain_current": WRITER_PROMPT,
    "targeted_revision": ENHANCED_WRITER_REVISION_PROMPT,
    "expand_content": ENHANCED_WRITER_EXPAND_PROMPT,
    "character_focused": ENHANCED_WRITER_CHARACTER_FOCUSED_PROMPT,
    "plot_focused": ENHANCED_WRITER_PLOT_FOCUSED_PROMPT,
    "comprehensive_rewrite": ENHANCED_WRITER_COMPREHENSIVE_REWRITE_PROMPT,
    "maintain_quality": WRITER_PROMPT
}

def get_prompt_template(strategy: str) -> str:
    """根据修改策略获取对应的提示词模板"""
    return PROMPT_STRATEGY_MAP.get(strategy, WRITER_PROMPT)
