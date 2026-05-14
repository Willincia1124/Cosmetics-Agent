from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .catalog import PRODUCTS
from .llm import LLMClient
from .models import EnrichmentRunReport, ExtractedProductInfo, Product, SearchResult, StagedKnowledgeCandidate
from .toolbox import ResearchToolbox


DEFAULT_STAGING_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_staging"
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_reports"
DEFAULT_SNAPSHOTS_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge_snapshots"
ALLOWED_EVIDENCE_TYPES = {"general", "safety", "repair"}

CONCERN_LABELS = {
    "uv_protection": "防晒",
    "lightweight": "轻薄肤感",
    "anti_acne": "痘肌维稳",
    "oil_control": "控油",
    "brightening": "提亮",
    "barrier_support": "修护",
    "soothing": "舒缓",
    "hydrating": "保湿",
    "long_wear": "持妆",
    "light_coverage": "轻薄底妆",
}
SKIN_TYPE_LABELS = {
    "oily": "油皮",
    "combination": "混油皮",
    "acne_prone": "痘肌",
    "sensitive": "敏感肌",
    "dry": "干皮",
    "normal": "中性皮",
}
SCENARIO_LABELS = {
    "daily": "通勤日常",
    "summer": "夏季",
    "winter": "秋冬",
    "dating": "约会场景",
    "sensitive_period": "敏感期",
}
FINISH_LABELS = {
    "light": "清爽轻薄",
    "matte": "雾面",
    "glowy": "滋润光泽",
}
CATEGORY_LABELS = {
    "sunscreen": "防晒产品",
    "serum": "精华",
    "moisturizer": "保湿产品",
    "foundation": "底妆产品",
    "lip": "唇部产品",
    "cleanser": "洁面产品",
}


class KnowledgeEnricher:
    def __init__(self, toolbox: ResearchToolbox, llm: LLMClient | None = None) -> None:
        self.toolbox = toolbox
        self.llm = llm

    def run(
        self,
        category: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        output_dir: str | Path | None = None,
        source_mode: str = "public_web",
    ) -> EnrichmentRunReport:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        staging_dir, reports_dir, _ = ensure_knowledge_dirs(output_dir)
        products = select_products(category=category, product_id=product_id, limit=limit)

        staged: list[StagedKnowledgeCandidate] = []
        failed_products: list[dict[str, str]] = []
        generated = 0
        rejected = 0

        for product in products:
            try:
                context = self._collect_context(product)
                candidates = self._generate_candidates(product, context, run_id)
                generated += len(candidates)
                for candidate in candidates:
                    normalized = validate_candidate(candidate)
                    if normalized is None:
                        rejected += 1
                        continue
                    staged.append(normalized)
            except Exception as exc:
                failed_products.append({"product_id": product.id, "error": str(exc)})

        deduped = dedupe_candidates(staged)
        deduped_count = max(0, len(staged) - len(deduped))
        report = EnrichmentRunReport(
            run_id=run_id,
            source_mode=source_mode,
            generated_candidates=generated,
            kept_candidates=len(deduped),
            rejected_candidates=rejected,
            deduped_candidates=deduped_count,
            processed_products=len(products),
            failed_products=failed_products,
        )

        output_file = staging_dir / f"{run_id}.jsonl"
        report_file = reports_dir / f"{run_id}.json"
        report.output_file = str(output_file)
        report.report_file = str(report_file)

        if not dry_run:
            write_candidates(output_file, deduped)
            write_report(report_file, report)
        return report

    def _collect_context(self, product: Product) -> dict[str, object]:
        web_results = []
        product_results = []
        extracted_infos: list[ExtractedProductInfo] = []
        for query in build_research_queries(product):
            web_results.extend(self.toolbox.search_web(query=query, top_k=3))
        product_results = self.toolbox.search_products(product_name=product.name, brand=product.brand, top_k=3)
        for result in product_results[:2]:
            info = self.toolbox.extract_product_info(result.url)
            if info is not None:
                extracted_infos.append(info)
        return {
            "web_results": unique_search_results(web_results),
            "product_results": unique_search_results(product_results),
            "extracted_infos": extracted_infos,
        }

    def _generate_candidates(
        self,
        product: Product,
        context: dict[str, object],
        run_id: str,
    ) -> list[StagedKnowledgeCandidate]:
        rule_candidates = build_rule_candidates(product, context, run_id)
        if self.llm is None:
            return rule_candidates
        rewritten = self._rewrite_with_llm(product, context, rule_candidates)
        return rewritten or rule_candidates

    def _rewrite_with_llm(
        self,
        product: Product,
        context: dict[str, object],
        candidates: list[StagedKnowledgeCandidate],
    ) -> list[StagedKnowledgeCandidate]:
        web_results = context.get("web_results", [])
        extracted_infos = context.get("extracted_infos", [])
        prompt = {
            "product": asdict(product),
            "web_results": [asdict(item) for item in web_results[:3]],
            "extracted_infos": [asdict(item) for item in extracted_infos[:2]],
            "candidates": [asdict(item) for item in candidates],
        }
        payload = self.llm._chat_json(  # noqa: SLF001
            system_prompt=(
                "你是美妆知识库 enrichment 助手。"
                "你只能基于给定商品信息和网页摘要对候选知识条目做更自然的重写。"
                "不得发明不存在于输入里的品牌、成分、场景和结论。"
                "只返回 JSON。"
            ),
            user_prompt=json.dumps(prompt, ensure_ascii=False),
            schema_hint={"candidates": [asdict(candidates[0])] if candidates else []},
        )
        if not payload or not isinstance(payload.get("candidates"), list):
            return candidates
        rewritten: list[StagedKnowledgeCandidate] = []
        for item in payload["candidates"]:
            try:
                rewritten.append(StagedKnowledgeCandidate(**item))
            except TypeError:
                continue
        return rewritten


def ensure_knowledge_dirs(output_dir: str | Path | None = None) -> tuple[Path, Path, Path]:
    base = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "data"
    staging_dir = base / "knowledge_staging"
    reports_dir = base / "knowledge_reports"
    snapshots_dir = base / "knowledge_snapshots"
    for path in (staging_dir, reports_dir, snapshots_dir):
        path.mkdir(parents=True, exist_ok=True)
    return staging_dir, reports_dir, snapshots_dir


def select_products(category: str | None, product_id: str | None, limit: int | None) -> list[Product]:
    products = PRODUCTS
    if category:
        products = [item for item in products if item.category == category]
    if product_id:
        products = [item for item in products if item.id == product_id]
    if limit is not None:
        products = products[: max(0, limit)]
    return products


def build_research_queries(product: Product) -> list[str]:
    queries = [
        f"{product.brand} {product.name}",
        f"{product.brand} {product.category} {' '.join(product.hero_ingredients[:2])}".strip(),
    ]
    if product.suitable_skin_types:
        skin = SKIN_TYPE_LABELS.get(product.suitable_skin_types[0], product.suitable_skin_types[0])
        concern = CONCERN_LABELS.get(product.benefits[0], product.benefits[0]) if product.benefits else product.category
        queries.append(f"{skin} {product.category} {concern}")
    return [query for query in queries if query.strip()]


def build_rule_candidates(
    product: Product,
    context: dict[str, object],
    run_id: str,
) -> list[StagedKnowledgeCandidate]:
    web_results: list[SearchResult] = context.get("web_results", [])  # type: ignore[assignment]
    extracted_infos: list[ExtractedProductInfo] = context.get("extracted_infos", [])  # type: ignore[assignment]
    source_urls = [item.url for item in web_results[:3]] + [item.source_url for item in extracted_infos[:2]]
    source_titles = [item.title for item in web_results[:3]] + [item.name for item in extracted_infos[:2]]

    candidates: list[StagedKnowledgeCandidate] = []
    general_title = build_general_title(product)
    general_content = build_general_content(product)
    candidates.append(
        build_candidate(
            product=product,
            title=general_title,
            category=product.category,
            evidence_type="general",
            content=general_content,
            source_urls=source_urls,
            source_titles=source_titles,
            run_id=run_id,
        )
    )

    if should_generate_safety(product):
        candidates.append(
            build_candidate(
                product=product,
                title=build_safety_title(product),
                category="safety",
                evidence_type="safety",
                content=build_safety_content(product),
                source_urls=source_urls,
                source_titles=source_titles,
                run_id=run_id,
            )
        )

    if should_generate_repair(product):
        candidates.append(
            build_candidate(
                product=product,
                title=build_repair_title(product),
                category="repair",
                evidence_type="repair",
                content=build_repair_content(product),
                source_urls=source_urls,
                source_titles=source_titles,
                run_id=run_id,
            )
        )
    return candidates


def build_candidate(
    product: Product,
    title: str,
    category: str,
    evidence_type: str,
    content: str,
    source_urls: list[str],
    source_titles: list[str],
    run_id: str,
) -> StagedKnowledgeCandidate:
    confidence_score, quality_flags = score_candidate_fields(product, evidence_type, source_urls)
    tags = sorted({*product.tags[:3], *extract_tags_from_title(title)})
    candidate = StagedKnowledgeCandidate(
        id=build_candidate_id(product.id, evidence_type, title),
        title=title,
        category=category,
        tags=tags,
        product_ids=[product.id],
        concerns=list(product.benefits[:4]),
        skin_types=list(product.suitable_skin_types[:4]),
        ingredients=list(product.hero_ingredients[:4]),
        scenarios=infer_scenarios(product),
        finish_preferences=infer_finish_preferences(product),
        evidence_type=evidence_type,
        content=content,
        source_urls=dedupe_preserve_order(source_urls),
        source_titles=dedupe_preserve_order(source_titles),
        generator_product_id=product.id,
        generator_product_name=product.name,
        confidence_score=confidence_score,
        quality_flags=quality_flags,
        dedupe_key=build_dedupe_key(category, title),
        run_id=run_id,
    )
    return candidate


def build_general_title(product: Product) -> str:
    skin_label = first_label(product.suitable_skin_types, SKIN_TYPE_LABELS, fallback="对应肤质")
    category_label = CATEGORY_LABELS.get(product.category, product.category)
    benefit_label = first_label(product.benefits, CONCERN_LABELS, fallback="核心诉求")
    return f"{skin_label}更适合关注{benefit_label}的{category_label}"


def build_general_content(product: Product) -> str:
    skin_text = "、".join(filter(None, [SKIN_TYPE_LABELS.get(item, item) for item in product.suitable_skin_types[:3]]))
    concern_text = "、".join(filter(None, [CONCERN_LABELS.get(item, item) for item in product.benefits[:3]]))
    ingredient_text = "、".join(product.hero_ingredients[:3])
    category_text = CATEGORY_LABELS.get(product.category, product.category)
    notes = product.notes or "整体定位偏均衡。"
    return (
        f"{skin_text}在选择这类{category_text}时，通常会优先考虑{concern_text}。"
        f"这款产品的核心成分包括{ingredient_text}，{notes}"
    )


def build_safety_title(product: Product) -> str:
    if "fragrance" in product.free_from_ingredients:
        return "敏感肌或成分避雷用户可优先考虑无香精路线"
    return f"{product.category}选品时更适合先做低刺激和耐受性判断"


def build_safety_content(product: Product) -> str:
    free_from = "、".join(product.free_from_ingredients[:3]) or "高刺激成分"
    return (
        f"如果用户属于敏感肌、痘肌或有明确成分避雷诉求，通常更适合优先关注是否避开{free_from}。"
        f"{product.notes or '建议先局部试用，再观察肤感与耐受。'}"
    )


def build_repair_title(product: Product) -> str:
    return "修护型诉求用户可优先关注屏障支持和舒缓成分"


def build_repair_content(product: Product) -> str:
    ingredients = "、".join(product.hero_ingredients[:3]) or "修护型成分"
    return (
        f"当用户处于敏感期、换季期或屏障不稳定时，通常会优先考虑含有{ingredients}的产品。"
        f"{product.notes or '这类产品更偏向稳定肤况，而不是追求刺激性较高的速效功效。'}"
    )


def should_generate_safety(product: Product) -> bool:
    trigger_terms = {"acne_prone", "sensitive"}
    return bool(trigger_terms.intersection(product.suitable_skin_types) or product.free_from_ingredients)


def should_generate_repair(product: Product) -> bool:
    repair_terms = {"barrier_support", "soothing", "hydrating"}
    repair_ingredients = {"ceramide", "panthenol", "cholesterol", "centella"}
    return bool(repair_terms.intersection(product.benefits) or repair_ingredients.intersection(product.hero_ingredients))


def infer_scenarios(product: Product) -> list[str]:
    scenarios: list[str] = []
    for tag in product.tags:
        if tag in {"通勤", "晨洁"}:
            scenarios.append("daily")
        if tag in {"夏天"}:
            scenarios.append("summer")
        if tag in {"秋冬", "换季"}:
            scenarios.append("winter")
        if tag in {"约会"}:
            scenarios.append("dating")
    if "sensitive" in product.suitable_skin_types or "泛红" in product.tags:
        scenarios.append("sensitive_period")
    return dedupe_preserve_order(scenarios)


def infer_finish_preferences(product: Product) -> list[str]:
    mapping = {
        "light": "light",
        "gel": "light",
        "natural": "light",
        "matte": "matte",
        "glowy": "glowy",
        "rich": "glowy",
        "cream": "glowy",
    }
    value = mapping.get(product.finish)
    return [value] if value else []


def score_candidate_fields(product: Product, evidence_type: str, source_urls: list[str]) -> tuple[float, list[str]]:
    score = 0.4
    flags: list[str] = []
    if source_urls:
        score += 0.25
    else:
        flags.append("low_source_coverage")
    if product.hero_ingredients:
        score += 0.15
    if product.suitable_skin_types:
        score += 0.1
    if product.notes:
        score += 0.1
    if evidence_type in {"safety", "repair"}:
        score += 0.05
    if len(source_urls) < 2:
        flags.append("low_confidence")
    return min(score, 1.0), flags


def validate_candidate(candidate: StagedKnowledgeCandidate) -> StagedKnowledgeCandidate | None:
    if candidate.evidence_type not in ALLOWED_EVIDENCE_TYPES:
        return None
    if not candidate.product_ids:
        return None
    if not candidate.category or not candidate.content.strip():
        return None
    if len(candidate.content.strip()) < 24:
        return None
    if is_overly_generic(candidate.content):
        candidate.quality_flags = dedupe_preserve_order([*candidate.quality_flags, "generic_content"])
        return None
    if candidate.evidence_type == "general" and candidate.category in {"safety", "repair"}:
        return None
    if candidate.evidence_type in {"safety", "repair"} and candidate.category not in {"safety", "repair"}:
        candidate.category = candidate.evidence_type
    candidate.source_urls = dedupe_preserve_order(candidate.source_urls)
    candidate.source_titles = dedupe_preserve_order(candidate.source_titles)
    candidate.tags = dedupe_preserve_order(candidate.tags)
    candidate.concerns = dedupe_preserve_order(candidate.concerns)
    candidate.skin_types = dedupe_preserve_order(candidate.skin_types)
    candidate.ingredients = dedupe_preserve_order(candidate.ingredients)
    candidate.scenarios = dedupe_preserve_order(candidate.scenarios)
    candidate.finish_preferences = dedupe_preserve_order(candidate.finish_preferences)
    return candidate


def dedupe_candidates(candidates: list[StagedKnowledgeCandidate]) -> list[StagedKnowledgeCandidate]:
    kept: dict[str, StagedKnowledgeCandidate] = {}
    for candidate in candidates:
        key = f"{candidate.dedupe_key}:{','.join(candidate.product_ids)}"
        existing = kept.get(key)
        if existing is None or candidate.confidence_score > existing.confidence_score:
            kept[key] = candidate
    return sorted(kept.values(), key=lambda item: (item.generator_product_id, item.evidence_type, item.title))


def write_candidates(path: Path, candidates: list[StagedKnowledgeCandidate]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in candidates:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def write_report(path: Path, report: EnrichmentRunReport) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(report), handle, ensure_ascii=False, indent=2)


def unique_search_results(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for item in results:
        key = item.url
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def build_candidate_id(product_id: str, evidence_type: str, title: str) -> str:
    digest = hashlib.sha1(f"{product_id}:{evidence_type}:{normalize_title(title)}".encode("utf-8")).hexdigest()[:10]
    return f"kb-{product_id}-{evidence_type}-{digest}"


def build_dedupe_key(category: str, title: str) -> str:
    return f"{category}:{normalize_title(title)}"


def normalize_title(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", "", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]", "", lowered)
    return lowered


def is_overly_generic(text: str) -> bool:
    generic_markers = ("综合表现均衡", "整体定位偏均衡", "可作为备选")
    return any(marker in text for marker in generic_markers)


def extract_tags_from_title(title: str) -> list[str]:
    candidates = ["清爽", "保湿", "修护", "敏感肌", "痘肌", "底妆", "防晒", "通勤", "雾面"]
    return [item for item in candidates if item in title]


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def first_label(values: list[str], mapping: dict[str, str], fallback: str) -> str:
    for value in values:
        if value in mapping:
            return mapping[value]
    return fallback
