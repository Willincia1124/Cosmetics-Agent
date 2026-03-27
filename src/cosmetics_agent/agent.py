from __future__ import annotations

from .formatter import format_agent_response
from .llm import LLMClient
from .models import AgentResponse
from .memory import SessionMemory
from .multi_agent import MultiAgentBeautyAdvisor
from .parser import parse_user_query
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
        self.multi_agent = MultiAgentBeautyAdvisor(llm=self.llm, research=self.research)

    def run(self, query: str, top_k: int = 3) -> AgentResponse:
        profile = parse_user_query(query)
        memory_summary = ""
        long_term_memories: list[dict[str, str]] = []
        if self.memory is not None:
            profile = self.memory.merge(profile)
            memory_summary = self.memory.get_session_summary()
            long_term_memories = self.memory.get_long_term_memories(limit=5)

        llm_enabled = self.llm is not None
        multi_result = self.multi_agent.run(
            query=query,
            profile=profile,
            top_k=top_k,
            memory_summary=memory_summary,
            long_term_memories=long_term_memories,
        )

        summary = self._build_summary(
            multi_result.profile,
            multi_result.recommendations,
            multi_result.clarifying_questions,
            multi_result.retrieved_knowledge,
            multi_result.llm_summary,
        )
        response = AgentResponse(
            profile=multi_result.profile,
            recommendations=multi_result.recommendations,
            clarifying_questions=multi_result.clarifying_questions,
            summary=summary,
            retrieved_knowledge=multi_result.retrieved_knowledge,
            llm_enabled=llm_enabled,
            live_tools_enabled=self.research is not None,
            tool_events=multi_result.tool_events,
            react_steps=multi_result.react_steps,
            multi_agent_steps=multi_result.multi_agent_steps,
            plan_steps=multi_result.plan_steps,
            self_check_notes=multi_result.self_check_notes,
        )
        if self.memory is not None:
            self.memory.remember_turn(query, response)
            response.session_summary = self.memory.get_session_summary()
            response.recent_messages = self.memory.get_recent_messages()
            response.long_term_memories = self.memory.get_long_term_memories(limit=5)
        return response

    def render(self, query: str, top_k: int = 3) -> str:
        response = self.run(query, top_k=top_k)
        global_cautions = self.multi_agent.safety_agent.run(response.profile, response.recommendations)[0]
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
