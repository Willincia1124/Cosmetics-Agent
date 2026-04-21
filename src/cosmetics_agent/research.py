from __future__ import annotations

from .models import ReActStep, Recommendation, ToolEvent, UserProfile
from .toolbox import ResearchToolbox, build_tool_event


class ResearchOrchestrator:
    """Runs live web tools to enrich recommendations with internet context."""

    def __init__(self, toolbox: ResearchToolbox, llm=None) -> None:
        self.toolbox = toolbox
        self.llm = llm

    def enrich_recommendations(
        self,
        query: str,
        profile: UserProfile,
        recommendations: list[Recommendation],
        top_k: int = 2,
    ) -> tuple[list[ToolEvent], list[ReActStep]]:
        llm_result = self._try_llm_tool_calling(query, profile, recommendations, top_k=top_k)
        if llm_result[0]:
            return llm_result

        events: list[ToolEvent] = []
        react_steps: list[ReActStep] = []

        if not recommendations:
            results = self.toolbox.search_web(query=query, top_k=5)
            events.append(
                build_tool_event(
                    tool_name="search_web",
                    status="success" if results else "empty",
                    input_summary=query,
                    output_summary=f"找到 {len(results)} 条网页结果",
                )
            )
            react_steps.append(
                ReActStep(
                    step_index=1,
                    thought="当前没有本地候选商品，先查找网页资料看看是否有可用线索。",
                    action=f"search_web(query={query})",
                    observation=f"检索到 {len(results)} 条网页结果。",
                )
            )
            return events, react_steps

        step_index = 1
        for item in recommendations[:top_k]:
            purchase_links = self.toolbox.get_purchase_links(
                product_name=item.product.name,
                brand=item.product.brand,
                search_query=_build_marketplace_search_query(profile, item),
                top_k=3,
            )
            item.purchase_links = purchase_links
            events.append(
                build_tool_event(
                    tool_name="get_purchase_links",
                    status="success" if purchase_links else "empty",
                    input_summary=f"{item.product.brand} {item.product.name}",
                    output_summary=f"解析到 {len(purchase_links)} 个购买链接",
                )
            )
            react_steps.append(
                ReActStep(
                    step_index=step_index,
                    thought=f"先为 {item.product.name} 找购买链接，确认是否有可靠的购买入口。",
                    action=f"get_purchase_links(product_name={item.product.name}, brand={item.product.brand})",
                    observation=f"找到 {len(purchase_links)} 个购买链接。",
                )
            )
            step_index += 1

            if purchase_links:
                info = self.toolbox.extract_product_info(purchase_links[0].url)
                if info is not None:
                    if info.summary:
                        item.live_insights.append(f"网页摘要：{info.summary}")
                    if info.price_text:
                        item.live_insights.append(f"网页价格线索：{info.price_text}")
                    events.append(
                        build_tool_event(
                            tool_name="extract_product_info",
                            status="success",
                            input_summary=purchase_links[0].url,
                            output_summary=(info.summary[:80] + "...") if len(info.summary) > 80 else (info.summary or "抽取到标题/价格"),
                        )
                    )
                    react_steps.append(
                        ReActStep(
                            step_index=step_index,
                            thought=f"已经有链接，再读取 {item.product.name} 的首个商品页，补充网页摘要和价格线索。",
                            action=f"extract_product_info(url={purchase_links[0].url})",
                            observation=(info.summary[:120] if info.summary else "抽取到了页面标题或价格线索。"),
                        )
                    )
                    step_index += 1

            if not item.live_insights:
                item.live_insights.append("暂未检索到足够稳定的实时网页摘要，建议以官方链接为准。")

        react_steps.append(
            ReActStep(
                step_index=step_index,
                thought="目前已经拿到主要购买线索和必要网页摘要，可以停止外部动作。",
                action="finish",
                observation="保留当前结果用于最终推荐展示。",
            )
        )
        return events, react_steps

    def _try_llm_tool_calling(
        self,
        query: str,
        profile: UserProfile,
        recommendations: list[Recommendation],
        top_k: int,
    ) -> tuple[list[ToolEvent], list[ReActStep]]:
        if self.llm is None or not recommendations:
            return [], []

        executed, react_steps = self.llm.run_react_tool_loop(query, profile, recommendations[:top_k], self.toolbox)
        if not executed:
            return [], react_steps

        events: list[ToolEvent] = []
        recommendation_map = {item.product.name: item for item in recommendations}
        for call in executed:
            tool_name = call["tool_name"]
            arguments = call["arguments"]
            result = call["result"]
            events.append(
                build_tool_event(
                    tool_name=tool_name,
                    status=call["status"],
                    input_summary=_summarize_tool_args(arguments),
                    output_summary=_summarize_tool_result(result),
                )
            )

            if tool_name == "get_purchase_links":
                product_name = str(arguments.get("product_name", "")).strip()
                recommendation = recommendation_map.get(product_name)
                if recommendation is not None:
                    links = result.get("results", [])
                    recommendation.purchase_links = [
                        self._build_purchase_link(item)
                        for item in links
                        if isinstance(item, dict)
                    ][:3]
            elif tool_name == "extract_product_info":
                extracted = result.get("result")
                if isinstance(extracted, dict):
                    url = str(extracted.get("source_url", ""))
                    for recommendation in recommendations:
                        if any(link.url == url for link in recommendation.purchase_links):
                            summary = str(extracted.get("summary", "")).strip()
                            price_text = str(extracted.get("price_text", "")).strip()
                            if summary:
                                recommendation.live_insights.append(f"网页摘要：{summary}")
                            if price_text:
                                recommendation.live_insights.append(f"网页价格线索：{price_text}")
        for recommendation in recommendations[:top_k]:
            if not recommendation.live_insights:
                recommendation.live_insights.append("暂未检索到足够稳定的实时网页摘要，建议以官方链接为准。")
        return events, react_steps

    @staticmethod
    def _build_purchase_link(payload: dict):
        from .models import PurchaseLink

        return PurchaseLink(
            title=str(payload.get("title", "")),
            url=str(payload.get("url", "")),
            platform=str(payload.get("platform", "")),
            price_text=str(payload.get("price_text", "")),
            seller_type=str(payload.get("seller_type", "")),
        )


def _summarize_tool_args(arguments: dict) -> str:
    return " | ".join(f"{key}={value}" for key, value in arguments.items())[:160]


def _summarize_tool_result(result: dict) -> str:
    if "results" in result and isinstance(result["results"], list):
        return f"返回 {len(result['results'])} 条结果"
    if "result" in result and isinstance(result["result"], dict):
        text = str(result["result"].get("summary", "") or result["result"].get("name", ""))
        return text[:80] or "返回 1 条结构化结果"
    if "error" in result:
        return str(result["error"])[:120]
    return "无结构化结果"


def _build_marketplace_search_query(profile: UserProfile, item: Recommendation) -> str:
    parts: list[str] = []
    if item.product.category:
        category_map = {
            "cleanser": "洁面",
            "serum": "精华",
            "moisturizer": "面霜 乳液",
            "sunscreen": "防晒霜",
            "foundation": "粉底液 底妆",
            "lip": "口红 唇釉",
        }
        parts.append(category_map.get(item.product.category, item.product.category))
    if "oily" in profile.skin_types or "combination" in profile.skin_types:
        parts.append("油皮 混油")
    if "acne_prone" in profile.skin_types:
        parts.append("痘肌 不闷痘")
    if "sensitive" in profile.skin_types:
        parts.append("敏感肌")
    if "light" in profile.finish_preferences:
        parts.append("清爽")
    if profile.concerns:
        concern_map = {
            "uv_protection": "防晒",
            "hydrating": "保湿",
            "barrier_support": "修护",
            "brightening": "提亮",
            "oil_control": "控油",
            "anti_acne": "祛痘",
            "soothing": "舒缓",
        }
        parts.extend(concern_map[item] for item in profile.concerns if item in concern_map)
    if profile.avoided_ingredients:
        if "fragrance" in profile.avoided_ingredients:
            parts.append("无香精")
        if "alcohol_denat" in profile.avoided_ingredients:
            parts.append("无酒精")
    if not parts:
        parts.extend([item.product.brand, item.product.name])
    return " ".join(part for part in parts if part).strip()
