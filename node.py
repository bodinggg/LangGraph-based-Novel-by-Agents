import json

from model import *
from agent import * 
from tool import extract_json
from typing import Literal


# -------------------- 大纲 -------------------- [生成 -> 验证 -> 状态判断]
def generate_outline_node(state: NovelState, outline_agent: OutlineGeneratorAgent) -> NovelState:
    """生成小说大纲的节点"""
    print(f"正在生成小说大纲（第{state.attempt + 1}次尝试）...")
    
    raw_outline = outline_agent.generate_outline(state)
    
    # 尝试提取JSON部分
    extracted_json = extract_json(raw_outline)
    if extracted_json:
        raw_outline = extracted_json
        print(f"成功提取大纲JSON内容：{raw_outline}")
    
    return {
        "raw_outline": raw_outline,
        "attempt": state.attempt + 1
    }

def validate_outline_node(state: NovelState) -> NovelState:
    """验证小说大纲的节点"""
    print("正在验证小说大纲格式...")
    try:
        # 解析JSON
        outline_data = json.loads(state.raw_outline)
        
        # 验证数据结构
        validated_outline = NovelOutline(** outline_data)
        print(f"[test] validated_outline is {validated_outline}")
        # 检查角色一致性
        all_characters = set(validated_outline.characters)
        for chapter in validated_outline.chapters:
            for char in chapter.characters_involved:
                if char not in all_characters:
                    raise ValueError(f"章节'{chapter.title}'中出现的角色'{char}'不在角色列表中")
        
        return {
            "validated_outline": validated_outline,
            "attempt":0,
            "outline_validated_error": None
        }
    except json.JSONDecodeError as e:
        # 提供更详细的错误位置信息
        print(f"【大纲】 JSON格式解析错误：\n")
        error_lines = state.raw_outline.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行，第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        return {"outline_validated_error": error_msg, "validated_outline": None}
    except Exception as e:
        print(f"【大纲】格式验证失败: {str(e)}")
        return {"outline_validated_error": f"大纲验证失败: {str(e)}", "validated_outline": None}
 
def check_outline_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    """检查大纲验证结果"""
    print(f"检查大纲验证结果...")
    if state.outline_validated_error is None:
        print(f"【大纲】success：大纲检查成功，转移至 generate_characters 节点")
        return "success"
    elif state.attempt < state.max_attempts:
        print(f"【大纲】retry：验证失败，将进行第{state.attempt + 1}次重试...")
        return "retry"
    else:
        print(f"【大纲】failure：大纲检查失败，转移至 failure 节点")
        return "failure"
 
# -------------------- 角色档案 -------------------- [生成 -> 验证 -> 状态判断]
def generate_characters_node(state: NovelState, character_agent: CharacterAgent) -> NovelState:
    """生成详细角色档案的节点"""
    print(f"正在生成角色档案（第{state.attempt + 1}次尝试）...")

    # 调用角色代理生成角色档案
    raw_characters = character_agent.generate_characters(state)

    # 尝试提取JSON部分
    extracted_json = extract_json( raw_characters)
    if extracted_json:
        raw_characters = extracted_json
        print(f"成功提取角色列表JSON内容")
        
    return {
        "row_characters": raw_characters,
        "attempt": state.attempt + 1
    }

def validate_characters_node(state: NovelState) -> NovelState:
    """验证角色档案格式"""
    print("正在验证角色档案格式...")
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
                print(f"【角色档案】 角色'{char_data.name}'验证失败: {str(e)}")
                return {"characters_validated_error": f"角色'{char_data.name}'验证失败: {str(e)}"}
        
        # 检查是否所有角色都已生成
        outline_characters = set(state.validated_outline.characters)
        generated_names = set(char.name for char in validated_characters)
        missing = outline_characters - generated_names
        if missing:
            print(f"警告: 以下角色未生成详细档案: {', '.join(missing)}")
            return {"characters_validated_error": f"以下角色未生成详细档案: {', '.join(missing)}"}
        
        return {
            "validated_characters": validated_characters,
            "attempt":0,
            "characters_validated_error": None
        }
        
    except json.JSONDecodeError as e:
        error_lines = state.raw_outline.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行，第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        print(f"【角色档案】角色生成JSON格式错误")
        return {
            "characters_validated_error": error_msg
        }
    except Exception as e:
        print(f"【角色档案】角色生成失败: {str(e)}")
        return {"characters_validated_error": f"角色生成失败: {str(e)}"}

def check_characters_node(state:NovelState) -> Literal["success", "retry", "failure"]:
    """检查角色档案结果"""
    print(f"检查角色档案验证结果...")
    if state.characters_validated_error is None:
        print(f"【角色档案】success：角色档案检查成功，转移至 write_chapter 节点...")
        return "success"
    elif state.attempt < state.max_attempts:
        print(f"【角色档案】retry：角色档案验证失败， 重新生成角色档案...")
        return "retry"
    else:
        print(f"【角色档案】failure：角色档案验证失败，达到最大重试次数，结束写作...")
        return "failure"
        
# -------------------- 章节写作 -------------------- [生成 -> 验证 -> 状态判断]
def write_chapter_node(state: NovelState, writer_agent: WriterAgent) -> NovelState:
    """撰写单章内容的节点"""
    
    # 获取当前状态中的必要信息
    revision_feedback = state.validated_evaluation
    current_index = state.current_chapter_index
    outline = state.validated_outline
      
    # 获取当前章节大纲
    chapter_outline = outline.chapters[current_index]
    if revision_feedback:
        print(f"根据反馈修改第{current_index + 1}章: {chapter_outline.title}（第{state.evaluate_attempt + 1}次修改）")
    else:
        print(f"正在撰写第{current_index + 1}章: {chapter_outline.title}")

    # 调用写作代理生成章节内容
    raw_chapter = writer_agent.write_chapter(state)
        
    # 提取并解析JSON
    extracted_json = extract_json(raw_chapter)
    if extracted_json:
        raw_chapter = extracted_json
        print("【单章撰写】成功提取大纲JSON内容")
    return {
        "raw_current_chapter": raw_chapter,
        "attempt": state.attempt + 1,
        "evaluate_attempt": state.evaluate_attempt + 1 
    }   
    
def validate_chapter_node(state:NovelState) -> NovelState:
    
    try:
        current_chapter_index = state.current_chapter_index
        chapter_outline = state.validated_outline.chapters[current_chapter_index]
        
        raw_current_chapter = state.raw_current_chapter
        
        # 加载当前章节内容
        chapter_data = json.loads(raw_current_chapter)
        
        # 验证章节内容
        chapter_content = ChapterContent(** chapter_data)
        
        # 确保标题一致
        if chapter_content.title != chapter_outline.title:
            print(f"警告: 生成的章节标题与大纲不一致，已自动修正")
            chapter_content.title = chapter_outline.title
        
        # 存储当前章节草稿，等待评审
        return {
            "validated_chapter_draft": chapter_content,
            "attempt":0,
            "current_chapter_validated_error": None
        }
    except json.JSONDecodeError as e:
        error_lines = state.raw_outline.split('\n')
        error_line = min(e.lineno - 1, len(error_lines) - 1) if e.lineno else 0
        context = "\n".join(error_lines[max(0, error_line - 2):min(len(error_lines), error_line + 3)])
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行，第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        print(f"【单章撰写】生成JSON格式错误")
        return {
            "current_chapter_validated_error": error_msg
        }    
    except Exception as e:
        print()
        return {"current_chapter_validated_error": f"章节撰写失败: {str(e)}"}

def check_chapter_node(state:NovelState) -> Literal["success", "retry", "failure"]: # 内容结构的成功与失败，不用于Reflect
    if state.current_chapter_validated_error is None:
        print("success：章节攥写完成，等待评估...")
        return "success"
    elif state.attempt < state.max_attempts:
        print("retry：章节撰写失败，重新撰写")
        return "retry"
    else:
        print(f"failure：章节撰写失败，达到最大重试次数，结束流程")
        return "failure"
    
# -------------------- 评估 -------------------- [评估[生成 -> 验证 -> 状态判断] -> 状态判断]
def evaluate_chapter_node(state: NovelState, reflect_agent: ReflectAgent) -> NovelState:
    """评估章节质量的节点"""
    current_index = state.current_chapter_index
    outline = state.validated_outline
    # 获取当前章节大纲
    chapter_outline = outline.chapters[current_index]
    print(f"正在评估第{current_index + 1}章: {chapter_outline.title}")
    # 调用反思代理进行评估
    raw_evaluation = reflect_agent.evaluate_chapter(state)
    # 提取并解析JSON
    extracted_json = extract_json(raw_evaluation)
        
    if extracted_json:
        raw_evaluation = extracted_json
        print(f"成功评估！")
    
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
        print(f"第{current_index + 1}章评估结果: 评分 {evaluation.score}/10, {'通过' if evaluation.passes else '未通过'}")
        if not evaluation.passes:
            print(f"主要问题: {evaluation.feedback[:100]}...")
        
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
        
        error_msg = (f"JSON解析错误: 在第{e.lineno}行，第{e.colno}列 - {str(e)}\n"
                    f"错误位置附近内容:\n{context}\n"
                    "请检查括号是否匹配、是否使用双引号、逗号是否正确。")
        return {
            "evaluation_validated_error": error_msg, 
        }
    except Exception as e:
        return {
            "evaluation_validated_error": f"评估失败: {str(e)}", 
        }


def check_evaluation_node(state: NovelState) -> Literal["success", "retry", "failure"]:
    # 评估内容是否有错误
    if state.evaluation_validated_error is None:
        return "success"
    elif state.attempt < state.max_attempts:
        return "retry"
    else:
        return "failure"
        
def evaluation_to_chapter_node(state:NovelState) -> NovelState:
    print(f"评估内容没问题，重写本章节:{state.validated_evaluation}")
    return {
        "attempt":0
    }

# 检查评估章节节点
def check_evaluation_chapter_node(state: NovelState) -> Literal["accept", "revise", "force_accpet"]:
    """检查章节评估结果，决定是接受、修改还是强制接受"""
    evaluation = state.validated_evaluation
    if evaluation.passes:
        return "accept"  # 如果没有评估结果，强制接受
    elif state.evaluate_attempt < state.max_attempts:
        return "revise"
    else:
        return "force_accpet"


# 接受章节节点
def accept_chapter_node(state: NovelState) -> NovelState:
    """接受章节，将其添加到章节列表并准备处理下一章节"""
    chapters_content = state.chapters_content
    current_draft = state.validated_chapter_draft
    current_index = state.current_chapter_index
    print("接受章节，将其添加到章节列表并准备处理下一章节")
    # 将当前草稿添加到章节列表
    chapters_content.append(current_draft)
    
    # 重置章节相关状态，准备处理下一章节
    return {
        "chapters_content": chapters_content,
        "current_chapter_index": current_index + 1,
        "evaluate_attempt":0,
        "validated_chapter_draft": None,
        "validated_evaluation": None
    }


def check_chapter_completion_node(state: NovelState) -> Literal["continue", "complete"]:
    """检查是否所有章节都已撰写完成"""
    
    total_chapters = len(state.validated_outline.chapters)
    current_index = state.current_chapter_index
    
    if current_index < total_chapters:
        state.attempt = 0
        return "continue"
    else:
        return "complete"
