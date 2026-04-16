import json
from typing import Optional
import re


# 工具函数：优化的JSON提取逻辑
def extract_json(generated_text: str) -> Optional[str]:
    """从生成的文本中提取JSON部分，专门处理被```json标记包裹的内容"""
    try:
        # 首先尝试匹配被```json和```包裹的内容（最常见情况）
        json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', generated_text)
        if json_block_match:
            json_content = json_block_match.group(1).strip()
            # 验证提取的内容是否是有效的JSON
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                print("提取的JSON块格式无效，尝试其他提取方式")
        
        # 如果没有找到标记包裹的JSON，尝试匹配纯JSON对象
        json_obj_match = re.search(r'\{\s*"[\w"]+":[\s\S]*\}', generated_text)
        if json_obj_match:
            json_content = json_obj_match.group(0).strip()
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                print("提取的JSON对象格式无效")
        
        # 尝试匹配JSON数组
        json_array_match = re.search(r'\[\s*\{\s*"[\w"]+":[\s\S]*\}\s*\]', generated_text)
        if json_array_match:
            json_content = json_array_match.group(0).strip()
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError:
                print("提取的JSON数组格式无效")
                
        # 如果所有尝试都失败，返回原始文本的可能JSON部分
        print("无法找到有效的JSON结构，返回可能的JSON部分")
        return generated_text
        
    except Exception as e:
        print(f"提取JSON时出错: {str(e)}")
        return None
