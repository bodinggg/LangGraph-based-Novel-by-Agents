from transformers import pipeline, AutoTokenizer

from src.prompt import *
from src.state import NovelState
from src.config import *
from src.model import *

# 大纲代理 - 用于生成统领大纲
class OutlineGeneratorAgent:
    def __init__(self, model_pipeline: pipeline, tokenizer: AutoTokenizer):
        self.pipeline = model_pipeline
        self.tokenizer = tokenizer
        self.system_prompt = OUTLINE_PROMPT
    def generate_outline(self, state: NovelState) -> str:
        
        user_intent = state.user_intent
        error_message = state.outline_validated_error
        
        # 构建对话历史
        messages = [
            {"role":"system", "content": self.system_prompt},
        ]
        
        # 构建user信息
        user_message = f"用户需求：{user_intent}\n请先思考，然后生成大纲"
        
        if error_message:
            user_message = f"之前的尝试出现错误: {error_message}\n请修正错误并重新生成符合格式的大纲。特别注意要用```json和```正确包裹JSON内容。\n{user_message}"
        
        messages.append({"role":"user", "content": user_message})
        
        # 转换为模型需要的输入格式
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize = False,
        )
        
        result = self.pipeline(
            prompt,
            max_new_tokens = OutlineConfig.max_new_tokens,
            temperature = OutlineConfig.temperature,
            top_p = OutlineConfig.top_p,
            do_sample = True,
        )
        
        # 提取生成的回答
        generated_text = result[0]["generated_text"][len(prompt):].strip()
        
        return generated_text

# 角色代理 - 用于生成角色档案
class CharacterAgent:
    def __init__(self, model_pipeline: pipeline, tokenizer: AutoTokenizer):
        self.pipeline = model_pipeline
        self.tokenizer = tokenizer
        self.system_prompt = CHARACTER_PROMPT
    
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
        context += "角色列表及他们在故事中的关键事件:\n"
        for name, events in character_context.items():
            context += f"- {name}: {'; '.join(events[:3])}\n"  # 取前3个关键事件
        if error_message:
            context += error_message
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"根据以下小说大纲生成详细角色档案:\n{context}\n请生成符合格式的角色档案JSON:"}
        ]
        
        # 转换为模型需要的输入格式
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        result = self.pipeline(
            prompt,
            max_new_tokens=CharacterConfig.max_new_tokens,
            temperature=CharacterConfig.temperature,
            top_p=CharacterConfig.top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        generated_text = result[0]['generated_text'][len(prompt):].strip()
        return generated_text

# 写作代理 - 用于单章撰写
class WriterAgent:
    def __init__(self, model_pipeline: pipeline, tokenizer: AutoTokenizer):
        self.pipeline = model_pipeline
        self.tokenizer = tokenizer
        self.system_prompt = WRITER_PROMPT
        
    
    def write_chapter(self, state: NovelState) -> str:
        """撰写单章内容"""
        
        error_message = state.current_chapter_validated_error
        outline = state.validated_outline
        characters = state.validated_characters
        
        current_chapter_index = state.current_chapter_index
        chapters = outline.chapters
        chapter_outline = chapters[current_chapter_index]
        novel_title = outline.title
        genre = outline.genre
        setting = outline.setting
        quality = state.validated_evaluation
        if quality:
            revision_feedback = quality.feedback
        else:
            revision_feedback = None    
        
        
        # 构建上下文信息
        context = f"小说标题: {novel_title}\n类型: {genre}\n整体背景: {setting}\n\n"
        
        # 添加当前章节大纲
        context += "当前章节大纲:\n"
        context += f"标题: {chapter_outline.title}\n"
        context += f"摘要: {chapter_outline.summary}\n"
        context += f"关键事件: {', '.join(chapter_outline.key_events)}\n"
        context += f"场景: {chapter_outline.setting}\n\n"
        
        # 添加本章涉及的角色信息
        involved_chars = [char for char in characters 
                         if char.name in chapter_outline.characters_involved]
        context += "本章涉及角色:\n"
        for char in involved_chars:
            context += f"- {char.name}: 性格={char.personality}; 目标={', '.join(char.goals[:2])}; 背景摘要={char.background}\n"
        
        # 添加前情提要（最近2章）
        if current_chapter_index > 1:
            context += "\n前情提要:\n"
            for prev in state.validated_outline.chapters[current_chapter_index-2:current_chapter_index]:  # 只取最近2章
                context += f"第{current_chapter_index}章《{prev.title}》: {prev.summary}...\n"
        if error_message:
            context += error_message
        # 添加修改意见（如果有）
        user_message = f"根据以下信息撰写章节内容:\n{context}\n请生成符合格式的章节JSON:"
        if revision_feedback:
            user_message = f"修改意见:\n{revision_feedback}\n请根据以上意见修改章节内容，保持核心情节不变但改进写作质量。\n{user_message}"
        
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]
        print(f"[write_chapter] |{current_chapter_index}| {user_message}")
        # 转换为模型需要的输入格式
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # 调用模型生成章节内容
        result = self.pipeline(
            prompt,
            max_new_tokens=WriterConfig.max_new_tokens, 
            temperature=WriterConfig.temperature,  
            top_p=WriterConfig.top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        generated_text = result[0]['generated_text'][len(prompt):].strip()
        return generated_text

    def write_section(self, state:NovelState) -> str:
        """分节写作"""
        # 章节基本信息
        error_message = state.current_chapter_validated_error
        outline = state.validated_outline
        characters = state.validated_characters
        
        current_chapter_index = state.current_chapter_index
        chapters = outline.chapters
        chapter_outline = chapters[current_chapter_index]
        novel_title = outline.title
        genre = outline.genre
        setting = outline.setting
        
        quality = state.validated_evaluation
        
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

        请撰写这一章的开头部分，包括：
        - 场景描述
        - 引入主要人物
        - 设定章节基调
        - 引出本章主要事件的开端

        确保内容生动、细节丰富，字数不少于2000字。
        
        直接生成小说内容！
        """
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": opening_prompt}
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        generated_text += self._get_content(state, prompt)
        # 2. 中间部分 (约1500-2000字)
        # 提供前文作为上下文
        middle_prompt = f"""
        {base_info}

        本章开头部分内容：
        ...{generated_text[-500:]}  

        请继续撰写本章的中间部分，包括：
        - 发展章节的主要冲突和事件
        - 展示角色互动
        - 推进情节发展
        - 增加情节紧张度或复杂性

        确保内容生动、细节丰富，字数不少于2000字，衔接流畅。
        
        直接生成小说内容！
        """
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": middle_prompt}
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        generated_text += self._get_content(state, prompt)
        # 3. 结尾部分 (约1500字)
        ending_prompt = f"""
        {base_info}

        本章前文内容摘要：
        ...{generated_text[-500:]} 

        请完成本章的结尾部分，包括：
        - 解决或推进本章的主要冲突
        - 展示角色的反应和情感变化
        - 为下一章埋下伏笔
        - 以合适的钩子结束本章

        确保内容生动、细节丰富，字数不少于2000字，与前文无缝衔接。
        
        直接生成小说内容！
        """
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": ending_prompt}
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        generated_text += self._get_content(state, prompt)
        title = state.validated_outline.chapters[current_chapter_index].title
        temp_ChapterContent = ChapterContent(title=title, content=generated_text)
        
        return str(temp_ChapterContent)
        
    # 直接生成内容拼接
    def _get_content(self, state:NovelState, prompt:str) -> str:
        result = self.pipeline(
            prompt,
            max_new_tokens=WriterConfig.max_new_tokens, 
            temperature=WriterConfig.temperature,  
            top_p=WriterConfig.top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        generated_text = result[0]['generated_text'][len(prompt):].strip()
        return generated_text
    
    def _get_relavant_context(self, state:NovelState, chapter_id:int) -> str:
        
        # 角色档案
        relevant_chars = []
        for char in state.validated_characters:
            if char.name in state.validated_outline.chapters[chapter_id].characters_involved:
                # 简化的角色信息减少token
                char_summary = f"角色：{char.name}\n性格：{char.personality}\n"
                char_summary += f"目标：{'，'.join(char.goals)}\n"
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
    def __init__(self, model_pipeline: pipeline, tokenizer: AutoTokenizer):
        self.pipeline = model_pipeline
        self.tokenizer = tokenizer
        self.system_prompt = REFLECT_PROMPT
    
    def evaluate_chapter(self, state: NovelState) -> str:
        """评估章节质量并提供反馈"""
        error_message = state.evaluation_validated_error
        
        current_chapter_index = state.current_chapter_index
        chapter_content = state.validated_chapter_draft
        chapter_outline = state.validated_outline.chapters[current_chapter_index]
        characters = state.validated_characters
        
        min_length = WriterConfig.min_word_length
         
        involved_chars = [char for char in characters 
                         if char.name in chapter_outline.characters_involved]
        
        # 构建评估上下文
        context = f"章节标题: {chapter_content.title}\n"
        context += f"章节大纲摘要: {chapter_outline.summary}\n"
        context += f"关键事件要求: {', '.join(chapter_outline.key_events)}\n\n"
        
        context += "本章涉及角色及其性格:\n"
        for char in involved_chars:
            context += f"- {char.name}: {char.personality}\n"
        
        context += f"\n最小长度要求: {min_length}字符\n"
        context += f"实际长度: {len(chapter_content.content)}字符\n\n"
        
        context += "章节内容:\n"
        context += chapter_content.content
        
        if error_message:
            context += error_message
        
        # 构建对话历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请评审以下章节内容并提供评估:\n{context}\n请生成符合格式的评估JSON:"}
        ]
        
        # 转换为模型需要的输入格式
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # 调用模型进行评估
        result = self.pipeline(
            prompt,
            max_new_tokens=ReflectConfig.max_new_tokens,
            temperature=ReflectConfig.temperature,  # 较低的随机性，确保评估的一致性
            top_p=ReflectConfig.top_p,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        generated_text = result[0]['generated_text'][len(prompt):].strip()
        return generated_text
