import json
from typing import Literal

from src.model import (
    Character,
    ChapterOutline,
    VolumeOutline,  
    NovelOutline,
    ChapterContent,
    QualityEvaluation,
    EntityContent,
)
from src.agent import (
    OutlineGeneratorAgent,
    WriterAgent,
    CharacterAgent,
    ReflectAgent,
    EntityAgent,
) 
from src.tool import extract_json
from src.state import NovelState
from src.log_config import loggers
from src.config_loader import OutlineConfig
from src.storage import NovelStorage

logger = loggers['node']
        

# -------------------- 大纲(分卷) -------------------- [生成 -> 验证 -> 状态判断]
def generate_master_outline_node(state: NovelState, outline_agent:OutlineGeneratorAgent) -> NovelState:
    logger.info(f"开始分卷生成小说大纲(第{state.attempt + 1}次尝试)")
    raw_master = outline_agent.generate_master_outline(state.user_intent)
    extracted_json = extract_json(raw_master)
    if extracted_json:
        raw_master = extracted_json
        logger.info(f"【分卷】成功提取大纲JSON内容")
    return {
        "raw_master_outline": raw_master,
        "attempt":state.attempt+1
    }
    
def validate_master_outline_node(state: NovelState) -> NovelState:
    try:
        master_data = json.loads(state.raw_master_outline)
        master_data["chapters"]=[]
        validated_outline = NovelOutline(** master_data)
        master_outline = validated_outline.master_outline
        # 验证卷册章节范围合理性（总章节≥100）
        total_chapters = sum(int(vol.chapters_range.split('-')[1]) - int(vol.chapters_range.split('-')[0]) + 1 
                            for vol in master_outline)
        if total_chapters < state.min_chapters:
            raise ValueError(f"总章节数不足{state.min_chapters}（当前{total_chapters}章）")
        
        
            
        return {
            "validated_outline": validated_outline,
            "outline_validated_error": None,
            "attempt":0,
            "current_volume_index": 0  # 初始化当前卷索引
            
        }
        
    except json.JSONDecodeError as e:
        # 提供更详细的错误位置信息
        
        error_lines = state.raw_master_outline.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【分卷】 JSON格式解析错误:\n{error_msg}")
        return {
            "outline_validated_error": error_msg
        }     
    except Exception as e:
        logger.info(f"【分卷】格式验证失败: {str(e)}")
        return {
            "outline_validated_error": f"大纲验证失败: {str(e)}"
        }

def check_master_outline_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查大纲验证结果"""
    logger.info(f"检查大纲分卷验证结果...")
    if state.outline_validated_error is None:
        logger.info(f"【分卷】success:大纲检查成功, 转移至 generate_volume_outline 节点")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【分卷】retry:验证失败, 将进行第{state.attempt + 1}次重试...")
        return "retry"
    else:
        logger.info(f"【分卷】failure:大纲检查失败, 转移至 failure 节点")
        return "failure"
        
# -------------------- 大纲(分章) -------------------- [生成 -> 验证 -> 状态判断]   
def generate_volume_outline_node(state:NovelState, outline_agent:OutlineGeneratorAgent) -> NovelState:
    logger.info(f"开始分章生成卷{state.current_volume_index+1}小说大纲(第{state.attempt + 1}次尝试)")
    volume_index = state.current_volume_index
    raw_chapters = outline_agent.generate_volume_chapters(state, volume_index)
    extracted_json = extract_json(raw_chapters)
    if extracted_json:
        raw_chapters = extracted_json
        logger.info(f"【分章】成功提取大纲JSON内容")
    return {
        "raw_volume_chapters": raw_chapters,
        "attempt":state.attempt+1
    }

def validate_volume_outline_node(state:NovelState) -> NovelState:
    logger.info(f"开始分章验证卷{state.current_volume_index+1}小说大纲(第{state.attempt + 1}次尝试)")
    try:
        volume_index = state.current_volume_index
        volume_data = json.loads(state.raw_volume_chapters)
        chapters = [ChapterOutline(**chap) for chap in volume_data["chapters"]]
        # 验证章节编号与总纲一致
        master_vol = state.validated_outline.master_outline[volume_index]
        start_idx, end_idx = map(int, master_vol.chapters_range.split('-'))
        if len(chapters) != end_idx - start_idx + 1:
            logger.info(f"【分章】卷{volume_index+1}章节数不符（应有{end_idx-start_idx+1}章，实际{len(chapters)}章）")
            raise ValueError(f"卷{volume_index+1}章节数不符（应有{end_idx-start_idx+1}章，实际{len(chapters)}章）")
        
        # 检查角色一致性
        all_characters = set(state.validated_outline.characters)
        for chapter in chapters:
            for char in chapter.characters_involved:
                if char not in all_characters:
                    logger.info(f"【分章】角色'{char}'不在角色列表[{state.validated_outline.characters}]中")
                    raise ValueError(f"章节'{chapter.title}'中出现的角色'{char}'不在角色列表[{state.validated_outline.characters}]中")
                
        return {
            "validated_chapters": chapters,
            "outline_validated_error": None,
            "attempt":0
        }
    except json.JSONDecodeError as e:
        # 提供更详细的错误位置信息
        error_lines = state.raw_volume_chapters.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【分章】 JSON格式解析错误:\n{error_msg}")
        return {"outline_validated_error": error_msg}    
    except Exception as e:
        return {"outline_validated_error": str(e)}     

def check_volume_outline_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查大纲验证结果"""
    logger.info(f"检查分章卷{state.current_volume_index+1}验证结果...")
    if state.outline_validated_error is None:
        logger.info(f"【分章，卷{state.current_volume_index+1}】success:大纲检查成功, 转移至 accept_outline 节点")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【分章，卷{state.current_volume_index+1}】retry:验证失败, 将进行第{state.attempt + 1}次重试...")
        return "retry"
    else:
        logger.info(f"【分章，卷{state.current_volume_index+1}】failure:大纲检查失败, 转移至 failure 节点")
        return "failure"

# 中继节点
def volume2character(state:NovelState) -> NovelState:

    return {"attempt":0}


# 判断大纲是否创建结束
# 接受章节节点
def accept_outline_node(state: NovelState) -> NovelState:
    """接受当前卷, 将其添加到大纲中章节列表并准备处理下一卷"""
    # 合并到总章节列表
    chapters = state.validated_chapters
    validated_outline = state.validated_outline
    validated_outline.chapters.extend(chapters)
    current_volume_index = state.current_volume_index
    # 重置卷相关状态, 准备处理下一卷
    if current_volume_index == len(validated_outline.master_outline) - 1:
        state.novel_storage = NovelStorage(state.validated_outline.title)
        state.novel_storage.save_outline(state.validated_outline)
        
    
    return {
        "novel_storage": state.novel_storage,
        "validated_outline": validated_outline,
        "current_volume_index": current_volume_index + 1,
        "raw_volume_chapters": None
    }


def check_outline_completion_node(state: NovelState) -> Literal["continue", "complete"]:
    """检查是否所有大纲的卷都已撰写完成"""
    total_volumes = len(state.validated_outline.master_outline)
    current_index = state.current_volume_index
           
    if current_index < total_volumes:
        state.attempt = 0
        logger.info("接受此卷, 将其添加到大纲中章节列表并准备处理下一卷")
        return "continue"
    else:
        
        logger.info("接受此卷, 已经完成所有大纲中章节列表")
        
        return "complete"

# -------------------- 大纲 -------------------- [生成 -> 验证 -> 状态判断]
def generate_outline_node(state: NovelState, outline_agent: OutlineGeneratorAgent) -> NovelState:
    """生成小说大纲的节点"""
    logger.info(f"开始生成小说大纲(第{state.attempt + 1}次尝试)")
    
    raw_outline = outline_agent.generate_outline(state)

    # 尝试提取JSON部分
    extracted_json = extract_json(raw_outline)
    if extracted_json:
        raw_outline = extracted_json
        logger.info(f"成功提取大纲JSON内容")
    
    return {
        "raw_outline": raw_outline,
        "attempt": state.attempt + 1
    }


def validate_outline_node(state: NovelState) -> NovelState:
    """验证小说大纲的节点"""
    logger.info(f"开始生成小说大纲(第{state.attempt + 1}次尝试)")
    try:
        # 解析JSON
        outline_data = json.loads(state.raw_outline)
        # 验证数据结构
        validated_outline = NovelOutline(** outline_data)
        
        # 检查角色一致性
        all_characters = set(validated_outline.characters)
        for chapter in validated_outline.chapters:
            for char in chapter.characters_involved:
                if char not in all_characters:
                    logger.info(f"【大纲】角色'{char}'不在角色列表[{validated_outline.characters}]中")
                    raise ValueError(f"章节'{chapter.title}'中出现的角色'{char}'不在角色列表[{state.validated_outline.characters}]中")
        
        if len(outline_data['chapters']) < OutlineConfig.min_chapters:
            raise ValueError(f"章节数不足，至少需要{OutlineConfig.min_chapters}个章节，实际生成了{len(outline_data.chapters)}个章节")
        state.novel_storage = NovelStorage(validated_outline.title)
        state.novel_storage.save_outline(validated_outline) 
        return {
            "novel_storage": state.novel_storage,
            "validated_outline": validated_outline,
            "attempt":0,
            "outline_validated_error": None
        }
    except json.JSONDecodeError as e:
        # 提供更详细的错误位置信息
        
        error_lines = state.raw_outline.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【大纲】 JSON格式解析错误:\n{error_msg}")
        return {"outline_validated_error": error_msg, "validated_outline": None}
    except Exception as e:
        logger.info(f"【大纲】格式验证失败: {str(e)}")
        return {"outline_validated_error": f"大纲验证失败: {str(e)}", "validated_outline": None}
 
def check_outline_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查大纲验证结果"""
    logger.info(f"检查大纲验证结果...")
    if state.outline_validated_error is None:
        logger.info(f"【大纲】success:大纲检查成功, 转移至 generate_characters 节点")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【大纲】retry:验证失败, 将进行第{state.attempt + 1}次重试...")
        return "retry"
    else:
        logger.info(f"【大纲】failure:大纲检查失败, 转移至 failure 节点")
        return "failure"
 
# -------------------- 角色档案 -------------------- [生成 -> 验证 -> 状态判断]
def generate_characters_node(state: NovelState, character_agent: CharacterAgent) -> NovelState:
    """生成详细角色档案的节点"""
    logger.info(f"正在生成角色档案(第{state.attempt + 1}次尝试)...")

    

    # 调用角色代理生成角色档案
    raw_characters = character_agent.generate_characters(state)

    # 尝试提取JSON部分
    extracted_json = extract_json( raw_characters)
    if extracted_json:
        raw_characters = extracted_json
        logger.info(f"成功提取角色列表JSON内容")
    
    # 到生成角色档案了，大纲一定创建完成了，这时候去初始化存储器
    return {
        "validated_outline":None,
        "row_characters": raw_characters,
        "attempt": state.attempt + 1
    }

def validate_characters_node(state: NovelState) -> NovelState:
    """验证角色档案格式"""
    logger.info("正在验证角色档案格式...")
    try:
        # 解析JSON
        characters_data = json.loads(state.row_characters)
        # 验证每个角色是否符合Character模型
        validated_characters = []
        for char_data in characters_data:
            try:
                character = Character(**char_data)
                validated_characters.append(character)
            except Exception as e:
                logger.info(f"【角色档案】 角色'{char_data.name}'验证失败: {str(e)}")
                return {"characters_validated_error": f"角色'{char_data.name}'验证失败: {str(e)}"}
        
        # 检查是否所有角色都已生成
        outline_characters = set(state.novel_storage.load_outline().characters)
        generated_names = set(char.name for char in validated_characters)
        missing = outline_characters - generated_names
        if missing:
            logger.info(f"【角色档案】以下角色未生成详细档案: {', '.join(missing)}")
            return {"characters_validated_error": f"以下角色未生成详细档案: {', '.join(missing)}"}
        
        # 虽然这种形式不好，但是目前不想大拆重改，先叠shit山吧
        state.novel_storage.save_characters(validated_characters)
        
        return {
            "validated_characters": validated_characters,
            "attempt":0,
            "characters_validated_error": None
        }
        
    except json.JSONDecodeError as e:
        error_lines = state.row_characters.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【角色档案】角色生成JSON格式错误")
        
        
        return {
            "characters_validated_error": error_msg
        }
    except Exception as e:
        logger.info(f"【角色档案】角色生成失败: {str(e)}")
        return {"characters_validated_error": f"角色生成失败: {str(e)}"}

def check_characters_node(state:NovelState) -> Literal["success", "retry", "failure"]:
    """检查角色档案结果"""
    logger.info(f"检查角色档案验证结果...")
    if state.characters_validated_error is None:
            
        logger.info(f"【角色档案】success:角色档案检查成功, 转移至 write_chapter 节点...")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【角色档案】retry:角色档案验证失败,  重新生成角色档案...")
        return "retry"
    else:
        logger.info(f"【角色档案】failure:角色档案验证失败, 达到最大重试次数, 结束写作...")
        return "failure"
        
# -------------------- 章节写作 -------------------- [生成 -> 验证 -> 状态判断]
def write_chapter_node(state: NovelState, writer_agent: WriterAgent) -> NovelState:
    """撰写单章内容的节点"""
    
    # 获取当前状态中的必要信息
    revision_feedback = state.validated_evaluation
    current_index = state.current_chapter_index
    outline = state.novel_storage.load_outline()
      
    # 获取当前章节大纲
    chapter_outline = outline.chapters[current_index]
    if revision_feedback:
        logger.info(f"根据反馈修改第{current_index + 1}章: {chapter_outline.title}(第{state.evaluate_attempt + 1}次修改)")
    else:
        logger.info(f"正在撰写第{current_index + 1}章: {chapter_outline.title}(第{state.attempt+1}次重写)")

    # 调用写作代理生成章节内容
    raw_chapter = writer_agent.write_chapter(state)
        
    # 提取并解析JSON
    extracted_json = extract_json(raw_chapter)
    if extracted_json:
        raw_chapter = extracted_json
        logger.info("【单章撰写】成功提取大纲JSON内容")
    return {
        "raw_current_chapter": raw_chapter,
        "attempt": state.attempt + 1,
        "evaluate_attempt": state.evaluate_attempt + 1 
    }   
    
def validate_chapter_node(state:NovelState) -> NovelState:
    
    try:
        current_chapter_index = state.current_chapter_index
        chapter_outline = state.novel_storage.load_outline().chapters[current_chapter_index]
        
        raw_current_chapter = state.raw_current_chapter
        
        # 加载当前章节内容
        chapter_data = json.loads(raw_current_chapter)
        
        # 验证章节内容
        chapter_content = ChapterContent(** chapter_data)
        
        # 确保标题一致
        if chapter_content.title != chapter_outline.title:
            logger.info(f"警告: 生成的章节标题与大纲不一致, 已自动修正")
            chapter_content.title = chapter_outline.title
        
        # 存储当前章节草稿, 等待评审
        return {
            "validated_chapter_draft": chapter_content,
            "current_chapter_index":current_chapter_index,
            "attempt":0,
            "current_chapter_validated_error": None
        }
    except json.JSONDecodeError as e:
        error_lines = state.raw_current_chapter.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【单章撰写】生成JSON格式错误")
        return {
            "current_chapter_validated_error": error_msg
        }    
    except Exception as e:
        logger.info(f"【单章撰写】章节撰写失败: {str(e)}")
        return {"current_chapter_validated_error": f"章节撰写失败: {str(e)}"}

def check_chapter_node(state:NovelState) -> Literal["success", "retry", "failure"]: # 内容结构的成功与失败, 不用于Reflect
    if state.current_chapter_validated_error is None:
        logger.info("【单章撰写】success:章节撰写成功, 转移至 evaluate_chapter 节点...")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info("【单章撰写】retry:章节撰写失败, 重新撰写")
        return "retry"
    else:
        logger.info(f"【单章撰写】failure:章节撰写失败, 达到最大重试次数, 结束流程")
        return "failure"
    
# -------------------- 评估 -------------------- [评估[生成 -> 验证 -> 状态判断] -> 状态判断]
def evaluate_chapter_node(state: NovelState, reflect_agent: ReflectAgent) -> NovelState:
    """评估章节质量的节点"""
    current_index = state.current_chapter_index
    outline = state.novel_storage.load_outline()
    # 获取当前章节大纲
    chapter_outline = outline.chapters[current_index]
    logger.info(f"正在评估第{current_index + 1}章: {chapter_outline.title}(第{state.attempt+1}次生成评估)(第{state.evaluate_attempt+1}次评估该章)")
    # 调用反思代理进行评估
    raw_evaluation = reflect_agent.evaluate_chapter(state)
    # 提取并解析JSON
    extracted_json = extract_json(raw_evaluation)
        
    if extracted_json:
        raw_evaluation = extracted_json
        logger.info(f"成功评估！")
    
    return {
        "attmept": state.attempt+1,

        "raw_chapter_evaluation": raw_evaluation
    }
    
def validate_evaluate_node(state:NovelState) -> NovelState:
    try:
        current_index = state.current_chapter_index
        
        # 尝试解析为json格式
        evalutaion_data = json.loads(state.raw_chapter_evaluation)
        
        evaluation = QualityEvaluation(**evalutaion_data)
        
        # 输出评估结果摘要
        logger.info(f"第{current_index + 1}章评估结果: 评分 {evaluation.score}/10, {'通过' if evaluation.passes else '未通过'}")
        if not evaluation.passes:
            logger.info(f"主要问题: {evaluation.overall_feedback}")
        
        return {
            "validated_evaluation" : evaluation,
            "attempt":0,
            "evaluation_validated_error": None
        }
        
    except json.JSONDecodeError as e:
        # 提供更详细的错误位置信息
        error_lines = state.raw_chapter_evaluation.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【内容评估】生成JSON格式错误")
        return {
            "evaluation_validated_error": error_msg, 
        }
    except Exception as e:
        logger.info(f"【内容评估】评估失败: {str(e)}")
        return {
            "evaluation_validated_error": f"评估失败: {str(e)}", 
        }

# 评估报告节点
def evaluate_report_node(state: NovelState, reflect_agent: ReflectAgent) -> NovelState:
    """生成评估报告的节点"""
    try:
        reflect_agent.generate_evaluation_report(state)
        logger.info(f"【内容评估】生成评估报告成功")
        return{
            "report_error":None
        }
    except Exception as e:
        logger.info(f"【内容评估】生成评估报告失败: {str(e)}")
        return {
            "report_error": f"生成评估报告失败: {str(e)}"
        }

def check_evaluation_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    # 评估内容是否有错误
    if state.evaluation_validated_error is None:
        logger.info(f"【内容评估】success:评估内容正确, 转移至 evaluate2wirter 节点...")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【内容评估】retry:评估内容失败,  重新生成评估内容...")
        return "retry"
    else:
        logger.info(f"【内容评估】failure:章节撰写失败, 达到最大重试次数, 结束流程")
        return "failure"
        
def evaluation_to_chapter_node(state:NovelState) -> NovelState:
    logger.info(f"评估内容没问题, 重写本章节:{state.validated_evaluation}")
    return {
        "attempt":0
    }

# 检查评估章节节点
def check_evaluation_chapter_node(state: NovelState) -> Literal["accept", "revise", "force_accpet"]:
    """检查章节评估结果, 决定是接受、修改还是强制接受"""
    evaluation = state.validated_evaluation
    if evaluation.passes:
        logger.info(f"当前第{state.current_chapter_index+1}章<{state.validated_chapter_draft.title}>通过")
        return "accept"  
    elif state.evaluate_attempt < state.max_attempts:
        logger.info(f"当前第{state.current_chapter_index+1}章<{state.validated_chapter_draft.title}>, 接受修改意见, 重写本章")
        return "revise"
    else:
        logger.info(f"达到验证的最大次数, 强制接受本章")
        return "force_accpet"

# ---------------------- 实体识别 ---------------------- [生成 -> 验证 -> 状态判断]
def generate_entities_node(state: NovelState, entity_agent: EntityAgent) -> NovelState:
    """生成实体列表的节点"""
    logger.info(f"正在生成实体列表(第{state.attempt + 1}次尝试)...")
    raw_entities = entity_agent.generate_entities(state)
    # 提取并解析JSON
    extracted_json = extract_json(raw_entities)
    if extracted_json:
        raw_entities = extracted_json
        logger.info("【实体识别】成功提取大纲JSON内容")

    
    return {
        "attempt": state.attempt + 1,
        "raw_entities": raw_entities
    }

def validate_entities_node(state: NovelState) -> NovelState:
    """验证实体列表格式"""
    logger.info("正在验证实体列表格式...")
    try:
        entities_data = json.loads(state.raw_entities)
        entities = EntityContent(**entities_data)
        
        logger.info(f"第{state.current_chapter_index + 1}章实体加载完成")
        # 存储实体文件到对应章节
        state.novel_storage.save_entity(state.current_chapter_index,entities)
        return {
            "attempt": 0,
            "entities_validated_error": None
        }
    except json.JSONDecodeError as e:
        error_lines = state.raw_entities.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行, 第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        logger.info(f"【实体识别】生成JSON格式错误")
        return {
            "entities_validated_error": error_msg
        }
    except Exception as e:
        logger.info(f"【实体识别】实体生成失败: {str(e)}")
        return {
            "entities_validated_error": f"实体生成失败: {str(e)}"
        }

def check_entities_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查实体列表生成结果"""
    if state.entities_validated_error is None:
        logger.info(f"【实体识别】success:实体列表生成成功, 转移至 write_entities 节点...")
        return "success"
    elif state.attempt < state.max_attempts:
        logger.info(f"【实体识别】retry:实体列表生成失败,  重新生成实体列表...")
        return "retry"
    else:
        logger.info(f"【实体识别】failure:实体列表生成失败, 达到最大重试次数, 结束流程")
        return "failure"
    
# 接受章节节点
def accept_chapter_node(state: NovelState) -> NovelState:
    """接受章节, 将其添加到章节列表并准备处理下一章节"""
    current_draft = state.validated_chapter_draft
    current_index = state.current_chapter_index
    

    state.novel_storage.save_chapter(chapter_index=current_index+1, chapter= current_draft)
    logger.info(f"章节{current_index+1}已接受, 已添加到本地")
    # 重置章节相关状态, 准备处理下一章节
    return {
        "current_chapter_index": current_index + 1,
        "evaluate_attempt":0,
        "validated_chapter_draft": None,
        "validated_evaluation": None
    }


def check_chapter_completion_node(state: NovelState) -> Literal["continue", "complete"]:
    """检查是否所有章节都已撰写完成"""
    
    total_chapters = len(state.novel_storage.load_outline().chapters)
    current_index = state.current_chapter_index
    
    if current_index < total_chapters:
        state.attempt = 0
        logger.info("接受章节, 将其添加到章节列表并准备处理下一章节")
        return "continue"
    else:
        logger.info("接受章节, 已经完成所有章节写作")
        return "complete"
