"""
缓存效率计算工具

用于评估 StoryBible 分层注入的 KV cache 命中率
"""
from typing import List


def calculate_prefix_overlap(prompt_a: str, prompt_b: str) -> float:
    """计算两个 prompt 的前缀重叠率

    原理：从头开始逐字符比较，找到第一个不同位置，
    计算相同前缀占较小 prompt 的比例。

    Args:
        prompt_a: 第一个 prompt
        prompt_b: 第二个 prompt

    Returns:
        0.0-1.0 的重叠率，1.0 表示完全相同
    """
    if not prompt_a or not prompt_b:
        return 0.0

    min_len = min(len(prompt_a), len(prompt_b))
    if min_len == 0:
        return 0.0

    # 找到第一个不同位置
    diff_pos = 0
    for i in range(min_len):
        if prompt_a[i] != prompt_b[i]:
            diff_pos = i
            break
    else:
        diff_pos = min_len

    return diff_pos / min_len


def calculate_prompt_stability(prompts: List[str]) -> float:
    """计算多个 prompt 的平均稳定性

    计算相邻 prompt 之间的前缀重叠率的平均值。
    用于评估分层注入对缓存效率的影响。

    Args:
        prompts: prompt 列表

    Returns:
        0.0-1.0 的稳定性分数
    """
    if len(prompts) < 2:
        return 1.0

    overlaps = []
    for i in range(len(prompts) - 1):
        overlap = calculate_prefix_overlap(prompts[i], prompts[i + 1])
        overlaps.append(overlap)

    return sum(overlaps) / len(overlaps)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数

    估算规则：
    - 中文字符：约 1.5-2 字/token
    - 英文字符：约 4 字符/token
    - 标点符号：约 2 字符/token

    由于混合文本的复杂性，使用简化估算：总字符数 / 3

    Args:
        text: 输入文本

    Returns:
        估算的 token 数
    """
    if not text:
        return 0

    # 简化估算：字符数 / 3
    # 实际 token 数取决于具体分词器，但这个估算在大多数情况下够用
    return len(text) // 3


def calculate_cache_savings(layered_overlap: float, flat_overlap: float) -> float:
    """计算分层注入相比平铺注入的缓存节省

    Args:
        layered_overlap: 分层注入的前缀重叠率
        flat_overlap: 平铺注入的前缀重叠率

    Returns:
        缓存节省比例（0.0-1.0）
        正值表示分层更好，负值表示分层更差
    """
    if flat_overlap == 0:
        return 0.0

    return (layered_overlap - flat_overlap) / flat_overlap


def format_cache_report(
    flat_overlap: float,
    layered_overlap: float,
    stability: float,
    total_tokens: int
) -> str:
    """生成缓存效率报告

    Args:
        flat_overlap: 平铺注入的前缀重叠率
        layered_overlap: 分层注入的前缀重叠率
        stability: 提示稳定性分数
        total_tokens: 单章注入的 token 数

    Returns:
        格式化的报告字符串
    """
    savings = calculate_cache_savings(layered_overlap, flat_overlap)

    lines = [
        "=" * 50,
        "StoryBible 缓存效率报告",
        "=" * 50,
        f"平铺注入前缀重叠率:  {flat_overlap:.1%}",
        f"分层注入前缀重叠率:  {layered_overlap:.1%}",
        f"缓存改善:            {savings:+.1%}",
        f"提示稳定性:          {stability:.1%}",
        f"单章 token 数:        {total_tokens}",
        "=" * 50,
    ]

    if layered_overlap > flat_overlap + 0.1:
        lines.append("结论: ✓ 分层注入显著提升缓存效率")
    elif layered_overlap > flat_overlap:
        lines.append("结论: ✓ 分层注入略有改善")
    else:
        lines.append("结论: ⚠ 分层注入无明显改善")

    return "\n".join(lines)