from __future__ import annotations

import json
from dataclasses import dataclass

from .guardrails import build_global_cautions
from .llm import LLMClient
from .models import MultiAgentStep, PlanStep, Recommendation, UserProfile
from .parser import build_clarifying_questions
from .rag import retrieve_knowledge
from .recommender import recommend_products
from .research import ResearchOrchestrator


@dataclass(slots=True)
class MultiAgentResult:
    profile: UserProfile
    clarifying_questions: list[str]
    retrieved_knowledge: list
    recommendations: list[Recommendation]
    llm_summary: str
    tool_events: list
    react_steps: list
    multi_agent_steps: list[MultiAgentStep]
    global_cautions: list[str]
    plan_steps: list[str]
    self_check_notes: list[str]


class RequestPlannerAgent:
    name = "RequestPlannerAgent"
    responsibility = "在真正执行前为当前请求生成一个清晰的执行计划。"

    def run(self, query: str, profile: UserProfile) -> tuple[list[PlanStep], MultiAgentStep]:
        plan = [
            PlanStep("整合用户画像与记忆上下文"),
            PlanStep("判断是否需要追问并明确当前诉求"),
            PlanStep("从知识库和产品库中筛选候选商品"),
            PlanStep("如开启 live tools，补充网页线索和购买链接"),
            PlanStep("对结果做安全复核与最终自检"),
        ]
        if profile.desired_categories:
            plan[2].title = f"围绕 {','.join(profile.desired_categories)} 筛选候选商品"
        return plan, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"query={query[:80]}",
            output_summary=" -> ".join(step.title for step in plan),
        )


class TaskCoordinatorAgent:
    name = "TaskCoordinator"
    responsibility = "拆解用户请求，安排后续角色分工，并汇总最终协作结果。"

    def plan(self, query: str, profile: UserProfile) -> MultiAgentStep:
        tasks = [
            "画像分析",
            "诉求分析",
            "商品检索与排序",
            "购买信息收集",
            "安全复核",
        ]
        category_hint = ",".join(profile.desired_categories) if profile.desired_categories else "待补充品类"
        return MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"query={query[:80]} | category_hint={category_hint}",
            output_summary=" -> ".join(tasks),
        )


class ProfileAnalysisAgent:
    name = "ProfileAnalysisAgent"
    responsibility = "基于用户原话、短期记忆和长期记忆理解当前肤质状态与个体特征。"

    def run(
        self,
        query: str,
        profile: UserProfile,
        llm: LLMClient | None,
        memory_summary: str,
        long_term_memories: list[dict[str, str]],
    ) -> tuple[UserProfile, MultiAgentStep]:
        output_notes: list[str] = []
        refined = profile
        pre_knowledge = retrieve_knowledge(profile)
        if llm is not None:
            refined = llm.enhance_profile(query, profile, pre_knowledge)
            output_notes.append("使用 LLM 对画像做了补全与修正")
        if memory_summary:
            output_notes.append("结合了短期记忆摘要")
        if long_term_memories:
            output_notes.append(f"参考了 {len(long_term_memories[:3])} 条长期记忆")
        if not output_notes:
            output_notes.append("采用规则解析得到当前画像")
        return refined, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"skin={profile.skin_types or ['unknown']} | concerns={profile.concerns or ['unknown']}",
            output_summary="；".join(output_notes),
        )


class NeedAnalysisAgent:
    name = "NeedAnalysisAgent"
    responsibility = "识别用户当前最核心的购买诉求、缺失信息和决策重点。"

    def run(self, profile: UserProfile) -> tuple[list[str], MultiAgentStep]:
        clarifying_questions = build_clarifying_questions(profile)
        priorities: list[str] = []
        if profile.desired_categories:
            priorities.append("已识别目标品类")
        if profile.concerns:
            priorities.append("已识别核心诉求")
        if profile.budget_max is not None:
            priorities.append("已识别预算约束")
        if clarifying_questions:
            priorities.append(f"仍需补充 {len(clarifying_questions)} 个关键信息点")
        if not priorities:
            priorities.append("需求仍较模糊，需要进一步澄清")
        return clarifying_questions, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"category={profile.desired_categories or ['unknown']} | budget={profile.budget_max}",
            output_summary="；".join(priorities),
        )


class ProductSelectionAgent:
    name = "ProductSelectionAgent"
    responsibility = "结合用户状态、诉求、知识库和产品库筛选并排序候选商品。"

    def run(
        self,
        profile: UserProfile,
        top_k: int,
        llm: LLMClient | None,
    ) -> tuple[list, list[Recommendation], str, MultiAgentStep]:
        retrieved_knowledge = retrieve_knowledge(profile)
        recommendations = recommend_products(profile, top_k=top_k, retrieved_knowledge=retrieved_knowledge)
        llm_summary = ""
        if llm is not None and recommendations:
            recommendations, llm_summary = llm.rerank_and_explain(profile, recommendations, retrieved_knowledge)
        output = [
            f"检索到 {len(retrieved_knowledge)} 条知识片段",
            f"选出 {len(recommendations)} 个候选商品",
        ]
        if llm_summary:
            output.append("使用 LLM 对候选顺序做了复核")
        return retrieved_knowledge, recommendations, llm_summary, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"category={profile.desired_categories or ['unknown']} | concerns={profile.concerns or ['unknown']}",
            output_summary="；".join(output),
        )


class PurchaseLinkAgent:
    name = "PurchaseLinkAgent"
    responsibility = "为候选商品补充实时网页线索和购买链接。"

    def run(
        self,
        query: str,
        profile: UserProfile,
        recommendations: list[Recommendation],
        research: ResearchOrchestrator | None,
        top_k: int,
    ) -> tuple[list, list, MultiAgentStep]:
        if research is None:
            return [], [], MultiAgentStep(
                agent_name=self.name,
                responsibility=self.responsibility,
                input_summary="live tools disabled",
                output_summary="未开启实时工具，跳过购买链接收集",
            )
        tool_events, react_steps = research.enrich_recommendations(query, profile, recommendations, top_k=min(2, top_k))
        links_count = sum(len(item.purchase_links) for item in recommendations[: min(2, len(recommendations))])
        return tool_events, react_steps, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"top_k={min(2, top_k)} recommendations",
            output_summary=f"生成 {len(tool_events)} 条工具记录，收集到 {links_count} 个购买链接",
        )


class SafetyReviewerAgent:
    name = "SafetyReviewerAgent"
    responsibility = "对推荐结果做安全和约束复核，避免明显高风险或不合适的输出。"

    def run(self, profile: UserProfile, recommendations: list[Recommendation]) -> tuple[list[str], MultiAgentStep]:
        cautions = build_global_cautions(profile, recommendations)
        output = "；".join(cautions[:2]) if cautions else "未触发额外安全提醒"
        return cautions, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"recommendations={len(recommendations)}",
            output_summary=output,
        )


class ReflectionAgent:
    name = "ReflectionAgent"
    responsibility = "在最终输出前做 self-check，检查约束、风险和结果一致性。"

    def run(
        self,
        profile: UserProfile,
        recommendations: list[Recommendation],
        clarifying_questions: list[str],
    ) -> tuple[list[str], MultiAgentStep]:
        notes: list[str] = []
        for item in recommendations:
            if profile.budget_max is not None and item.product.price > profile.budget_max:
                notes.append(f"{item.product.name} 超出预算上限，建议仅作为进阶备选。")
            if set(profile.avoided_ingredients).intersection(item.product.hero_ingredients):
                notes.append(f"{item.product.name} 与用户避开成分存在冲突。")
        if clarifying_questions:
            notes.append(f"当前仍有 {len(clarifying_questions)} 个待补充信息点，推荐精度还有提升空间。")
        if not notes:
            notes.append("推荐结果与当前预算、肤质和禁忌信息整体一致。")
        return notes, MultiAgentStep(
            agent_name=self.name,
            responsibility=self.responsibility,
            input_summary=f"recommendations={len(recommendations)} | clarifications={len(clarifying_questions)}",
            output_summary="；".join(notes[:2]),
        )


class MultiAgentBeautyAdvisor:
    """Explicit multi-agent architecture layered over the existing recommendation system."""

    def __init__(self, llm: LLMClient | None, research: ResearchOrchestrator | None) -> None:
        self.llm = llm
        self.research = research
        self.planner = RequestPlannerAgent()
        self.coordinator = TaskCoordinatorAgent()
        self.profile_agent = ProfileAnalysisAgent()
        self.need_agent = NeedAnalysisAgent()
        self.product_agent = ProductSelectionAgent()
        self.purchase_agent = PurchaseLinkAgent()
        self.safety_agent = SafetyReviewerAgent()
        self.reflection_agent = ReflectionAgent()

    def run(
        self,
        query: str,
        profile: UserProfile,
        top_k: int,
        memory_summary: str = "",
        long_term_memories: list[dict[str, str]] | None = None,
    ) -> MultiAgentResult:
        long_term_memories = long_term_memories or []
        plan, planner_step = self.planner.run(query, profile)
        steps: list[MultiAgentStep] = [planner_step, self.coordinator.plan(query, profile)]
        _mark_done(plan, 0)

        profile, profile_step = self.profile_agent.run(
            query=query,
            profile=profile,
            llm=self.llm,
            memory_summary=memory_summary,
            long_term_memories=long_term_memories,
        )
        steps.append(profile_step)
        _mark_done(plan, 1)

        clarifying_questions, need_step = self.need_agent.run(profile)
        steps.append(need_step)
        _mark_done(plan, 2)

        retrieved_knowledge, recommendations, llm_summary, product_step = self.product_agent.run(
            profile=profile,
            top_k=top_k,
            llm=self.llm,
        )
        steps.append(product_step)

        tool_events, react_steps, purchase_step = self.purchase_agent.run(
            query=query,
            profile=profile,
            recommendations=recommendations,
            research=self.research,
            top_k=top_k,
        )
        steps.append(purchase_step)
        _mark_done(plan, 3)

        global_cautions, safety_step = self.safety_agent.run(profile, recommendations)
        steps.append(safety_step)
        self_check_notes, reflection_step = self.reflection_agent.run(
            profile=profile,
            recommendations=recommendations,
            clarifying_questions=clarifying_questions,
        )
        steps.append(reflection_step)
        _mark_done(plan, 4)

        return MultiAgentResult(
            profile=profile,
            clarifying_questions=clarifying_questions,
            retrieved_knowledge=retrieved_knowledge,
            recommendations=recommendations,
            llm_summary=llm_summary,
            tool_events=tool_events,
            react_steps=react_steps,
            multi_agent_steps=steps,
            global_cautions=global_cautions,
            plan_steps=[_format_plan_step(item) for item in plan],
            self_check_notes=self_check_notes,
        )


def _mark_done(plan: list[PlanStep], index: int) -> None:
    if 0 <= index < len(plan):
        plan[index].done = True


def _format_plan_step(step: PlanStep) -> str:
    prefix = "[x]" if step.done else "[ ]"
    return f"{prefix} {step.title}"
