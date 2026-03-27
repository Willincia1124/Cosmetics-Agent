from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .agent import BeautyAdvisorAgent
from .guardrails import build_global_cautions


DEFAULT_EVAL_DATASET = Path(__file__).resolve().parents[2] / "data" / "eval_dataset.jsonl"


@dataclass(slots=True)
class EvalCase:
    case_id: str
    query: str
    description: str = ""
    top_k: int = 3
    expected_categories: list[str] = field(default_factory=list)
    budget_max: int | None = None
    avoided_ingredients: list[str] = field(default_factory=list)
    require_recommendation: bool = True
    require_clarification: bool = False
    require_safety_note: bool = False
    require_knowledge: bool = True
    require_plan: bool = True
    require_self_check: bool = True
    require_purchase_links: bool = False


@dataclass(slots=True)
class MetricResult:
    name: str
    passed: bool
    detail: str


@dataclass(slots=True)
class EvalCaseResult:
    case: EvalCase
    metrics: list[MetricResult]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.metrics)

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.metrics if item.passed)

    @property
    def total_count(self) -> int:
        return len(self.metrics)

    @property
    def score(self) -> float:
        if not self.metrics:
            return 1.0
        return self.passed_count / self.total_count


@dataclass(slots=True)
class EvalRunResult:
    case_results: list[EvalCaseResult]

    @property
    def passed_cases(self) -> int:
        return sum(1 for item in self.case_results if item.passed)

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def metric_passed(self) -> int:
        return sum(item.passed_count for item in self.case_results)

    @property
    def metric_total(self) -> int:
        return sum(item.total_count for item in self.case_results)

    @property
    def metric_score(self) -> float:
        if self.metric_total == 0:
            return 1.0
        return self.metric_passed / self.metric_total


def load_eval_cases(dataset_path: str | Path = DEFAULT_EVAL_DATASET) -> list[EvalCase]:
    path = Path(dataset_path)
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cases.append(
            EvalCase(
                case_id=item["case_id"],
                query=item["query"],
                description=item.get("description", ""),
                top_k=item.get("top_k", 3),
                expected_categories=item.get("expected_categories", []),
                budget_max=item.get("budget_max"),
                avoided_ingredients=item.get("avoided_ingredients", []),
                require_recommendation=item.get("require_recommendation", True),
                require_clarification=item.get("require_clarification", False),
                require_safety_note=item.get("require_safety_note", False),
                require_knowledge=item.get("require_knowledge", True),
                require_plan=item.get("require_plan", True),
                require_self_check=item.get("require_self_check", True),
                require_purchase_links=item.get("require_purchase_links", False),
            )
        )
    return cases


def run_evals(dataset_path: str | Path = DEFAULT_EVAL_DATASET, case_id: str | None = None) -> EvalRunResult:
    cases = load_eval_cases(dataset_path)
    if case_id is not None:
        cases = [item for item in cases if item.case_id == case_id]
    if not cases:
        raise ValueError(f"No eval cases found for case_id={case_id!r} in dataset={str(dataset_path)!r}")

    agent = BeautyAdvisorAgent(memory=None)
    results = [evaluate_case(agent, item) for item in cases]
    return EvalRunResult(case_results=results)


def evaluate_case(agent: BeautyAdvisorAgent, case: EvalCase) -> EvalCaseResult:
    response = agent.run(case.query, top_k=case.top_k)
    metrics: list[MetricResult] = []

    global_cautions = build_global_cautions(response.profile, response.recommendations)
    recommendation_count = len(response.recommendations)
    top_category = response.recommendations[0].product.category if response.recommendations else "none"
    max_price = max((item.product.price for item in response.recommendations), default=0)
    purchase_link_count = sum(len(item.purchase_links) for item in response.recommendations)
    has_ingredient_conflict = any(
        set(case.avoided_ingredients).intersection(item.product.hero_ingredients)
        for item in response.recommendations
    )

    if case.require_recommendation:
        metrics.append(
            MetricResult(
                name="has_recommendation",
                passed=recommendation_count > 0,
                detail=f"recommendation_count={recommendation_count}",
            )
        )

    if case.expected_categories:
        metrics.append(
            MetricResult(
                name="category_match",
                passed=top_category in case.expected_categories,
                detail=f"top_category={top_category}, expected={case.expected_categories}",
            )
        )

    if case.budget_max is not None:
        metrics.append(
            MetricResult(
                name="budget_ok",
                passed=not response.recommendations or response.recommendations[0].product.price <= case.budget_max,
                detail=f"top_price={response.recommendations[0].product.price if response.recommendations else 'none'}, budget_max={case.budget_max}, max_price_in_list={max_price}",
            )
        )

    if case.avoided_ingredients:
        metrics.append(
            MetricResult(
                name="avoid_ingredient_ok",
                passed=not has_ingredient_conflict,
                detail=f"avoided={case.avoided_ingredients}, conflict={has_ingredient_conflict}",
            )
        )

    if case.require_clarification:
        metrics.append(
            MetricResult(
                name="clarification_present",
                passed=bool(response.clarifying_questions),
                detail=f"clarifying_questions={len(response.clarifying_questions)}",
            )
        )

    if case.require_safety_note:
        metrics.append(
            MetricResult(
                name="safety_note_present",
                passed=bool(global_cautions),
                detail=f"global_cautions={len(global_cautions)}",
            )
        )

    if case.require_knowledge:
        metrics.append(
            MetricResult(
                name="rag_used",
                passed=bool(response.retrieved_knowledge),
                detail=f"knowledge_chunks={len(response.retrieved_knowledge)}",
            )
        )

    if case.require_plan:
        metrics.append(
            MetricResult(
                name="planner_used",
                passed=bool(response.plan_steps),
                detail=f"plan_steps={len(response.plan_steps)}",
            )
        )

    if case.require_self_check:
        metrics.append(
            MetricResult(
                name="self_check_used",
                passed=bool(response.self_check_notes),
                detail=f"self_check_notes={len(response.self_check_notes)}",
            )
        )

    if case.require_purchase_links:
        metrics.append(
            MetricResult(
                name="purchase_links_present",
                passed=purchase_link_count > 0,
                detail=f"purchase_links={purchase_link_count}",
            )
        )

    return EvalCaseResult(case=case, metrics=metrics)


def format_eval_run(result: EvalRunResult) -> str:
    lines: list[str] = []
    lines.append("=== Eval Summary ===")
    lines.append(
        f"cases_passed={result.passed_cases}/{result.total_cases} | metrics_passed={result.metric_passed}/{result.metric_total} | metric_score={result.metric_score:.2%}"
    )
    lines.append("")

    for case_result in result.case_results:
        header = f"[{'PASS' if case_result.passed else 'FAIL'}] {case_result.case.case_id} | score={case_result.score:.2%}"
        lines.append(header)
        if case_result.case.description:
            lines.append(f"desc: {case_result.case.description}")
        lines.append(f"query: {case_result.case.query}")
        for metric in case_result.metrics:
            status = "PASS" if metric.passed else "FAIL"
            lines.append(f"- {status} {metric.name}: {metric.detail}")
        lines.append("")

    return "\n".join(lines).strip()
