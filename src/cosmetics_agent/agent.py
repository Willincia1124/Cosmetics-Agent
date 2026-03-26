from __future__ import annotations

from .formatter import format_agent_response
from .guardrails import build_global_cautions
from .llm import LLMClient
from .models import AgentResponse
from .memory import SessionMemory
from .parser import build_clarifying_questions, parse_user_query
from .rag import retrieve_knowledge
from .recommender import recommend_products
from .config import LLMConfig, ToolConfig
from .research import ResearchOrchestrator
from .toolbox import ResearchToolbox


class BeautyAdvisorAgent:
    """A lightweight multi-step beauty advisor agent for local CLI usage."""

    def __init__(self, memory: SessionMemory | None = None) -> None:
        self.memory = memory
        llm_config = LLMConfig.from_env()
        self.llm = LLMClient(llm_config) if llm_config is not None else None
        tool_config = ToolConfig.from_env()
        self.tool_config = tool_config
        self.research = (
            ResearchOrchestrator(ResearchToolbox(timeout_seconds=tool_config.timeout_seconds), llm=self.llm)
            if tool_config.enabled
            else None
        )

    def run(self, query: str, top_k: int = 3) -> AgentResponse:
        profile = parse_user_query(query)
        if self.memory is not None:
            profile = self.memory.merge(profile)
        clarifying_questions = build_clarifying_questions(profile)
        retrieved_knowledge = retrieve_knowledge(profile)
        llm_enabled = self.llm is not None

        if self.llm is not None:
            enhanced_profile = self.llm.enhance_profile(query, profile, retrieved_knowledge)
            profile = enhanced_profile
            clarifying_questions = build_clarifying_questions(profile)
            retrieved_knowledge = retrieve_knowledge(profile)

        recommendations = recommend_products(profile, top_k=top_k, retrieved_knowledge=retrieved_knowledge)
        llm_summary = ""
        if self.llm is not None and recommendations:
            recommendations, llm_summary = self.llm.rerank_and_explain(profile, recommendations, retrieved_knowledge)

        tool_events = []
        react_steps = []
        if self.research is not None:
            tool_events, react_steps = self.research.enrich_recommendations(query, profile, recommendations, top_k=min(2, top_k))

        summary = self._build_summary(profile, recommendations, clarifying_questions, retrieved_knowledge, llm_summary)
        response = AgentResponse(
            profile=profile,
            recommendations=recommendations,
            clarifying_questions=clarifying_questions,
            summary=summary,
            retrieved_knowledge=retrieved_knowledge,
            llm_enabled=llm_enabled,
            live_tools_enabled=self.research is not None,
            tool_events=tool_events,
            react_steps=react_steps,
        )
        if self.memory is not None:
            self.memory.remember_turn(query, response)
            response.session_summary = self.memory.get_session_summary()
            response.recent_messages = self.memory.get_recent_messages()
            response.long_term_memories = self.memory.get_long_term_memories(limit=5)
        return response

    def render(self, query: str, top_k: int = 3) -> str:
        response = self.run(query, top_k=top_k)
        global_cautions = build_global_cautions(response.profile, response.recommendations)
        return format_agent_response(response, global_cautions)

    def _build_summary(self, profile, recommendations, clarifying_questions, retrieved_knowledge, llm_summary) -> str:
        if llm_summary:
            summary = llm_summary
        elif recommendations:
            best = recommendations[0].product
            summary = f"当前最匹配的是 {best.name}，因为它在肤质适配、核心诉求和预算上整体更平衡。"
        else:
            summary = "这次没有找到足够匹配的候选，后续可以扩大产品库或补充更具体的需求。"

        if clarifying_questions:
            summary += " 如果你补充缺失信息，我可以把推荐进一步收窄。"

        if "sensitive" in profile.skin_types or "acne_prone" in profile.skin_types:
            summary += " 对敏感肌或痘肌，我会优先保守推荐、避免高风险组合。"

        if retrieved_knowledge:
            summary += f" 这次还额外参考了 {len(retrieved_knowledge)} 条知识库片段来增强推荐依据。"

        return summary
