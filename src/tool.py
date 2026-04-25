import json
import logging
from typing import Optional, Tuple
import re

logger = logging.getLogger(__name__)


def is_json_truncated(json_str: str) -> bool:
    """检测JSON是否可能被截断（以不完整的结构结束）"""
    if not json_str or not json_str.strip():
        return True

    # 清理空白
    cleaned = json_str.strip()

    # 检查是否以明显的截断标记结束
    truncated_indicators = [
        ',\n    {"',      # 数组元素中间截断
        ',\n        {"',   # 嵌套对象中间截断
        ',\n  {"',        # 紧凑格式中间截断
        '}\n',            # 对象后换行（可能正常）
        ']\n',            # 数组后换行（可能正常）
    ]

    # 检查是否以未闭合的结构结束
    open_braces = cleaned.count('{') - cleaned.count('}')
    open_brackets = cleaned.count('[') - cleaned.count(']')

    # 如果开括号数量大于闭括号，说明截断
    if open_braces > 0 or open_brackets > 0:
        return True

    # 如果以单个引号结束（字符串未闭合），说明截断
    if cleaned.endswith("'") or cleaned.endswith('"'):
        return True

    # 如果以逗号结束后直接是空白/换行，说明可能截断
    if re.search(r',\s*$', cleaned):
        return True

    return False


def extract_json(generated_text: str) -> Optional[str]:
    """从生成的文本中提取JSON部分，专门处理被```json标记包裹的内容

    Returns:
        提取的JSON字符串，如果无法提取有效JSON则返回None
    """
    if not generated_text or not generated_text.strip():
        logger.debug("输入文本为空")
        return None

    try:
        # 首先尝试匹配被```json和```包裹的内容（最常见情况）
        json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', generated_text)
        if json_block_match:
            json_content = json_block_match.group(1).strip()
            # 验证提取的内容是否是有效的JSON
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError as e:
                # 如果是截断错误（行号超过实际行数），说明JSON不完整
                if is_json_truncated(json_content):
                    logger.debug(f"提取的JSON块不完整（可能被截断）: {str(e)[:50]}")
                    return None
                logger.debug("提取的JSON块格式无效，尝试其他提取方式")

        # 如果没有找到标记包裹的JSON，尝试匹配纯JSON对象
        json_obj_match = re.search(r'\{\s*"[\w"]+":[\s\S]*\}', generated_text)
        if json_obj_match:
            json_content = json_obj_match.group(0).strip()
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError as e:
                if is_json_truncated(json_content):
                    logger.debug(f"提取的JSON对象不完整（可能被截断）: {str(e)[:50]}")
                    return None
                logger.debug("提取的JSON对象格式无效")

        # 尝试匹配JSON数组
        json_array_match = re.search(r'\[\s*\{\s*"[\w"]+":[\s\S]*\}\s*\]', generated_text)
        if json_array_match:
            json_content = json_array_match.group(0).strip()
            try:
                json.loads(json_content)
                return json_content
            except json.JSONDecodeError as e:
                if is_json_truncated(json_content):
                    logger.debug(f"提取的JSON数组不完整（可能被截断）: {str(e)[:50]}")
                    return None
                logger.debug("提取的JSON数组格式无效")

        # 如果所有尝试都失败，打印调试信息
        logger.debug("无法找到有效的JSON结构")
        return None

    except Exception as e:
        logger.debug(f"提取JSON时出错: {str(e)}")
        return None
