
from src.prompt import *
from src.state import NovelState
from src.model import ChapterContent
from src.model_manager import ModelManager
from src.config_loader import BaseConfig

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
        return self.model_manager.generate(messages, self.config)
        
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

        prompt = VOLUME_OUTLINE_PROMPT.format(
            prev_context=prev_context, current_volume=current_volume.title, start_idx=start_idx, end_idx=end_idx, num_chapter=end_idx-start_idx+1, master_outline=state.validated_outline
        )
        if state.outline_validated_error:
            prompt = f"之前的尝试出现错误: {state.outline_validated_error}\n请修正错误并重新生成符合格式的大纲。特别注意要用```json和```正确包裹JSON内容。\n{prompt}"
        messages = [
            {"role":"system", "content": OUTLINE_INSTRUCT},
            {"role":"user", "content":prompt}
        ]
        
        return self.model_manager.generate(messages, self.config)
    
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
        
        return self.model_manager.generate(messages, self.config)

# 角色代理 - 用于生成角色档案
class CharacterAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        
    
    def generate_characters(self, state: NovelState) -> str:
        # 从大纲中提取角色相关信息
        error_message = state.characters_validated_error
        
        outline = state.validated_outline
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
        
        return self.model_manager.generate(messages, self.config)
    
# 写作代理 - 用于单章撰写
class WriterAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
    
    def write_chapter(self, state: NovelState) -> str:
        """撰写单章内容"""
        
        error_message = state.current_chapter_validated_error
        outline = state.validated_outline
        # 调用当前章节涉及角色的角色档案
        characters = [ c for c in state.validated_characters if c.name in outline.chapters[state.current_chapter_index].characters_involved]
        current_chapter_index = state.current_chapter_index
        
        
        quality = state.validated_evaluation
        if quality:
            print(f"[test] quality:\n{quality}")
            revision_feedback = quality.feedback
        else:
            revision_feedback = None    
        
        
        # 构建上下文信息
        prompt = WRITER_PROMPT.format(
            genre=outline.genre,
            outline_setting=outline.setting,
            outline_title=outline.title,
            outline_theme = outline.theme,
            outline_plot_summary = outline.plot_summary,
            character_list = ', '.join(outline.characters),
            pre_summary = outline.chapters[current_chapter_index-1].summary if current_chapter_index > 0 else "无",
            pre_context = state.chapters_content[-1].content[-100:] if current_chapter_index > 0 else "无",
            post_summary = outline.chapters[current_chapter_index+1].summary if current_chapter_index < len(outline.chapters)-1 else "无",
            chapter_outline = outline.chapters[current_chapter_index],
            chapter_outline_title = outline.chapters[current_chapter_index].title,
            chapter_outline_key_events = ', '.join(outline.chapters[current_chapter_index].key_events),
            chapter_outline_setting = outline.chapters[current_chapter_index].setting,
            chapter_outline_summary = outline.chapters[current_chapter_index].summary,
            character = characters,
            current_chapter_idx = current_chapter_index,
            num_chapters = len(outline.chapters),
            word_count = 3000,
        )
        # 错误信息与修改意见放在最后
        if error_message:
            prompt += error_message
        if revision_feedback:
            prompt += f"\n\n修改意见: {revision_feedback}"

        messages = [
            {
                "role":"user",
                "content":prompt
            }
        ]
        
        return self.model_manager.generate(messages, self.config)

    def _write_expansion(self, state: NovelState) -> str:
        """扩写"""
        pass


    
    def write_section(self, state:NovelState) -> str:
        """分节写作"""
        # 章节基本信息
        outline = state.validated_outline
        
        current_chapter_index = state.current_chapter_index
        chapters = outline.chapters
        chapter_outline = chapters[current_chapter_index]
        
        context = self._get_relavant_context(state, current_chapter_index)
        base_info = f"""
        第{current_chapter_index}章: {chapter_outline.title}
        章节摘要: {chapter_outline.summary}
        关键事件: {', '.join(chapter_outline.key_events)}
        场景: {chapter_outline.setting}
        涉及角色: {', '.join(chapter_outline.characters_involved)}
        """
        #  分三部分写作：开头、中间、结尾
        generated_text = ""
        
        # 1. 开头部分 (约1500字)
        opening_prompt = f"""
        {context}

        {base_info}

        请撰写这一章的开头部分, 包括：
        - 场景描述
        - 引入主要人物
        - 设定章节基调
        - 引出本章主要事件的开端

        确保内容生动、细节丰富, 字数不少于2000字。
        
        直接生成小说内容！
        """
        
        # 对话模板待添加
        generated_text += self.model_manager.generate(self.system_prompt+opening_prompt, self.config)

        # 2. 中间部分 (约1500-2000字)
        # 提供前文作为上下文
        middle_prompt = f"""
        {base_info}

        本章开头部分内容：
        ...{generated_text[-500:]}  

        请继续撰写本章的中间部分, 包括：
        - 发展章节的主要冲突和事件
        - 展示角色互动
        - 推进情节发展
        - 增加情节紧张度或复杂性

        确保内容生动、细节丰富, 字数不少于2000字, 衔接流畅。
        
        直接生成小说内容！
        """
        
        # 对话模板待添加
        generated_text += self.model_manager.generate(self.system_prompt+middle_prompt, self.config)
        # 3. 结尾部分 (约1500字)
        ending_prompt = f"""
        {base_info}

        本章前文内容摘要：
        ...{generated_text[-500:]} 

        请完成本章的结尾部分, 包括：
        - 解决或推进本章的主要冲突
        - 展示角色的反应和情感变化
        - 为下一章埋下伏笔
        - 以合适的钩子结束本章

        确保内容生动、细节丰富, 字数不少于2000字, 与前文无缝衔接。
        
        直接生成小说内容！
        """

        # 对话模板待添加
        generated_text += self.model_manager.generate(self.system_prompt+ending_prompt, self.config)
        title = state.validated_outline.chapters[current_chapter_index].title
        temp_ChapterContent = ChapterContent(title=title, content=generated_text)
        
        return str(temp_ChapterContent)

    
    def _get_relavant_context(self, state:NovelState, chapter_id:int) -> str:
        
        # 角色档案
        relevant_chars = []
        for char in state.validated_characters:
            if char.name in state.validated_outline.chapters[chapter_id].characters_involved:
                # 简化的角色信息减少token
                char_summary = f"角色：{char.name}\n性格：{char.personality}\n"
                char_summary += f"目标：{', '.join(char.goals)}\n"
                relevant_chars.append(char_summary)
        relevant_chars = '\n'.join(relevant_chars)
        context = f"""相关角色信息：{relevant_chars}"""
        
        # 利用大纲生成的摘要信息当前文信息
        if chapter_id > 0:
            context += f"前一章（{state.validated_outline.chapters[chapter_id-1].title}） 摘要：{state.validated_outline.chapters[chapter_id-1].summary}"
            context += f"前一章最后的内容为：...{state.chapters_content[-1].content[-100:]}"
        
        return context

# 反思代理 - 用于评审章节质量
class ReflectAgent:
    def __init__(self, model_manager: ModelManager, config: BaseConfig):
        self.model_manager = model_manager
        self.config = config
        self.system_prompt = REFLECT_PROMPT
        
    
    def evaluate_chapter(self, state: NovelState) -> str:
        """评估章节质量并提供反馈"""
        error_message = state.evaluation_validated_error
        
        current_chapter_index = state.current_chapter_index
        chapter_content = state.validated_chapter_draft
        chapter_outline = state.validated_outline.chapters[current_chapter_index]
        characters = state.validated_characters
         
        involved_chars = [char for char in characters 
                         if char.name in chapter_outline.characters_involved]
        
        # 构建评估上下文
        context = f"章节标题: {chapter_content.title}\n"
        context += f"章节大纲摘要: {chapter_outline.summary}\n"
        context += f"关键事件要求: {', '.join(chapter_outline.key_events)}\n\n"
        
        context += "本章涉及角色及其性格:\n"
        for char in involved_chars:
            context += f"- {char.name}: {char.personality}\n"

        context += f"实际长度: {len(chapter_content.content)}字符\n\n"
        
        context += "章节内容:\n"
        context += chapter_content.content
        
        if error_message:
            context += error_message

        user_message = f"请评审以下章节内容并提供评估:\n{context}\n请生成符合格式的评估JSON:"
        
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
        
        return self.model_manager.generate(messages, self.config)
