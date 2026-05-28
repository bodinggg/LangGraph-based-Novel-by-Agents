"""
StoryBible 有效性审计报告生成器

生成标准化的审计报告，包含分层注入、缓存效率、约束有效性、端到端一致性四个维度。
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


# ============ 审计数据结构 ============

@dataclass
class LayerAudit:
    """分层注入审计结果"""
    layer0_items: int = 0  # Layer 0 静态约束数量
    layer1_items: int = 0  # Layer 1 慢变状态数量
    layer2_items: int = 0  # Layer 2 快变状态数量
    separation_correct: bool = True  # 分层是否正确
    injection_order_correct: bool = True  # 注入顺序是否正确
    total_tokens: int = 0  # 总注入 token 数
    token_budget_ok: bool = True  # 是否在预算内（<2000）


@dataclass
class CacheAudit:
    """缓存效率审计结果"""
    flat_prefix_overlap: float = 0.0  # 平铺注入的前缀重叠率
    layered_prefix_overlap: float = 0.0  # 分层注入的前缀重叠率
    cache_improvement: float = 0.0  # 改善百分比
    layer0_stability: float = 1.0  # Layer 0 跨章节稳定性（应为1.0）


@dataclass
class ConstraintAudit:
    """约束有效性审计结果"""
    total_trials: int = 0  # 总测试次数
    with_context_violations: int = 0  # 有上下文违规次数
    without_context_violations: int = 0  # 无上下文违规次数
    violation_rate_with: float = 0.0  # 有上下文的违规率
    violation_rate_without: float = 0.0  # 无上下文的违规率
    effectiveness_ratio: float = 0.0  # 违规率下降比例
    judge_verdict: str = "N/A"  # LLM 裁判总体判定
    keyword_detection_accuracy: float = 0.0  # 规则引擎准确率


@dataclass
class E2EAudit:
    """端到端一致性审计结果"""
    total_chapters: int = 0  # 总章节数
    chapters_with_violations: int = 0  # 存在违规的章节数
    total_violations: int = 0  # 总违规数
    violations_per_chapter: List[int] = field(default_factory=list)  # 每章违规数
    trend: str = "稳定"  # "递减" | "稳定" | "递增"
    revision_fix_rate: float = 0.0  # 重写修复率


@dataclass
class AuditReport:
    """StoryBible 有效性审计报告"""
    layer_audit: LayerAudit = field(default_factory=LayerAudit)
    cache_audit: CacheAudit = field(default_factory=CacheAudit)
    constraint_audit: ConstraintAudit = field(default_factory=ConstraintAudit)
    e2e_audit: E2EAudit = field(default_factory=E2EAudit)
    overall_score: float = 0.0  # 0-100
    timestamp: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M'))


# ============ 评分计算 ============

def calculate_score(report: AuditReport) -> float:
    """计算审计报告综合评分

    Args:
        report: 审计报告

    Returns:
        0-100 的综合评分
    """
    # 分层注入 (25分)
    layer_score = 0
    if report.layer_audit.separation_correct:
        layer_score += 10
    if report.layer_audit.injection_order_correct:
        layer_score += 10
    if report.layer_audit.token_budget_ok:
        layer_score += 5

    # 缓存效率 (25分)
    cache_score = min(25, report.cache_audit.cache_improvement * 50)

    # 约束有效性 (30分)
    constraint_score = 0
    if report.constraint_audit.effectiveness_ratio > 0.5:
        constraint_score += 15
    elif report.constraint_audit.effectiveness_ratio > 0.3:
        constraint_score += 10
    if report.constraint_audit.violation_rate_with < 0.2:
        constraint_score += 15
    elif report.constraint_audit.violation_rate_with < 0.4:
        constraint_score += 10

    # 端到端 (20分)
    e2e_score = 0
    if report.e2e_audit.trend == "递减":
        e2e_score += 10
    elif report.e2e_audit.trend == "稳定":
        e2e_score += 5
    if report.e2e_audit.revision_fix_rate > 0.8:
        e2e_score += 10
    elif report.e2e_audit.revision_fix_rate > 0.6:
        e2e_score += 5

    total = layer_score + cache_score + constraint_score + e2e_score
    report.overall_score = total
    return total


def get_score_rating(score: float) -> str:
    """根据评分返回星级评价

    Args:
        score: 综合评分

    Returns:
        星级评价字符串
    """
    if score >= 80:
        return "★★★★★ 优秀"
    elif score >= 60:
        return "★★★★ 良好"
    elif score >= 40:
        return "★★★ 需改进"
    else:
        return "★★ 较差"


# ============ 建议生成 ============

def generate_recommendations(report: AuditReport) -> List[str]:
    """生成改进建议

    Args:
        report: 审计报告

    Returns:
        改进建议列表
    """
    recommendations = []

    if not report.layer_audit.token_budget_ok:
        recommendations.append("- Token 超预算: 考虑裁剪 Layer 1 历史阶段，只保留当前阶段")

    if report.cache_audit.cache_improvement < 0.3:
        recommendations.append("- 缓存改善有限: 检查 Layer 0 是否包含过多变化内容")

    if report.constraint_audit.effectiveness_ratio < 0.5:
        recommendations.append("- 约束有效性不足: 考虑增强 Layer 0 约束的显眼程度（加粗/重复）")

    if report.e2e_audit.trend == "递增":
        recommendations.append("- 违规未递减: 检查 StoryBible 更新逻辑是否正确提取新约束")

    if report.e2e_audit.trend == "稳定" and report.e2e_audit.total_violations > 5:
        recommendations.append("- 违规未递减: 系统可能存在固定的模式问题，建议检查 WriterAgent prompt")

    if report.e2e_audit.revision_fix_rate < 0.8:
        recommendations.append("- 重写修复率低: 检查 revision_context 是否包含足够违规信息")

    if report.constraint_audit.keyword_detection_accuracy < 0.8:
        recommendations.append("- 规则引擎准确率低: 考虑升级为 LLM 辅助检查")

    if not recommendations:
        recommendations.append("- 当前系统表现良好，无明显改进点")

    return recommendations


# ============ 报告生成 ============

def generate_audit_report(report: AuditReport) -> str:
    """生成格式化的审计报告

    Args:
        report: 审计报告

    Returns:
        格式化的报告字符串
    """
    score = calculate_score(report)
    rating = get_score_rating(score)
    recommendations = generate_recommendations(report)

    layer = report.layer_audit
    cache = report.cache_audit
    constraint = report.constraint_audit
    e2e = report.e2e_audit

    # 计算各维度分数
    layer_score = min(25, (10 if layer.separation_correct else 0) +
                       (10 if layer.injection_order_correct else 0) +
                       (5 if layer.token_budget_ok else 0))
    cache_score = min(25, cache.cache_improvement * 50)
    constraint_score = 0
    if constraint.effectiveness_ratio > 0.5:
        constraint_score += 15
    elif constraint.effectiveness_ratio > 0.3:
        constraint_score += 10
    if constraint.violation_rate_with < 0.2:
        constraint_score += 15
    elif constraint.violation_rate_with < 0.4:
        constraint_score += 10
    e2e_score = (10 if e2e.trend == "递减" else 5 if e2e.trend == "稳定" else 0) + \
                (10 if e2e.revision_fix_rate > 0.8 else 5 if e2e.revision_fix_rate > 0.6 else 0)

    return f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    StoryBible 有效性审计报告                          ║
║                    生成时间: {report.timestamp}                          ║
╚══════════════════════════════════════════════════════════════════════╝

┌─ 1. 分层注入审计 ───────────────────────────────────────────────────┐
│ Layer 0 (静态约束):  {layer.layer0_items} 项                                        │
│ Layer 1 (慢变状态):  {layer.layer1_items} 项                                        │
│ Layer 2 (快变状态):  {layer.layer2_items} 项                                        │
│ 分离正确性:          {'✓ PASS' if layer.separation_correct else '✗ FAIL'}                                           │
│ 注入顺序正确性:      {'✓ PASS' if layer.injection_order_correct else '✗ FAIL'}                                           │
│ Token 预算:          {layer.total_tokens}/2000 ({'✓ 在预算内' if layer.token_budget_ok else '✗ 超出预算'})         │
│ 维度评分:            {layer_score:.0f}/25                                               │
└──────────────────────────────────────────────────────────────────────┘

┌─ 2. 缓存效率审计 ───────────────────────────────────────────────────┐
│ 平铺注入前缀重叠率:  {cache.flat_prefix_overlap:.1%}                                       │
│ 分层注入前缀重叠率:  {cache.layered_prefix_overlap:.1%}                                       │
│ 缓存改善:            {cache.cache_improvement:+.1%}                                       │
│ Layer 0 稳定性:      {cache.layer0_stability:.1%}                                       │
│ {'✓ 分层注入显著提升缓存效率' if cache.cache_improvement > 0.3 else '⚠ 改善有限'}                                               │
│ 维度评分:            {cache_score:.0f}/25                                               │
└──────────────────────────────────────────────────────────────────────┘

┌─ 3. 约束有效性审计 ─────────────────────────────────────────────────┐
│ 测试次数:            {constraint.total_trials}                                              │
│ 有上下文违规率:      {constraint.violation_rate_with:.1%}                                       │
│ 无上下文违规率:      {constraint.violation_rate_without:.1%}                                       │
│ 有效性比率:          {constraint.effectiveness_ratio:.1%}                                       │
│ LLM 裁判判定:       {constraint.judge_verdict}                                        │
│ 规则引擎准确率:      {constraint.keyword_detection_accuracy:.1%}                                       │
│ {'✓ StoryBible 约束显著降低违规率' if constraint.effectiveness_ratio > 0.5 else '⚠ 约束效果有限'}                                               │
│ 维度评分:            {constraint_score:.0f}/30                                               │
└──────────────────────────────────────────────────────────────────────┘

┌─ 4. 端到端一致性审计 ───────────────────────────────────────────────┐
│ 总章节数:            {e2e.total_chapters}                                              │
│ 存在违规的章节:      {e2e.chapters_with_violations}                                              │
│ 总违规数:            {e2e.total_violations}                                              │
│ 违规趋势:            {e2e.trend}                                              │
│ 重写修复率:          {e2e.revision_fix_rate:.1%}                                       │
│ 维度评分:            {e2e_score:.0f}/20                                               │
└──────────────────────────────────────────────────────────────────────┘

┌─ 5. 综合评分 ───────────────────────────────────────────────────────┐
│                                                              │
│   总分: {score:.0f}/100                                               │
│                                                              │
│   分层注入:  {layer_score:.0f}/25                                   │
│   缓存效率:  {cache_score:.0f}/25                                   │
│   约束有效:  {constraint_score:.0f}/30                              │
│   端到端:    {e2e_score:.0f}/20                                   │
│                                                              │
│   评级: {rating}                                  │
│                                                              │
└──────────────────────────────────────────────────────────────────┘

┌─ 6. 改进建议 ───────────────────────────────────────────────────────┐
{"".join(f"│ {rec:<65} │" if len(rec) <= 65 else f"│ {rec[:65]:<65} │" for rec in recommendations)}
└──────────────────────────────────────────────────────────────────────┘
"""