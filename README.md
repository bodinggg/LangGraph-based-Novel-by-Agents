## 项目简介

本项目通过多 Agent 协作与状态管理，构建了一套完整的小说创作工作流。系统接收用户的小说创作意图后，自动完成大纲生成、角色档案创建、章节撰写、内容评估与修改迭代，最终输出完整的小说内容。核心采用 LangGraph 实现状态流转与节点协作，结合本地模型完成文本生成任务。

## 功能特点

- **全流程自动化**：从用户意图到完整小说的端到端生成，无需人工干预
- **结构化生成**：严格遵循 JSON 格式验证，确保内容结构可控
- **多 Agent 协作**：大纲生成、角色塑造、章节撰写、质量评估等专项 Agent 分工协作
- **迭代优化机制**：每个环节均包含验证与重试逻辑，确保内容质量
- **可配置参数**：支持调整生成长度、温度等参数，适配不同创作需求
- **错误反馈**：重试次数达到上限，最后会优雅地告诉你问题出在哪里

## 安装指南

### 依赖环境

- Python 3.11+
- 依赖库：`transformers`, `langgraph`, `pydantic`, `torch`

### 安装步骤

1. 克隆项目代码

```bash
git clone https://github.com/bodinggg/LangGraph-based-Novel-by-Agents.git
cd novel-creator
```

1. 安装依赖包

```bash
pip install -r requirements.txt
```

1. 准备模型
   - 需配置支持对话生成的本地模型
   - 修改`app.py`中的`model_path`为你的模型路径

## 使用方法

1. 启动应用

```bash
python app.py
```

1. 输入创作意图

```plaintext
请输入你的小说创作意图：例如"科幻"
```

1. 系统自动运行
   - 依次执行大纲生成、角色创建、章节撰写等流程
   - 过程日志将实时输出
   - 最终生成完整小说内容

## 项目结构

```plaintext
my_novel/
├──app.py               # 应用入口，处理用户输入与启动工作流
├──config.yaml          # 配置文件，配置Agent所用模型参数
└──src
   ├── workflow.py          # 工作流定义，基于LangGraph构建节点与流转逻辑
   ├── agent.py/
   │   ├── OutlineGeneratorAgent  # 大纲生成代理
   │   ├── CharacterAgent         # 角色档案生成代理
   │   ├── WriterAgent            # 章节撰写代理
   │   └── ReflectAgent           # 内容评估代理
   ├── node.py              # 工作流节点函数，实现各环节具体逻辑
   ├── model.py             # 数据模型定义，基于Pydantic实现结构验证
   ├── state.py             # 全局状态管理，存储创作过程中的所有数据
   ├── prompt.py            # 各Agent的提示词模板
   ├── config_loader.py            # 生成参数配置（长度、温度等）
   └── tool.py              # 工具函数（如JSON提取）
   ```

## 工作流程介绍

1. **大纲生成阶段**
   - `generate_outline`：根据用户意图生成小说大纲（至少 10 章）
   - `validate_outline`：验证大纲 JSON 格式与内容完整性
   - `check_outline_node`：判断是否需要重试
2. **角色档案阶段**
   - `generate_characters`：基于大纲生成详细角色档案（背景、性格、目标等）
   - `validate_characters`：验证角色档案完整性与与大纲的一致性
   - `check_characters_node`：判断是否需要重试
3. **章节创作阶段**
   - `write_chapter`：根据大纲与角色档案撰写单章内容
   - `validate_chapter`：验证章节格式与内容是否符合要求
   - `check_chapter_node`：判断是否需要重试
   - `evaluate_chapter`：评估章节质量（评分、反馈建议）
   - `validate_evaluate`：验证评估格式是否符合要求
   - `check_evaluation_node`：判断是否需要重试
   - `evaluate2wirte`: 用于将判断评估内容转移到文本评估流程
   - `check_evaluation_chapter_node`: 判断流程转移
   - `accpet_chapter`：接受章节或返回修改，直至完成所有章节
   - `check_chapter_completion_node`：判断是否完成写作
   - `success`&`failure`: 引导流程结束

## 配置说明

可通过`config.py`调整生成参数：

```python
class WriterConfig:
    max_new_tokens = 4096  # 最大生成 tokens
    temperature = 0.4      # 生成随机性（0-1，值越低越确定）
    top_p = 0.9            # 核采样参数
    min_word_length = 1000 # 最小章节长度
```

## 示例输出

生成的小说内容包含：

- 完整的小说大纲（标题、类型、章节结构等）
- 详细角色档案（背景、性格、成长弧线等）
- 各章节完整内容（符合大纲设定，角色言行一致）
