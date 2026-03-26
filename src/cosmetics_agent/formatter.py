from __future__ import annotations

from .models import AgentResponse, Recommendation, UserProfile


def format_profile(profile: UserProfile) -> str:
    parts: list[str] = []
    if profile.skin_types:
        parts.append("肤质=" + " / ".join(profile.skin_types))
    if profile.concerns:
        parts.append("诉求=" + " / ".join(profile.concerns))
    if profile.desired_categories:
        parts.append("品类=" + " / ".join(profile.desired_categories))
    if profile.budget_max is not None:
        budget = f"{profile.budget_min}-{profile.budget_max}" if profile.budget_min is not None else f"<= {profile.budget_max}"
        parts.append("预算=" + budget)
    if profile.preferred_ingredients:
        parts.append("偏好成分=" + " / ".join(profile.preferred_ingredients))
    if profile.avoided_ingredients:
        parts.append("避开成分=" + " / ".join(profile.avoided_ingredients))
    if profile.finish_preferences:
        parts.append("肤感/妆效=" + " / ".join(profile.finish_preferences))
    return "；".join(parts) if parts else "暂无结构化画像"


def format_recommendation(item: Recommendation, index: int) -> str:
    reasons = "；".join(item.reasons[:3])
    cautions = f"\n  注意：{'；'.join(item.cautions[:2])}" if item.cautions else ""
    alternatives = f"\n  可替代：{'、'.join(item.alternatives)}" if item.alternatives else ""
    evidence = ""
    if item.evidence:
        evidence_titles = "；".join(chunk.title for chunk in item.evidence[:2])
        evidence = f"\n  知识依据：{evidence_titles}"
    live_insights = ""
    if item.live_insights:
        live_insights = f"\n  实时线索：{'；'.join(item.live_insights[:2])}"
    purchase_links = ""
    if item.purchase_links:
        link_text = "；".join(f"{link.platform}: {link.url}" for link in item.purchase_links[:2])
        purchase_links = f"\n  购买链接：{link_text}"
    return (
        f"{index}. {item.product.name} | {item.product.brand} | {item.product.category} | {item.product.price} 元\n"
        f"  推荐理由：{reasons}\n"
        f"  备注：{item.product.notes}{evidence}{live_insights}{purchase_links}{cautions}{alternatives}"
    )


def format_agent_response(response: AgentResponse, global_cautions: list[str]) -> str:
    lines: list[str] = []
    lines.append("=== 运行模式 ===")
    mode = "LLM 增强模式" if response.llm_enabled else "规则/RAG 模式（未检测到可用 LLM API 配置）"
    if response.live_tools_enabled:
        mode += " + Live Tools"
    lines.append(mode)
    lines.append("")

    lines.append("=== 用户画像 ===")
    lines.append(format_profile(response.profile))
    lines.append("")

    if response.clarifying_questions:
        lines.append("=== 建议先补充的信息 ===")
        for question in response.clarifying_questions:
            lines.append(f"- {question}")
        lines.append("")

    if response.retrieved_knowledge:
        lines.append("=== 检索到的知识库依据 ===")
        for chunk in response.retrieved_knowledge[:3]:
            lines.append(f"- {chunk.title}：{chunk.content}")
        lines.append("")

    if response.tool_events:
        lines.append("=== Tool Calling 记录 ===")
        for event in response.tool_events:
            lines.append(f"- {event.tool_name} [{event.status}] | 输入: {event.input_summary} | 输出: {event.output_summary}")
        lines.append("")

    if response.react_steps:
        lines.append("=== ReAct 轨迹 ===")
        for step in response.react_steps:
            lines.append(f"{step.step_index}. 思考：{step.thought}")
            lines.append(f"   动作：{step.action}")
            lines.append(f"   观察：{step.observation}")
        lines.append("")

    if response.session_summary:
        lines.append("=== 短期记忆摘要 ===")
        lines.append(response.session_summary)
        lines.append("")

    if response.long_term_memories:
        lines.append("=== 长期记忆片段 ===")
        for item in response.long_term_memories[:3]:
            lines.append(f"- {item['content']}")
        lines.append("")

    lines.append("=== 推荐结果 ===")
    if response.recommendations:
        for index, item in enumerate(response.recommendations, start=1):
            lines.append(format_recommendation(item, index))
            lines.append("")
    else:
        lines.append("暂无合适推荐。")
        lines.append("")

    if global_cautions:
        lines.append("=== 使用提醒 ===")
        for caution in global_cautions:
            lines.append(f"- {caution}")
        lines.append("")

    lines.append("=== 总结 ===")
    lines.append(response.summary)
    return "\n".join(lines).strip()
