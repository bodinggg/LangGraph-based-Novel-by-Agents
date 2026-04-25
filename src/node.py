import json
import asyncio
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
from src.client_pool import get_current_client_id

logger = loggers['node']
        

# -------------------- 大纲(分卷) -------------------- [生成 -> 验证 -> 状态判断]
def generate_master_outline_node(state: NovelState, outline_agent:OutlineGeneratorAgent) -> NovelState:
    # 如果已有验证通过的大纲（分卷模式），跳过生成
    if state.validated_outline is not None:
        logger.info("已有验证通过的分卷大纲，跳过生成步骤")
        return {
            "novel_storage": state.novel_storage,
            "raw_master_outline": state.raw_master_outline,
            "validated_outline": state.validated_outline,
            "attempt": 0,
            "outline_validated_error": None
        }

    logger.info(f"开始分卷生成小说大纲(第{state.attempt + 1}次尝试)")
    raw_master = outline_agent.generate_master_outline(state.user_intent)
    extracted_json = extract_json(raw_master)
    if extracted_json:
        raw_master = extracted_json
        logger.info(f"【分卷】成功提取大纲JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("【分卷】大纲JSON提取失败，内容可能被截断")
        return {
            "raw_master_outline": raw_master,
            "outline_validated_error": "大纲JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1
        }
    return {
        "raw_master_outline": raw_master,
        "attempt":state.attempt+1
    }
    
def validate_master_outline_node(state: NovelState) -> NovelState:
    # 如果已有验证通过的大纲，跳过验证（从存储恢复时）
    if state.validated_outline is not None and state.outline_validated_error is None:
        logger.info("已有验证通过的分卷大纲，跳过验证步骤")
        return {
            "novel_storage": state.novel_storage,
            "validated_outline": state.validated_outline,
            "outline_validated_error": None,
            "attempt": 0,
        }

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
    # 如果已有完整的大纲章节列表，跳过卷章节生成（从存储恢复时）
    # 计算 master_outline 中所有卷的章节总数
    if state.validated_outline is not None and state.validated_outline.master_outline is not None:
        total_expected = 0
        for vol in state.validated_outline.master_outline:
            start_idx, end_idx = map(int, vol.chapters_range.split('-'))
            total_expected += (end_idx - start_idx + 1)
        if len(state.validated_outline.chapters) >= total_expected:
            logger.info(f"所有卷章节已生成（共{len(state.validated_outline.chapters)}章），跳过卷章节生成")
            return {
                "novel_storage": state.novel_storage,
                "current_volume_index": len(state.validated_outline.master_outline),
                "validated_chapters": [],
                "raw_volume_chapters": None,
                "attempt": 0
            }

    logger.info(f"开始分章生成卷{state.current_volume_index+1}小说大纲(第{state.attempt + 1}次尝试)")
    volume_index = state.current_volume_index
    raw_chapters = outline_agent.generate_volume_chapters(state, volume_index)
    extracted_json = extract_json(raw_chapters)
    if extracted_json:
        raw_chapters = extracted_json
        logger.info(f"【分章】成功提取大纲JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("【分章】大纲JSON提取失败，内容可能被截断")
        return {
            "raw_volume_chapters": raw_chapters,
            "outline_validated_error": "分章大纲JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1
        }
    return {
        "raw_volume_chapters": raw_chapters,
        "attempt":state.attempt+1
    }

def validate_volume_outline_node(state:NovelState) -> NovelState:
    # 如果 raw_volume_chapters 为 None，说明已跳过卷章节生成（从存储恢复时）
    if state.raw_volume_chapters is None:
        logger.info("卷章节已全部生成，跳过验证步骤")
        return {
            "novel_storage": state.novel_storage,
            "validated_chapters": [],
            "outline_validated_error": None,
            "attempt": 0
        }

    logger.info(f"开始分章验证卷{state.current_volume_index+1}小说大纲(第{state.attempt}次尝试)")
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
    return {
        "novel_storage": state.novel_storage,
        "attempt": 0
    }


# 判断大纲是否创建结束
# 接受章节节点
def accept_outline_node(state: NovelState) -> NovelState:
    """接受当前卷, 将其添加到大纲中章节列表并准备处理下一卷"""
    # 合并到总章节列表 (immutable - create new object)
    chapters = state.validated_chapters
    validated_outline = state.validated_outline
    updated_chapters = validated_outline.chapters + chapters
    validated_outline = validated_outline.model_copy(update={"chapters": updated_chapters})
    current_volume_index = state.current_volume_index
    next_volume_index = current_volume_index + 1

    # 最后一卷时保存大纲和元数据（不改变 novel_storage 的类型）
    if current_volume_index == len(validated_outline.master_outline) - 1:
        state.novel_storage = NovelStorage(validated_outline.title)
        state.novel_storage.save_outline(validated_outline)
        state.novel_storage.save_outline_metadata(next_volume_index, len(updated_chapters))

    # 重置卷相关状态, 准备处理下一卷
    return {
        "novel_storage": state.novel_storage,
        "validated_outline": validated_outline,
        "current_volume_index": next_volume_index,
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
    # 如果已有验证通过的大纲，跳过生成（从存储恢复时）
    if state.validated_outline is not None:
        logger.info("已有验证通过的大纲，跳过生成步骤")
        return {
            "raw_outline": state.raw_outline or "",
            "validated_outline": state.validated_outline,
            "attempt": 0,
            "outline_validated_error": None
        }

    logger.info(f"开始生成小说大纲(第{state.attempt + 1}次尝试)")

    raw_outline = outline_agent.generate_outline(state)

    # 尝试提取JSON部分
    extracted_json = extract_json(raw_outline)
    if extracted_json:
        raw_outline = extracted_json
        logger.info(f"成功提取大纲JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("大纲JSON提取失败，内容可能被截断")
        return {
            "raw_outline": raw_outline,
            "outline_validated_error": "大纲JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1
        }

    return {
        "raw_outline": raw_outline,
        "attempt": state.attempt + 1
    }


def validate_outline_node(state: NovelState) -> NovelState:
    """验证小说大纲的节点"""
    # 如果已有验证通过的大纲，跳过验证（从存储恢复时）
    if state.validated_outline is not None and state.outline_validated_error is None:
        logger.info("已有验证通过的大纲，跳过验证步骤")
        return {
            "validated_outline": state.validated_outline,
            "attempt": 0,
            "outline_validated_error": None
        }

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
        
        if len(outline_data['chapters']) < state.min_chapters:
            raise ValueError(f"章节数不足，至少需要{state.min_chapters}个章节，实际生成了{len(outline_data.chapters)}个章节")
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
    # 如果已有验证通过的角色，跳过生成（从存储恢复时）
    if state.validated_characters is not None and len(state.validated_characters) > 0:
        logger.info("已有验证通过的角色，跳过生成步骤")
        return {
            "novel_storage": state.novel_storage,
            "validated_characters": state.validated_characters,
            "attempt": 0,
            "characters_validated_error": None
        }

    logger.info(f"正在生成角色档案(第{state.attempt + 1}次尝试)...")
    # 调用角色代理生成角色档案
    raw_characters = character_agent.generate_characters(state)

    # 尝试提取JSON部分
    extracted_json = extract_json(raw_characters)
    if extracted_json:
        raw_characters = extracted_json
        logger.info(f"成功提取角色列表JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("角色档案JSON提取失败，内容可能被截断")
        return {
            "validated_outline": None,
            "row_characters": raw_characters,
            "characters_validated_error": "角色档案JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1
        }

    # 到生成角色档案了，大纲一定创建完成了，这时候去初始化存储器
    return {
        "validated_outline":None,
        "row_characters": raw_characters,
        "attempt": state.attempt + 1
    }

def validate_characters_node(state: NovelState) -> NovelState:
    """验证角色档案格式"""
    # 如果已有验证通过的角色，跳过验证（从存储恢复时）
    if state.validated_characters is not None and len(state.validated_characters) > 0 and state.characters_validated_error is None:
        logger.info("已有验证通过的角色，跳过验证步骤")
        return {
            "novel_storage": state.novel_storage,
            "validated_characters": state.validated_characters,
            "attempt": 0,
            "characters_validated_error": None
        }

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
        logger.info("【单章撰写】成功提取章节JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("【单章撰写】章节JSON提取失败，内容可能被截断")
        return {
            "raw_current_chapter": raw_chapter,
            "current_chapter_validated_error": "章节JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1,
            "evaluate_attempt": state.evaluate_attempt + 1
        }
    return {
        "raw_current_chapter": raw_chapter,
        "attempt": state.attempt + 1,
        "evaluate_attempt": state.evaluate_attempt + 1
    }


async def async_write_chapter_node(state: NovelState, writer_agent: WriterAgent) -> NovelState:
    """异步撰写单章内容的节点（用于并行模式）"""

    revision_feedback = state.validated_evaluation
    current_index = state.current_chapter_index

    outline = state.novel_storage.load_outline()

    chapter_outline = outline.chapters[current_index]
    if revision_feedback:
        logger.info(f"[ASYNC] 根据反馈修改第{current_index + 1}章: {chapter_outline.title}(第{state.evaluate_attempt + 1}次修改)")
    else:
        logger.info(f"[ASYNC] 正在撰写第{current_index + 1}章: {chapter_outline.title}(第{state.attempt+1}次重写)")

    # 调用异步写作代理生成章节内容
    raw_chapter = await writer_agent.async_write_chapter(state)

    # 提取并解析JSON
    extracted_json = extract_json(raw_chapter)
    if extracted_json:
        raw_chapter = extracted_json
        logger.info("【异步单章撰写】成功提取章节JSON内容")
    else:
        logger.info("【异步单章撰写】章节JSON提取失败，内容可能被截断")
        return {
            "raw_current_chapter": raw_chapter,
            "current_chapter_validated_error": "章节JSON提取失败，内容可能被截断，请重试",
            "attempt": state.attempt + 1,
            "evaluate_attempt": state.evaluate_attempt + 1
        }
    return {
        "raw_current_chapter": raw_chapter,
        "attempt": state.attempt + 1,
        "evaluate_attempt": state.evaluate_attempt + 1
    }


def batch_write_chapters_node(state: NovelState, writer_agent: WriterAgent) -> NovelState:
    """批量撰写多章内容的节点（用于并行模式）

    根据当前章节索引和批次大小，并行生成多个章节
    """
    current_index = state.current_chapter_index
    batch_size = getattr(state, 'batch_size', 3)  # 默认批次大小为3

    outline = state.novel_storage.load_outline()
    total_chapters = len(outline.chapters)

    # 计算本次批次的章节范围
    start_idx = current_index
    end_idx = min(current_index + batch_size, total_chapters)

    logger.info(f"[BATCH] 开始批量撰写章节 {start_idx + 1} ~ {end_idx}，共 {end_idx - start_idx} 章")

    # 获取待写章节的大纲
    chapters_to_write = []
    for i in range(start_idx, end_idx):
        chapters_to_write.append({
            "index": i,
            "outline": outline.chapters[i]
        })

    # 批量生成
    async def write_one(idx: int, ch_outline):
        try:
            logger.info(f"[BATCH] 异步撰写第{idx + 1}章: {ch_outline.title}")
            # 创建临时状态（每个章节独立状态，避免污染）
            temp_state = state.model_copy()
            temp_state.current_chapter_index = idx
            # 重置评估相关字段 - 批量新章节不需要revision反馈
            temp_state.validated_evaluation = None
            temp_state.validated_chapter_draft = None
            temp_state.evaluate_attempt = 0
            temp_state.current_chapter_validated_error = None
            result = await writer_agent.async_write_chapter(temp_state)
            # 记录该章节使用的客户端 ID
            client_id = get_current_client_id()
            logger.info(f"[BATCH WRITE] 章节 {idx + 1} ({ch_outline.title}) 使用 {client_id}")
            return result
        except Exception as e:
            logger.error(f"[BATCH] 第{idx + 1}章撰写失败: {e}")
            return f'{{"error": "第{idx + 1}章撰写失败: {str(e)}"}}'

    async def run_batch():
        tasks = [write_one(ch["index"], ch["outline"]) for ch in chapters_to_write]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    # 同步执行异步批量任务
    results = asyncio.run(run_batch())

    # 处理结果
    batch_results = []
    for i, result in enumerate(results):
        # 处理异常情况
        if isinstance(result, Exception):
            logger.error(f"[BATCH] 第{start_idx + i + 1}章生成异常: {result}")
            batch_results.append({
                "chapter_index": start_idx + i,
                "raw_chapter": f'{{"error": "第{start_idx + i + 1}章生成异常: {str(result)}"}}',
                "success": False,
                "error": str(result)
            })
            continue

        raw_chapter = result
        if isinstance(raw_chapter, Exception):
            raw_chapter = str(raw_chapter)

        logger.info(f"[BATCH DEBUG] 第{start_idx + i + 1}章原始响应前200字符: {str(raw_chapter)[:200]}")
        extracted_json = extract_json(raw_chapter)
        logger.info(f"[BATCH DEBUG] 第{start_idx + i + 1}章extract_json结果: {str(extracted_json)[:200] if extracted_json else 'None'}")
        if extracted_json:
            batch_results.append({
                "chapter_index": start_idx + i,
                "raw_chapter": extracted_json,
                "success": True
            })
        else:
            # 保存原始响应（用于调试）和错误信息
            batch_results.append({
                "chapter_index": start_idx + i,
                "raw_chapter": raw_chapter,
                "raw_response_preview": str(raw_chapter)[:500] if raw_chapter else "空响应",
                "success": False,
                "error": "章节JSON提取失败，内容可能被截断"
            })
            logger.info(f"[BATCH] 第{start_idx + i + 1}章JSON提取失败，将原始响应保存用于调试")

    # 更新状态
    update = {
        "batch_results": batch_results,
        "batch_start_index": start_idx,
        "batch_end_index": end_idx - 1,
    }

    # 检查是否有失败的
    failed = [r for r in batch_results if not r["success"]]
    if failed:
        update["current_chapter_validated_error"] = f"批量中{failed[0]['chapter_index'] + 1}章JSON提取失败"

    return update   
    
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
        logger.info(f"成功提取评估JSON内容！")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("评估JSON提取失败，内容可能被截断")
        return {
            "attmept": state.attempt + 1,
            "raw_chapter_evaluation": raw_evaluation,
            "evaluation_validated_error": "评估JSON提取失败，内容可能被截断，请重试"
        }

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
            "novel_storage": state.novel_storage,
            "report_error":None
        }
    except Exception as e:
        logger.info(f"【内容评估】生成评估报告失败: {str(e)}")
        return {
            "novel_storage": state.novel_storage,
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
        "novel_storage": state.novel_storage,
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
        logger.info("【实体识别】成功提取实体JSON内容")
    else:
        # JSON提取失败（可能截断），返回错误以触发重试
        logger.info("【实体识别】实体JSON提取失败，内容可能被截断")
        return {
            "novel_storage": state.novel_storage,
            "attempt": state.attempt + 1,
            "raw_entities": raw_entities,
            "entities_validated_error": "实体JSON提取失败，内容可能被截断，请重试"
        }

    return {
        "novel_storage": state.novel_storage,
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
            "novel_storage": state.novel_storage,
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
            "novel_storage": state.novel_storage,
            "entities_validated_error": error_msg
        }
    except Exception as e:
        logger.info(f"【实体识别】实体生成失败: {str(e)}")
        return {
            "novel_storage": state.novel_storage,
            "entities_validated_error": f"实体生成失败: {str(e)}"
        }


async def async_generate_entities_node(state: NovelState, entity_agent: EntityAgent) -> NovelState:
    """异步生成实体列表的节点（用于并行模式）"""
    logger.info(f"[ASYNC] 正在生成第{state.current_chapter_index + 1}章实体列表(第{state.attempt + 1}次尝试)...")
    raw_entities = await entity_agent.async_generate_entities(state)

    extracted_json = extract_json(raw_entities)
    if extracted_json:
        raw_entities = extracted_json
        logger.info("【异步实体识别】成功提取实体JSON内容")
    else:
        logger.info("【异步实体识别】实体JSON提取失败，内容可能被截断")
        return {
            "novel_storage": state.novel_storage,
            "attempt": state.attempt + 1,
            "raw_entities": raw_entities,
            "entities_validated_error": "实体JSON提取失败，内容可能被截断，请重试"
        }

    return {
        "novel_storage": state.novel_storage,
        "attempt": state.attempt + 1,
        "raw_entities": raw_entities
    }


def batch_generate_entities_node(state: NovelState, entity_agent: EntityAgent) -> NovelState:
    """批量生成实体列表的节点（用于并行模式）

    根据批次结果，批量提取多个章节的实体
    """
    batch_results = getattr(state, 'batch_results', [])
    if not batch_results:
        logger.info("[BATCH] 无批次结果，跳过批量实体生成")
        return {"novel_storage": state.novel_storage}

    logger.info(f"[BATCH] 开始批量生成实体，共 {len(batch_results)} 章")

    async def generate_one(chapter_index: int, raw_chapter: str):
        logger.info(f"[BATCH] 异步生成第{chapter_index + 1}章实体")
        # 创建临时状态
        chapter_content = extract_json(raw_chapter)
        if chapter_content:
            try:
                content_dict = json.loads(chapter_content) if isinstance(chapter_content, str) else chapter_content
                temp_state = state.model_copy()
                temp_state.current_chapter_index = chapter_index
                temp_state.validated_chapter_draft = ChapterContent(**content_dict)
                return await entity_agent.async_generate_entities(temp_state)
            except Exception as e:
                logger.info(f"[BATCH] 第{chapter_index + 1}章实体生成失败: {e}")
                return None
        return None

    async def run_batch():
        tasks = [generate_one(r["chapter_index"], r["raw_chapter"]) for r in batch_results if r.get("success")]
        return await asyncio.gather(*tasks)

    # 同步执行异步批量任务
    results = asyncio.run(run_batch())

    # 处理结果
    entity_results = []
    for i, raw_entities in enumerate(results):
        if raw_entities:
            extracted = extract_json(raw_entities)
            if extracted:
                entity_results.append({
                    "chapter_index": batch_results[i]["chapter_index"] if i < len(batch_results) else i,
                    "raw_entities": extracted,
                    "success": True
                })
            else:
                entity_results.append({
                    "chapter_index": batch_results[i]["chapter_index"] if i < len(batch_results) else i,
                    "success": False,
                    "error": "实体JSON提取失败"
                })

    return {
        "batch_entity_results": entity_results,
        "novel_storage": state.novel_storage,
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
        "novel_storage": state.novel_storage,
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


# -------------------- 执行模式路由节点 --------------------
def route_to_writing_node(state: NovelState) -> NovelState:
    """路由到串行或并行写作节点"""
    logger.info(f"[ROUTING] 执行模式: {state.execution_mode}")
    return {
        "novel_storage": state.novel_storage,
        "execution_mode": state.execution_mode
    }


def check_execution_mode_node(state: NovelState) -> Literal["serial", "parallel"]:
    """检查执行模式，决定路由到串行还是并行写作"""
    mode = getattr(state, 'execution_mode', 'serial')
    logger.info(f"[MODE CHECK] 执行模式: {mode}")
    return mode


def batch_validate_chapters_node(state: NovelState) -> NovelState:
    """批量验证章节节点 - 验证并保存批量生成的章节

    批量模式流程：
    1. batch_write_chapters 并行生成多个章节
    2. batch_validate_chapters 验证并保存所有章节
    3. 根据模式决定下一步：serial模式继续串行评估，parallel模式批量评估
    """
    batch_results = getattr(state, 'batch_results', None)
    if batch_results is None:
        logger.info("[BATCH VALIDATE] 无批次结果，跳过")
        return {
            "novel_storage": state.novel_storage,
            "current_chapter_validated_error": "无批次结果"
        }

    logger.info(f"[BATCH VALIDATE] 开始验证并保存 {len(batch_results)} 个章节")

    saved_count = 0
    errors = []
    batch_chapters = []  # 本批次验证通过的章节列表，供UI批量显示

    for result in batch_results:
        chapter_index = result.get("chapter_index", 0)
        raw_chapter = result.get("raw_chapter", "")
        success = result.get("success", False)

        logger.info(f"[BATCH VALIDATE DEBUG] 第 {chapter_index + 1} 章: success={success}, raw_chapter前100字符={str(raw_chapter)[:100]}")

        try:
            chapter_data = json.loads(raw_chapter)
            chapter_content = ChapterContent(**chapter_data)

            # 保存章节
            state.novel_storage.save_chapter(chapter_index + 1, chapter_content)
            saved_count += 1
            batch_chapters.append(chapter_content)  # 收集验证通过的章节
            logger.info(f"[BATCH VALIDATE] 第 {chapter_index + 1} 章保存成功")
        except json.JSONDecodeError as e:
            errors.append(f"第 {chapter_index + 1} 章 JSON 解析失败: {str(e)}")
            logger.info(f"[BATCH VALIDATE] 第 {chapter_index + 1} 章 JSON 解析失败: {str(e)[:100]}")
        except Exception as e:
            errors.append(f"第 {chapter_index + 1} 章保存失败: {str(e)}")
            logger.info(f"[BATCH VALIDATE] 第 {chapter_index + 1} 章保存失败: {e}")

    # 计算下一章节索引
    last_index = batch_results[-1].get("chapter_index", 0) if batch_results else 0
    next_chapter_index = last_index + 1

    logger.info(f"[BATCH VALIDATE] 批量完成：成功 {saved_count}/{len(batch_results)} 章，返回 batch_chapters 共 {len(batch_chapters)} 章")

    update = {
        "novel_storage": state.novel_storage,
        "current_chapter_index": next_chapter_index,
        "evaluate_attempt": 0,
        "validated_chapter_draft": batch_chapters[-1] if batch_chapters else None,  # 最后一个章节
        "batch_chapters": batch_chapters,  # 本批次所有章节，供UI批量加载
        "validated_evaluation": None,
        "batch_results": None,  # 清除批次结果，避免状态污染
    }

    if errors:
        update["current_chapter_validated_error"] = errors[0]

    return update


def check_batch_completion_node(state: NovelState) -> Literal["continue_serial", "continue_parallel", "complete"]:
    """检查批量章节完成情况，决定下一步

    Returns:
        - continue_serial: 写作完成，进入串行评估流程
        - continue_parallel: 并行模式，继续下一批写作
        - complete: 所有章节完成（串行模式直接完成）
    """
    total_chapters = len(state.novel_storage.load_outline().chapters)
    current_index = state.current_chapter_index
    batch_results = getattr(state, 'batch_results', [])

    logger.info(f"[BATCH CHECK] 当前第 {current_index + 1} 章 / 共 {total_chapters} 章，执行模式: {state.execution_mode}，batch_results: {len(batch_results) if batch_results else 'None'}")

    # 如果当前批次没有结果，说明可能已经完成或出错
    if not batch_results and current_index > 0:
        logger.info("[BATCH CHECK] 无批次结果但已有进度，检查是否完成")

    # 检查是否所有章节已完成写作
    if current_index >= total_chapters:
        logger.info(f"[BATCH CHECK] ✅ 所有章节写作完成 (current={current_index}, total={total_chapters})，返回 complete")
        return "complete"  # 并行模式完成

    # 根据执行模式决定路由
    if state.execution_mode == "parallel":
        logger.info("[BATCH CHECK] 并行模式，继续下一批写作")
        return "continue_parallel"
    else:
        logger.info("[BATCH CHECK] 串行模式，回到串行评估流程")
        return "continue_serial"
