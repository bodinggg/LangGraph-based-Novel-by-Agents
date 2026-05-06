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
from src.feedback_nodes import (
    outline_feedback_node, process_outline_feedback_node, check_outline_feedback_node,
    character_feedback_node, process_character_feedback_node, check_character_feedback_node,
    chapter_feedback_node, process_chapter_feedback_node, check_chapter_feedback_deep_mode_node
)
from src.supervisor_node import supervisor_node, init_supervisor_node

from src.state import NovelState
from src.log_config import loggers
from src.model_manager import create_model_manager
from src.config_loader import (
    OutlineConfig,
    CharacterConfig,
    WriterConfig,
    ReflectConfig,
    BaseConfig,
    ModelConfig
)
from src.agents.registry import AgentRegistry

logger = loggers['workflow']


def _get_agent(agent_name: str, model_manager, config) -> object:
    """获取 Agent 实例（优先从注册表，否则直接实例化）"""
    if AgentRegistry.is_registered(agent_name):
        logger.info(f"[Workflow] 从注册表获取 Agent: {agent_name}")
        return AgentRegistry.get(agent_name, model_manager=model_manager, config=config)
    else:
        # 回退到直接实例化（向后兼容）
        agent_map = {
            "outline": OutlineGeneratorAgent,
            "character": CharacterAgent,
            "writer": WriterAgent,
            "reflect": ReflectAgent,
            "entity": EntityAgent,
        }
        agent_class = agent_map.get(agent_name)
        if agent_class:
            logger.info(f"[Workflow] 直接实例化 Agent: {agent_name}")
            return agent_class(model_manager, config)
        raise KeyError(f"Unknown agent: {agent_name}")

# 构建工作流
def create_workflow(model_config: ModelConfig, Agent_config: BaseConfig= None, execution_mode: str = "serial") -> StateGraph:
    """创建包含章节写作和质量评审的完整工作流"""
    # 获取共享模型实例
    model_manager = create_model_manager(model_config, execution_mode)
    logger.info(f"成功加载{model_config.model_type}模型管理器")

    # Use agent_config for outline settings, fallback to defaults
    outline_cfg = Agent_config if Agent_config is not None else OutlineConfig
    master_outline = outline_cfg.master_outline

    # 如果注册表为空，先注册内置 Agent
    if not AgentRegistry.list_agents():
        from src.agents.setup import register_builtin_agents
        register_builtin_agents()

    # 初始化 Agent（优先从注册表获取）
    outline_agent = _get_agent("outline", model_manager, outline_cfg)    # 大纲
    character_agent = _get_agent("character", model_manager, CharacterConfig)         # 角色
    writer_agent = _get_agent("writer", model_manager, WriterConfig)               # 写作
    reflect_agent = _get_agent("reflect", model_manager, ReflectConfig)             # 反思

    # 初始化 SupervisorNode（多 Agent 并行检查）
    init_supervisor_node(model_manager)

    logger.info("代理初始化完成, 开始构建工作流图...")

    # 创建图
    workflow = StateGraph(NovelState)
    # -------------------- 创建节点 --------------------
    if master_outline:
        # 分卷
        workflow.add_node("generate_outline",
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
        
    # 反馈节点
    workflow.add_node("outline_feedback", outline_feedback_node)
    workflow.add_node("process_outline_feedback", process_outline_feedback_node)
    
    # 角色
    workflow.add_node("generate_characters", 
                     lambda state: generate_characters_node(state, character_agent))
    workflow.add_node("validate_characters",validate_characters_node)
    
    # 角色反馈节点
    workflow.add_node("character_feedback", character_feedback_node)
    workflow.add_node("process_character_feedback", process_character_feedback_node)
    
    # 写作
    workflow.add_node("write_chapter",
                      lambda state: write_chapter_node(state, writer_agent))
    workflow.add_node("validate_chapter", validate_chapter_node)
    
    # 章节反馈节点
    workflow.add_node("chapter_feedback", chapter_feedback_node)
    workflow.add_node("process_chapter_feedback", process_chapter_feedback_node)
    
    # 评估
    workflow.add_node("evaluate_chapter",
                      lambda state: evaluate_chapter_node(state, reflect_agent))
    workflow.add_node("validate_evaluate", validate_evaluate_node)
    workflow.add_node("evaluate_report", 
                      lambda state: evaluate_report_node(state, reflect_agent))
    
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
    
    if master_outline:
        workflow.set_entry_point("generate_outline")
        workflow.add_edge("generate_outline", "validate_master_outline")
        workflow.add_conditional_edges(
            "validate_master_outline",
            check_master_outline_node,
            {
                "success": "generate_volume_outline",
                "retry": "generate_outline",
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
                "complete":"outline_feedback",
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
                "success": "outline_feedback",
                "retry": "generate_outline",
                "failure": "failure"
            }
        )
    
    # 反馈流程 - 大纲编辑在角色档案生成前进行
    workflow.add_edge("outline_feedback", "process_outline_feedback")
    workflow.add_conditional_edges(
        "process_outline_feedback",
        check_outline_feedback_node,
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
            "success": "character_feedback",
            "retry": "generate_characters",
            "failure": "failure"
        }
    )
    
    # 角色反馈流程
    workflow.add_edge("character_feedback", "process_character_feedback")
    workflow.add_conditional_edges(
        "process_character_feedback",
        check_character_feedback_node,
        {
            "success": "route_to_writing",
            "retry": "generate_characters",
            "failure": "failure"
        }
    )

    # -------------------- 执行模式路由 --------------------
    workflow.add_node("route_to_writing", route_to_writing_node)
    workflow.add_conditional_edges(
        "route_to_writing",
        check_execution_mode_node,
        {
            "serial": "write_chapter",
            "parallel": "batch_write_chapters"
        }
    )

    # -------------------- 批量并行写作节点 --------------------
    workflow.add_node("batch_write_chapters",
                      lambda state: batch_write_chapters_node(state, writer_agent))
    workflow.add_node("batch_validate_chapters", batch_validate_chapters_node)
    workflow.add_edge("batch_write_chapters", "batch_validate_chapters")

    # 批量验证后的路由
    workflow.add_conditional_edges(
        "batch_validate_chapters",
        check_batch_completion_node,
        {
            "continue_serial": "chapter_feedback",
            "continue_parallel": "route_to_writing",
            "complete": "success"
        }
    )

    # 写作
    workflow.add_edge("write_chapter", "validate_chapter")
    workflow.add_conditional_edges(
        "validate_chapter",
        check_chapter_node,
        {
            "success": "chapter_feedback",
            "retry": "write_chapter",
            "failure": "failure"
        }
    )
    
    # 章节反馈流程
    workflow.add_edge("chapter_feedback", "process_chapter_feedback")
    workflow.add_conditional_edges(
        "process_chapter_feedback",
        check_chapter_feedback_deep_mode_node,
        {
            "success": "evaluate_chapter",      # fast模式：走评估链
            "deep_skip": "supervisor_node",     # deep模式：跳过评估，直接进入supervisor
            "retry": "write_chapter",
            "failure": "failure"
        }
    )
    
    
    # 评估
    workflow.add_edge("evaluate_chapter", "validate_evaluate")
    # 评估报告
    workflow.add_edge("validate_evaluate", "evaluate_report")
    
    workflow.add_conditional_edges(
        "evaluate_report",
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
            "accept":"supervisor_node",     # 深度模式：验证通过，进入 supervisor 检查
            "revise":"write_chapter",
            "force_accpet":"accpet_chapter", # 强制接受
            "fast_accept":"accpet_chapter",  # 快速模式：直接接受，跳过 supervisor
        }
    )

    # Supervisor 检查节点（重构后：直接决策，不再经过 Council）
    workflow.add_node("supervisor_node", supervisor_node)

    # check_revision_node 根据 revision_needed 决定下一步
    workflow.add_conditional_edges(
        "supervisor_node",
        lambda state: "revise" if getattr(state, 'revision_needed', False) else "accept_chapter",
        {
            "revise": "write_chapter",        # 需要修订，重新撰写
            "accept_chapter": "accpet_chapter" # 无需修订，接受章节
        }
    )

    # 验收流程
    workflow.add_conditional_edges(
        "accpet_chapter",
        check_chapter_completion_node,
        {
            "complete": "success",
            "continue": "write_chapter"  # 继续写下一章
        }
    )
    
    workflow.add_edge("success", END)
    workflow.add_edge("failure", END)
    logger.info("工作流图创建完成, 开始编译!")
    # 编译图
    return workflow.compile()
