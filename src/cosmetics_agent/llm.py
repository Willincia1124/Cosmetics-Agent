from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict

from .config import LLMConfig
from .models import KnowledgeChunk, ReActStep, Recommendation, UserProfile


class LLMClient:
    """OpenAI-compatible lightweight client for free/low-cost providers."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def enhance_profile(self, query: str, profile: UserProfile, knowledge: list[KnowledgeChunk]) -> UserProfile:
        payload = self._chat_json(
            system_prompt=(
                "你是美妆导购 agent 的需求解析器。"
                "你的任务是基于用户原话、已有结构化画像和检索到的知识片段，补全更准确的用户画像。"
                "只返回 JSON，不要解释。"
            ),
            user_prompt=self._build_profile_prompt(query, profile, knowledge),
            schema_hint={
                "skin_types": [],
                "concerns": [],
                "desired_categories": [],
                "preferred_ingredients": [],
                "avoided_ingredients": [],
                "finish_preferences": [],
                "scenarios": [],
                "budget_min": None,
                "budget_max": None,
            },
        )
        if not payload:
            return profile

        merged = asdict(profile)
        for key, value in payload.items():
            if key not in merged or value in (None, [], ""):
                continue
            if isinstance(merged[key], list):
                merged[key] = _merge_unique(merged[key], [str(item) for item in value])
            else:
                merged[key] = value
        return UserProfile(**merged)

    def rerank_and_explain(
        self,
        profile: UserProfile,
        recommendations: list[Recommendation],
        knowledge: list[KnowledgeChunk],
    ) -> tuple[list[Recommendation], str]:
        payload = self._chat_json(
            system_prompt=(
                "你是美妆导购 agent 的复核决策器。"
                "请结合用户画像、候选商品和知识库依据，给出更合理的排序和简明解释。"
                "只返回 JSON，不要解释。"
            ),
            user_prompt=self._build_rerank_prompt(profile, recommendations, knowledge),
            schema_hint={
                "ordered_product_ids": [],
                "reason_overrides": {},
                "caution_overrides": {},
                "summary": "",
            },
        )
        if not payload:
            return recommendations, ""

        ordered_ids = [item for item in payload.get("ordered_product_ids", []) if isinstance(item, str)]
        reason_overrides = payload.get("reason_overrides", {})
        caution_overrides = payload.get("caution_overrides", {})
        summary = payload.get("summary", "") if isinstance(payload.get("summary"), str) else ""

        rec_map = {item.product.id: item for item in recommendations}
        reordered: list[Recommendation] = []
        for product_id in ordered_ids:
            recommendation = rec_map.pop(product_id, None)
            if recommendation is None:
                continue
            extra_reasons = reason_overrides.get(product_id, [])
            if isinstance(extra_reasons, list):
                recommendation.reasons = _merge_unique(recommendation.reasons, [str(item) for item in extra_reasons][:2])
            extra_cautions = caution_overrides.get(product_id, [])
            if isinstance(extra_cautions, list):
                recommendation.cautions = _merge_unique(recommendation.cautions, [str(item) for item in extra_cautions][:2])
            reordered.append(recommendation)
        reordered.extend(rec_map.values())
        return reordered, summary

    def run_react_tool_loop(
        self,
        query: str,
        profile: UserProfile,
        recommendations: list[Recommendation],
        toolbox,
        max_rounds: int = 4,
    ) -> tuple[list[dict], list[ReActStep]]:
        if not recommendations:
            return [], []

        candidate_text = json.dumps(
            [
                {
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "brand": item.product.brand,
                    "category": item.product.category,
                    "price": item.product.price,
                }
                for item in recommendations[:2]
            ],
            ensure_ascii=False,
        )
        prompt = (
            f"用户原话：{query}\n"
            f"用户画像：{json.dumps(asdict(profile), ensure_ascii=False)}\n"
            f"候选商品：{candidate_text}\n"
            "目标：为候选商品补充实时网页线索和购买链接。"
            "优先获取购买链接，其次在必要时提取商品页摘要。"
        )

        executed_calls: list[dict] = []
        react_steps: list[ReActStep] = []
        observations: list[str] = []
        for _ in range(max_rounds):
            decision = self._chat_json(
                system_prompt=(
                    "你是美妆导购 agent 的 ReAct 决策器。"
                    "请基于当前上下文，输出下一步的简短思考摘要、动作决策，以及需要的工具参数。"
                    "动作只能是 tool 或 finish。"
                    "如果用户已经获得足够稳定的购买链接或网页线索，就输出 finish。"
                ),
                user_prompt=(
                    f"{prompt}\n"
                    f"当前观察：{'; '.join(observations) if observations else '暂无'}\n"
                    f"可用工具：{json.dumps([tool['function']['name'] for tool in toolbox.tool_schemas()], ensure_ascii=False)}"
                ),
                schema_hint={
                    "thought": "",
                    "action": "tool",
                    "tool_name": "",
                    "tool_arguments": {},
                    "finish_reason": "",
                },
            )
            if not decision:
                break

            thought = str(decision.get("thought", "")).strip() or "继续检查候选商品的实时信息。"
            action = str(decision.get("action", "finish")).strip().lower()
            if action == "finish":
                react_steps.append(
                    ReActStep(
                        step_index=len(react_steps) + 1,
                        thought=thought,
                        action="finish",
                        observation=str(decision.get("finish_reason", "")).strip() or "当前信息已足够，停止工具调用。",
                    )
                )
                break

            tool_name = str(decision.get("tool_name", "")).strip()
            arguments = decision.get("tool_arguments", {})
            if not tool_name or not isinstance(arguments, dict):
                break
            try:
                result = toolbox.call(tool_name, arguments)
                status = "success" if result else "empty"
            except Exception as exc:
                result = {"error": str(exc)}
                status = "error"

            observation = _summarize_react_observation(result)
            observations.append(f"{tool_name}: {observation}")
            executed_calls.append(
                {
                    "tool_name": tool_name,
                    "status": status,
                    "arguments": arguments,
                    "result": result,
                }
            )
            react_steps.append(
                ReActStep(
                    step_index=len(react_steps) + 1,
                    thought=thought,
                    action=f"{tool_name}({json.dumps(arguments, ensure_ascii=False)})",
                    observation=observation,
                )
            )
        return executed_calls, react_steps

    def _chat_json(self, system_prompt: str, user_prompt: str, schema_hint: dict) -> dict | None:
        raw = self._chat_raw(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"请返回满足以下 JSON 结构的对象：\n{json.dumps(schema_hint, ensure_ascii=False)}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        if raw is None:
            return None

        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        if not isinstance(content, str):
            return None
        content = _strip_code_fence(content)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    def _chat_raw(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        response_format: dict | None = None,
    ) -> dict | None:
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            body["tools"] = tools
            if tool_choice is not None:
                body["tool_choice"] = tool_choice
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.provider == "openrouter":
            headers["HTTP-Referer"] = self.config.site_url
            headers["X-Title"] = self.config.app_name

        request = urllib.request.Request(
            self.config.base_url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    def _build_profile_prompt(self, query: str, profile: UserProfile, knowledge: list[KnowledgeChunk]) -> str:
        knowledge_text = "\n".join(f"- {chunk.title}: {chunk.content}" for chunk in knowledge[:3]) or "无"
        return (
            f"用户原话：{query}\n"
            f"已有画像：{json.dumps(asdict(profile), ensure_ascii=False)}\n"
            f"知识片段：\n{knowledge_text}\n"
            "要求：如果用户表达了隐含偏好，例如“通勤底妆”通常对应轻薄、持妆，可以补入合适字段；"
            "但不要臆造预算、肤质或用户没有表达过的明确禁忌。"
        )

    def _build_rerank_prompt(
        self,
        profile: UserProfile,
        recommendations: list[Recommendation],
        knowledge: list[KnowledgeChunk],
    ) -> str:
        candidates = []
        for item in recommendations:
            candidates.append(
                {
                    "product_id": item.product.id,
                    "name": item.product.name,
                    "category": item.product.category,
                    "price": item.product.price,
                    "benefits": item.product.benefits,
                    "suitable_skin_types": item.product.suitable_skin_types,
                    "finish": item.product.finish,
                    "hero_ingredients": item.product.hero_ingredients,
                    "notes": item.product.notes,
                    "current_reasons": item.reasons,
                    "current_cautions": item.cautions,
                }
            )
        knowledge_text = "\n".join(f"- {chunk.title}: {chunk.content}" for chunk in knowledge[:4]) or "无"
        return (
            f"用户画像：{json.dumps(asdict(profile), ensure_ascii=False)}\n"
            f"候选商品：{json.dumps(candidates, ensure_ascii=False)}\n"
            f"知识片段：\n{knowledge_text}\n"
            "要求：综合预算、肤质、功效、妆效、风险和知识依据进行复核排序。"
            "summary 用一句中文概括最推荐的原因。"
        )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    result = list(existing)
    for item in incoming:
        if item not in result:
            result.append(item)
    return result

def _summarize_react_observation(result: dict) -> str:
    if "results" in result and isinstance(result["results"], list):
        return f"工具返回 {len(result['results'])} 条结果。"
    if "result" in result and isinstance(result["result"], dict):
        text = str(result["result"].get("summary", "") or result["result"].get("name", ""))
        return text[:120] or "工具返回 1 条结构化结果。"
    if "error" in result:
        return f"工具报错：{str(result['error'])[:120]}"
    return "工具没有返回结构化结果。"
