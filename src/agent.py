from typing import Dict, Any, List
import json
from pathlib import Path

from src.prompt import *
from src.enhanced_prompts import get_prompt_template
from src.feedback_processor import FeedbackProcessor, ContentReferencer
from src.state import NovelState
from src.model import ChapterContent, ChapterOutline, QualityEvaluation, Character, NovelOutline
from src.model_manager import ModelManager
from src.config_loader import BaseConfig
from src.thinking_logger import log_agent_thinking
from src.evaluation_reporter import EvaluationReporter



# 大纲代理 - 用于生成统领大纲
class OutlineGeneratorAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config

    # 总纲生成(卷册划分)    
    def generate_master_outline(self, user_intent: str)->str:
        min_chapters = self.config.min_chapters
        volume = self.config.volume
        master_prompt = MASTER_OUTLINE_PROMPT.format(
            user_intent=user_intent, min_chapters=min_chapters, volume=volume
        )
        
        messages = [
            {"role":"system", "content": OUTLINE_INSTRUCT},
            {"role":"user", "content":master_prompt}
        ]

        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="OutlineGeneratorAgent",
            node_name="generate_master_outline",
            prompt_content=messages,
            response_content=response
        )
        
        return response
        
    # 基于总纲生成单卷
    def generate_volume_chapters(self, state: NovelState, volume_index:int) -> str:
        master_outline = state.validated_outline.master_outline
        current_volume = master_outline[volume_index]
        start_idx, end_idx = map(int, current_volume.chapters_range.split('-'))
        
        
        
        # 提取前卷关键信息作为上下文
        prev_context = ""
        if volume_index > 0:
            prev_volume = master_outline[volume_index - 1]
            prev_context = f"前卷《{prev_volume.title}》结局：{prev_volume.key_turning_points[-1]}\n"
            last_start_idx, last_end_idx = map(int, prev_volume.chapters_range.split('-'))
            prev_context += f"前卷《{prev_volume.title}》共{last_end_idx-last_start_idx+1}章，{prev_volume.key_turning_points[-1]}。\n"
            
        prompt = VOLUME_OUTLINE_PROMPT.format(
            prev_context=prev_context, 
            current_volume=current_volume.title,
            start_idx=start_idx, end_idx=end_idx,
            num_chapter=end_idx-start_idx+1,
            master_outline=state.validated_outline.master_outline,
            character_list = ', '.join(state.validated_outline.characters),
            outline_title = state.validated_outline.title,
            outline_genre = state.validated_outline.genre,
            outline_theme = state.validated_outline.theme,
            outline_setting = state.validated_outline.setting,
            outline_plot_summary = state.validated_outline.plot_summary
        )
        if state.outline_validated_error:
            prompt = f"{prompt}之前的尝试{state.raw_volume_chapters}出现错误: {state.outline_validated_error}\n请修正错误并重新生成符合格式的大纲。\n"
        messages = [
            {"role":"system", "content": OUTLINE_INSTRUCT},
            {"role":"user", "content":prompt}
        ]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="OutlineGeneratorAgent",
            node_name="generate_volume_chapters",
            prompt_content=messages,
            response_content=response,
            error_message=state.outline_validated_error
        )
        
        return response
    
    def generate_outline(self, state: NovelState) -> str:
        
        user_intent = state.user_intent
        error_message = state.outline_validated_error
        
        # 构建user信息
        user_message = OUTLINE_PROMPT.format(user_intent=user_intent, min_chapters = self.config.min_chapters)
        
        if error_message:
            user_message = f"之前的尝试出现错误: {error_message}\n请修正错误并重新生成符合格式的大纲。特别注意要用```json和```正确包裹JSON内容。\n{user_message}"
            
        # chat compelet
        messages = [
            {
                "role":"system",
                "content":OUTLINE_INSTRUCT
            },
            {
                "role":"user",
                "content":user_message
            }
        ]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="OutlineGeneratorAgent",
            node_name="generate_outline",
            prompt_content=messages,
            response_content=response,
            error_message=error_message
        )
        
        return response

# 角色代理 - 用于生成角色档案
class CharacterAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        
    
    def generate_characters(self, state: NovelState) -> str:
        # 从大纲中提取角色相关信息
        error_message = state.characters_validated_error
        
        outline = state.novel_storage.load_outline()
        characters_list = outline.characters
        
        # 提取每个角色在章节中出现的关键事件
        character_context = {}
        for name in characters_list:
            character_context[name] = []
        
        for chapter in outline.chapters:
            for char in chapter.characters_involved:
                if char in character_context:
                    character_context[char].append(f"在《{chapter.title}》中: {'; '.join(chapter.key_events)}")
        
        # 构建角色生成提示
        context = f"小说标题: {outline.title}\n类型: {outline.genre}\n背景: {outline.setting}\n情节概要: {outline.plot_summary}\n\n"
        context = "角色列表及他们在故事中的关键事件:\n"
        for name, events in character_context.items():
            context += f"- {name}: {'; '.join(events[:3])}\n"  # 取前3个关键事件
        
        prompt = CHARACTER_PROMPT.format(
            outline_title=outline.title,
            outline_genre=outline.genre,
            outline_setting=outline.setting,
            outline_plot_summary=outline.plot_summary,
            character_list=', '.join(characters_list),
            context=context
        )    
        if error_message:
            prompt += f"\n\n之前的尝试出现错误: {error_message}\n请修正错误并重新生成角色档案。"
        
        messages = [
            {
                "role":"user",
                "content":prompt
            }
        ]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="CharacterAgent",
            node_name="generate_characters",
            prompt_content=messages,
            response_content=response,
            error_message=error_message
        )
        
        return response
    
# 写作代理 - 用于单章撰写
class WriterAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        # 初始化反馈处理器
        self.feedback_processor = FeedbackProcessor(max_feedback_tokens=800)
        self.content_referencer = ContentReferencer()
    
    def write_chapter(self, state: NovelState) -> str:
        """撰写单章内容，增强反馈处理"""
        
        error_message = state.current_chapter_validated_error
        characters = state.novel_storage.load_characters()
        outline = state.novel_storage.load_outline()
        
        # 调用当前章节涉及角色的角色档案
        characters = [c for c in characters if c.name in outline.chapters[state.current_chapter_index].characters_involved]
        current_chapter_index = state.current_chapter_index
        
        # 获取评估反馈
        evaluation = state.validated_evaluation
        current_content = state.validated_chapter_draft
        
        # 处理反馈（如果存在）
        processed_feedback = None
        if evaluation and not evaluation.passes:
            processed_feedback = self.feedback_processor.process_evaluation(
                evaluation, 
                current_content, 
                state.evaluate_attempt
            )
        
        # 根据反馈确定写作策略
        strategy = "maintain_current"  # 默认策略
        if processed_feedback:
            strategy = processed_feedback.revision_strategy
        
        # 获取对应的提示词模板
        prompt_template = get_prompt_template(strategy)
        
        # 准备基础参数
        base_params = self._prepare_base_params(state, characters, outline, current_chapter_index)
        
        # 根据策略生成提示词
        if strategy == "maintain_current" or not processed_feedback:
            prompt = self._generate_base_prompt(prompt_template, base_params, error_message)
        else:
            prompt = self._generate_revision_prompt(
                prompt_template, base_params, processed_feedback, current_content
            )
        messages = [{"role": "user", "content": prompt}]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="WriterAgent",
            node_name="write_chapter",
            prompt_content=messages,
            response_content=response,
            error_message=error_message
        )
        
        return response

        
    
    def _prepare_base_params(self, state: NovelState, characters: List, outline, current_chapter_index: int) -> Dict:
        """准备基础参数，简化promt注入变量逻辑"""
        pre_chapter = state.novel_storage.load_chapter(current_chapter_index).content[-100:] if current_chapter_index > 0 else "无"
        pre_entity = state.novel_storage.load_entity(current_chapter_index-1) if current_chapter_index > 0 else None
        
        return {
            "genre": outline.genre,
            "outline_setting": outline.setting,
            "outline_title": outline.title,
            "outline_theme": outline.theme,
            "outline_plot_summary": outline.plot_summary,
            "character_list": ', '.join(outline.characters),
            "pre_summary": outline.chapters[current_chapter_index-1].summary if current_chapter_index > 0 else "无",
            "pre_context": pre_chapter,
            "post_summary": outline.chapters[current_chapter_index+1].summary if current_chapter_index < len(outline.chapters)-1 else "无",
            "chapter_outline_title": outline.chapters[current_chapter_index].title,
            "chapter_outline_key_events": ', '.join(outline.chapters[current_chapter_index].key_events),
            "chapter_outline_setting": outline.chapters[current_chapter_index].setting,
            "chapter_outline_summary": outline.chapters[current_chapter_index].summary,
            "character": characters,
            "current_chapter_idx": current_chapter_index,
            "num_chapters": len(outline.chapters),
            "word_count": 3000,
            "pre_entity": pre_entity
        }
    
    def _generate_base_prompt(self, template: str, params: Dict, error_message: str = None) -> str:
        """生成基础写作提示词"""
        prompt = template.format(**params)
        
        if error_message:
            prompt += f"\n\n错误信息: {error_message}"
            
        return prompt
    
    def _generate_revision_prompt(self, template: str, params: Dict, 
                                processed_feedback, current_content) -> str:
        """生成修改版提示词"""
        
        # 根据策略添加特定参数
        revision_params = params.copy()
        
        if processed_feedback.revision_strategy == "targeted_revision":
            revision_params.update({
                "original_title": current_content.title,
                "original_content": current_content.content[:2000],  # 限制长度
                "feedback_summary": processed_feedback.summary,
                "key_improvements": self._format_key_improvements(processed_feedback.evaluation.feedback_items),
                "revision_strategy": processed_feedback.revision_strategy
            })
        elif processed_feedback.revision_strategy == "expand_content":
            revision_params.update({
                "original_title": current_content.title,
                "original_content": current_content.content[:1500],
                "current_length": len(current_content.content),
                "expansion_needed": max(0, 3000 - len(current_content.content)),
                "expansion_strategy": "丰富细节描写，增加角色互动，扩展情节发展"
            })
        elif processed_feedback.revision_strategy == "character_focused":
            revision_params.update({
                "original_content": current_content.content[:2000],
                "character_feedback": self._extract_character_feedback(processed_feedback.evaluation.feedback_items),
                "character_profiles": self._format_character_profiles(params["character"])
            })
        elif processed_feedback.revision_strategy == "plot_focused":
            revision_params.update({
                "original_content": current_content.content[:2000],
                "plot_feedback": self._extract_plot_feedback(processed_feedback.evaluation.feedback_items)
            })
        elif processed_feedback.revision_strategy == "comprehensive_rewrite":
            revision_params.update({
                "feedback_history": self._format_feedback_history(processed_feedback)
            })
        
        return template.format(**revision_params)
    
    def _format_key_improvements(self, feedback_items: List) -> str:
        """格式化关键改进点"""
        improvements = []
        for i, item in enumerate(feedback_items[:3], 1):  # 最多3个
            improvements.append(f"{i}. {item.issue} - 建议：{item.suggestion}")
        return "\n".join(improvements)
    
    def _extract_character_feedback(self, feedback_items: List) -> str:
        """提取角色相关反馈"""
        character_issues = [item for item in feedback_items 
                          if item.category == "character"]
        if character_issues:
            return "; ".join([item.suggestion for item in character_issues[:2]])
        return "角色表现需要改进"
    
    def _extract_plot_feedback(self, feedback_items: List) -> str:
        """提取情节相关反馈"""
        plot_issues = [item for item in feedback_items 
                      if item.category == "plot"]
        if plot_issues:
            return "; ".join([item.suggestion for item in plot_issues[:2]])
        return "情节逻辑需要改进"
    
    def _format_character_profiles(self, characters: List) -> str:
        """格式化角色档案"""
        profiles = []
        for char in characters[:3]:  # 最多3个角色
            profiles.append(f"角色：{char.name}\n性格：{char.personality}\n目标：{', '.join(char.goals[:2])}")
        return "\n\n".join(profiles)
    
    def _format_feedback_history(self, processed_feedback) -> str:
        """格式化反馈历史"""
        return f"主要问题：{processed_feedback.summary}\n关键改进点：{self._format_key_improvements(processed_feedback.evaluation.feedback_items)}"

    def _write_expansion(self, state: NovelState) -> str:
        """扩写"""
        pass

    

# 反思代理 - 用于评审章节质量
class ReflectAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        self.system_prompt = REFLECT_PROMPT
        # 初始化评测报告生成器
        self.evaluation_reporter = EvaluationReporter()
        
    
    def evaluate_chapter(self, state: NovelState) -> str:
        """评估章节质量并提供反馈 - 增强版智能化评测"""
        error_message = state.evaluation_validated_error
        outline = state.novel_storage.load_outline()
        current_chapter_index = state.current_chapter_index
        chapter_content = state.validated_chapter_draft
        chapter_outline = outline.chapters[current_chapter_index]
        characters = state.novel_storage.load_characters()
         
        involved_chars = [char for char in characters 
                         if char.name in chapter_outline.characters_involved]
        
        # 构建增强版评估上下文 - 符合软件测试领域的标准化评测要求
        context = self._build_evaluation_context(
            chapter_content, chapter_outline, involved_chars, outline, current_chapter_index
        )
        
        if error_message:
            context += f"\n\n之前的评估错误: {error_message}"

        user_message = f"请基于以下标准化评测框架对章节内容进行全面评估:\n{context}\n请生成符合格式的评估JSON:"
        
        messages = [
            {
                "role":"system",
                "content":self.system_prompt
            },
            {
                "role":"user",
                "content":user_message
            }
        ]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="ReflectAgent",
            node_name="evaluate_chapter",
            prompt_content=messages,
            response_content=response,
            error_message=error_message
        )
        
        return response

    def generate_evaluation_report(self, state:NovelState):
        """生成评测报告"""
        chapter_content = state.validated_chapter_draft
        response = state.validated_evaluation
        self._generate_evaluation_report(state, chapter_content, response)

        
    def _build_evaluation_context(self, chapter_content: ChapterContent, chapter_outline: ChapterOutline, involved_chars:List[Character], outline:NovelOutline, current_chapter_index: int):
        """构建标准化评测上下文"""
        context = "=== 标准化内容质量评测框架 ===\n\n"
        
        # 1. 基础信息
        context += "【基础信息】\n"
        context += f"章节标题: {chapter_content.title}\n"
        context += f"章节大纲摘要: {chapter_outline.summary}\n"
        context += f"关键事件要求: {', '.join(chapter_outline.key_events)}\n"
        context += f"实际长度: {len(chapter_content.content)}字符\n\n"
        
        # 2. 角色一致性检查
        context += "【角色一致性检查】\n"
        for char in involved_chars:
            context += f"- {char.name}: 性格({char.personality}) | 目标({', '.join(char.goals[:2])})\n"
        context += "\n"
        
        # 3. 情节连贯性检查
        context += "【情节连贯性检查】\n"
        if current_chapter_index > 0:
            prev_chapter = outline.chapters[current_chapter_index - 1]
            context += f"前章关键事件: {', '.join(prev_chapter.key_events)}\n"
        if current_chapter_index < len(outline.chapters) - 1:
            next_chapter = outline.chapters[current_chapter_index + 1]
            context += f"后章关键事件: {', '.join(next_chapter.key_events)}\n"
        context += "\n"
        
        # 4. 内容完整性检查
        context += "【内容完整性检查】\n"
        context += f"大纲要求的关键事件数量: {len(chapter_outline.key_events)}\n"
        context += f"大纲要求的角色数量: {len(chapter_outline.characters_involved)}\n"
        context += "\n"
        
        # 5. 评测标准说明
        context += "【评测标准说明】\n"
        context += "一致性评分: 评估内容与大纲、前文、角色设定的符合程度\n"
        context += "连贯性评分: 评估情节逻辑、过渡自然度、因果关系\n"
        context += "完整性评分: 评估关键事件覆盖、角色表现、场景描写\n"
        context += "正确性评分: 评估事实准确性、逻辑合理性\n"
        context += "\n"
        
        # 6. 待评测内容
        context += "【待评测内容】\n"
        context += chapter_content.content

        return context
    
    def _generate_evaluation_report(self, state: NovelState, chapter_content: ChapterContent, evaluation_response: str):
        """生成标准化评测报告 - 展示EvaluationReporter的实际使用"""
        
        # 准备评测数据
        evaluation_data = {
            "chapter_title": chapter_content.title,
            "chapter_index": state.current_chapter_index,
            "evaluation_response": evaluation_response,
            "evaluate_attempt": state.evaluate_attempt
        }
        
        # 使用EvaluationReporter生成报告
        report = self.evaluation_reporter.generate_evaluation_report(state.validated_evaluation, evaluation_data)
 
        # 保存报告到result目录
        report_filename = f"evaluation_report_chapter_{state.current_chapter_index}.json"
        report_path = f"result/{state.novel_storage.load_outline().title}_storage/evaluate_reports"
        report_path = Path(report_path)
        report_path.mkdir(exist_ok=True)
        report_path = report_path / report_filename
        self.evaluation_reporter.save_report(report, report_path)


# 实体代理 - 用于控制情节发展
class EntityAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        self.system_prompt = WORLD_SYS_PROMPT
        
    def generate_entities(self, state: NovelState) :
        """根据章节内容添加动态实体信息，帮助维护情节一致性"""
 
        text_content = state.validated_chapter_draft.content
        chapter_name = state.validated_chapter_draft.title
        
        messages = [
            {
                "role":"system",
                "content":self.system_prompt
            },
            {
                "role":"user",
                "content":WORLD_USER_PROMPT.format(chapter_name=chapter_name, text_content=text_content)
            }
        ]
        
        response = self.model_manager.generate(messages, self.config)
        
        # 记录思考过程
        log_agent_thinking(
            agent_name="EntityAgent",
            node_name="generate_entities",
            prompt_content=messages,
            response_content=response
        )
        
        return response
