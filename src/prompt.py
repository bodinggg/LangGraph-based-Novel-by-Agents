"""
定义工作状态, 核心部分
"""
from typing import Dict
from langgraph.graph import StateGraph, END
from src.agent import (
    OutlineGeneratorAgent,
    CharacterAgent,
    WriterAgent,
    ReflectAgent,
    EntityAgent,
) 
from src.node import *
from src.state import NovelState
from src.log_config import loggers
from src.model_manager import LocalModelManager, APIModelManager
from src.config_loader import (
    OutlineConfig,
    CharacterConfig,
    WriterConfig,
    ReflectConfig,
    EntityConfig,
    BaseConfig,
    ModelConfig
)

logger = loggers['workflow']

# 构建工作流
def create_workflow(model_config: ModelConfig, Agent_config: BaseConfig= None) -> StateGraph:
    """创建包含章节写作和质量评审的完整工作流"""
    # 获取共享模型实例和分词器
    model_type = model_config.model_type
    
    if model_type == "local":
        model_manager = LocalModelManager(model_config.model_path)
    elif model_type == "api":
        model_manager = APIModelManager(
            model_config.api_url,
            model_config.api_key,
            model_name=model_config.model_name,
            max_retries=model_config.max_retries,
            retry_delay=model_config.retry_delay
        )
    logger.info(f"成功加载{model_type}模型管理器")
    # 允许改变config值
    if Agent_config is not None:
        OutlineConfig.min_chapters = Agent_config.min_chapters
        OutlineConfig.volume = Agent_config.volume
        OutlineConfig.master_outline = Agent_config.master_outline
    # 初始化 Agent
    outline_agent = OutlineGeneratorAgent(model_manager, OutlineConfig)    # 大纲
    character_agent = CharacterAgent(model_manager, CharacterConfig)         # 角色
    writer_agent = WriterAgent(model_manager, WriterConfig)               # 写作
    reflect_agent = ReflectAgent(model_manager, ReflectConfig)             # 反思
    entity_agent = EntityAgent(model_manager, EntityConfig)                 # 实体识别
    
    logger.info("代理初始化完成, 开始构建工作流图...")
    
    # 创建图
    workflow = StateGraph(NovelState)
    # -------------------- 创建节点 --------------------
    if OutlineConfig.master_outline:
        # 分卷
        workflow.add_node("generate_master_outline",
                        lambda state: generate_master_outline_node(state, outline_agent))
        workflow.add_node("validate_master_outline", validate_master_outline_node)
        
        # 分章
        workflow.add_node("generate_volume_outline", 
                        lambda state: generate_volume_outline_node(state, outline_agent))
        workflow.add_node("validate_volume_outline", validate_volume_outline_node)
        
        # 合并
        workflow.add_node("accpet_outline", accept_outline_node)
        workflow.add_node("volume2character", volume2character)
    else:
        # 大纲
        workflow.add_node("generate_outline", 
                        lambda state: generate_outline_node(state, outline_agent))
        workflow.add_node("validate_outline", validate_outline_node)
        
    
    # 角色
    workflow.add_node("generate_characters", 
                     lambda state: generate_characters_node(state, character_agent))
    workflow.add_node("validate_characters",validate_characters_node)
    
    # 写作
    workflow.add_node("write_chapter",
                      lambda state: write_chapter_node(state, writer_agent))
    workflow.add_node("validate_chapter", validate_chapter_node)
    
    # 新增：实体识别
    workflow.add_node("generate_entities",
                      lambda state: generate_entities_node(state, entity_agent))
    workflow.add_node("validate_entities", validate_entities_node)
    
    # 评估
    workflow.add_node("evaluate_chapter",
                      lambda state: evaluate_chapter_node(state, reflect_agent))
    workflow.add_node("validate_evaluate", validate_evaluate_node)
    
    workflow.add_node("evaluate2wirte", evaluation_to_chapter_node)
    
    # 接受本章
    workflow.add_node("accpet_chapter", accept_chapter_node)
    
    
    workflow.add_node("success", lambda state: {
        "result": "小说创作流程完成",
        "final_outline": state.novel_storage.load_outline(),
        "final_characters":state.novel_storage.load_characters(),
        "final_content": state.novel_storage.load_all_chapters()
    })
    
    workflow.add_node("failure", lambda state: {
        "result": "生成失败", 
        "final_error": state.outline_validated_error or state.characters_validated_error or state.current_chapter_validated_error or state.evaluation_validated_error
    })
    
    
    # -------------------- 创建边 --------------------
    # 大纲(原逻辑保留)
    
    if OutlineConfig.master_outline:
        workflow.set_entry_point("generate_master_outline")
        workflow.add_edge("generate_master_outline", "validate_master_outline")
        workflow.add_conditional_edges(
            "validate_master_outline",
            check_master_outline_node,
            {
                "success": "generate_volume_outline",
                "retry": "generate_master_outline",
                "failure": "failure"
            }
        )
        workflow.add_edge("generate_volume_outline", "validate_volume_outline")
        workflow.add_conditional_edges(
            "validate_volume_outline",
            check_volume_outline_node,
            {
                "success": "volume2character",
                "retry": "generate_volume_outline",
                "failure": "failure"
            }
        )
        workflow.add_edge("volume2character", "accpet_outline")
        workflow.add_conditional_edges(
            "accpet_outline",
            check_outline_completion_node,
            {
                "complete":"generate_characters",
                "continue":"generate_volume_outline"
            }
        )
        
    else:
        workflow.set_entry_point("generate_outline")
        workflow.add_edge("generate_outline", "validate_outline")
        workflow.add_conditional_edges(
            "validate_outline",
            check_outline_node,
            {
                "success": "generate_characters",
                "retry": "generate_outline",
                "failure": "failure"
            }
        )
    
    # 角色档案
    workflow.add_edge("generate_characters", "validate_characters")
    workflow.add_conditional_edges(
        "validate_characters",
        check_characters_node,
        {
            "success": "write_chapter",
            "retry": "generate_characters",
            "failure": "failure"
        }
    )
    
    # 写作
    workflow.add_edge("write_chapter", "validate_chapter")
    workflow.add_conditional_edges(
        "validate_chapter",
        check_chapter_node,
        {
            "success": "evaluate_chapter",
            "retry": "write_chapter",
            "failure": "failure"
        }
    )
    
    
    # 评估
    workflow.add_edge("evaluate_chapter", "validate_evaluate")
    workflow.add_conditional_edges(
        "validate_evaluate",
        check_evaluation_node,
        {
            "success": "evaluate2wirte",
            "retry": "evaluate_chapter",
            "failure":"failure"
        }
    )
    workflow.add_conditional_edges(
        "evaluate2wirte",
        check_evaluation_chapter_node,
        {
            "accept":"generate_entities",   # 验证通过，执行实体分析
            "revise":"write_chapter",
            "force_accpet":"accpet_chapter"
        }
    )
    
    # 新增：实体识别
    workflow.add_edge("generate_entities", "validate_entities")
    workflow.add_conditional_edges(
        "validate_entities",
        check_entities_node,
        {
            "success": "accpet_chapter",    # 实体识别成功，接受章节
            "retry": "generate_entities",
            "failure": "failure"
        }
    )
    
    workflow.add_conditional_edges(
        "accpet_chapter",
        check_chapter_completion_node,
        {
            "complete":"success",
            "continue":"write_chapter"
        }
    )
    
    workflow.add_edge("success", END)
    workflow.add_edge("failure", END)
    logger.info("工作流图创建完成, 开始编译!")
    # 编译图
    return workflow.compile()
