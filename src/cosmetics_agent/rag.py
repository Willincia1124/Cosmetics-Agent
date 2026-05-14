from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .models import KnowledgeChunk, Product, UserProfile


TOKEN_PATTERN = re.compile(r"[a-z0-9_+.-]+", re.IGNORECASE)
CN_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "防晒": ("防晒", "防晒霜", "防晒乳"),
    "油皮": ("油皮", "大油皮", "爱出油", "油光"),
    "混油": ("混油", "混油皮", "混合皮", "t区出油"),
    "痘肌": ("痘肌", "闭口", "粉刺", "长痘", "闷痘", "不致痘"),
    "敏感": ("敏感", "敏感肌", "易敏", "泛红"),
    "干皮": ("干皮", "干肌", "干燥", "拔干"),
    "通勤": ("通勤", "上班", "日常", "天天用"),
    "清爽": ("清爽", "轻薄", "成膜快", "不厚重", "不黏", "不搓泥"),
    "保湿": ("保湿", "补水", "滋润"),
    "修护": ("修护", "维稳", "屏障"),
    "底妆": ("底妆", "粉底", "气垫"),
    "雾面": ("雾面", "哑光"),
    "持妆": ("持妆", "不脱妆", "不斑驳"),
    "香精": ("香精",),
    "低刺激": ("低刺激", "温和"),
    "神经酰胺": ("神经酰胺",),
    "烟酰胺": ("烟酰胺",),
    "泛醇": ("泛醇",),
}


def _data_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "knowledge_base.jsonl"


@lru_cache(maxsize=1)
def load_knowledge_base() -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    with _data_path().open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            chunks.append(
                KnowledgeChunk(
                    id=raw["id"],
                    title=raw["title"],
                    category=raw["category"],
                    content=raw["content"],
                    tags=raw.get("tags", []),
                    product_ids=raw.get("product_ids", []),
                    concerns=raw.get("concerns", []),
                    skin_types=raw.get("skin_types", []),
                    ingredients=raw.get("ingredients", []),
                    scenarios=raw.get("scenarios", []),
                    finish_preferences=raw.get("finish_preferences", []),
                    evidence_type=raw.get("evidence_type", _infer_evidence_type(raw["category"])),
                )
            )
    return chunks


def retrieve_knowledge(profile: UserProfile, top_k: int = 5) -> list[KnowledgeChunk]:
    query_terms = build_query_terms(profile)
    if not query_terms:
        return []

    candidate_pool = _recall_chunks(profile, query_terms, recall_k=max(top_k * 3, 8))
    if not candidate_pool:
        return []
    reranked = _rerank_chunks(candidate_pool, query_terms, profile)
    return reranked[:top_k]


def retrieve_safety_knowledge(profile: UserProfile, top_k: int = 2) -> list[KnowledgeChunk]:
    query_terms = build_query_terms(profile)
    if not query_terms:
        return []
    safety_candidates = [
        chunk
        for chunk in load_knowledge_base()
        if chunk.category in {"safety", "repair"} or chunk.evidence_type == "safety"
    ]
    reranked = _rerank_chunks(safety_candidates, query_terms, profile, prefer_safety=True)
    return reranked[:top_k]


def _chunk_allowed_for_profile(chunk: KnowledgeChunk, profile: UserProfile) -> bool:
    if chunk.category in {"safety", "repair"} or chunk.evidence_type == "safety":
        return True
    if not profile.desired_categories:
        return True
    if chunk.category in profile.desired_categories:
        return True
    if set(profile.preferred_ingredients).intersection(chunk.ingredients):
        return True
    if set(profile.concerns).intersection(chunk.concerns):
        return True
    return False


def _recall_chunks(profile: UserProfile, query_terms: set[str], recall_k: int) -> list[KnowledgeChunk]:
    ranked: list[KnowledgeChunk] = []
    for chunk in load_knowledge_base():
        if not _chunk_allowed_for_profile(chunk, profile):
            continue
        score = _recall_score(chunk, query_terms, profile)
        if score <= 0:
            continue
        ranked.append(_clone_chunk_with_score(chunk, score))
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:recall_k]


def _rerank_chunks(
    chunks: list[KnowledgeChunk],
    query_terms: set[str],
    profile: UserProfile,
    prefer_safety: bool = False,
) -> list[KnowledgeChunk]:
    reranked: list[KnowledgeChunk] = []
    for chunk in chunks:
        score = _rerank_score(chunk, query_terms, profile, prefer_safety=prefer_safety)
        if score <= 0:
            continue
        reranked.append(_clone_chunk_with_score(chunk, score))
    reranked.sort(key=lambda item: item.score, reverse=True)
    return _dedupe_chunks(reranked)


def evidence_for_product(
    product: Product,
    profile: UserProfile,
    retrieved_chunks: list[KnowledgeChunk],
    top_k: int = 2,
) -> list[KnowledgeChunk]:
    relevant: list[KnowledgeChunk] = []
    for chunk in retrieved_chunks:
        if not _chunk_relevant_to_product(chunk, product, profile):
            continue
        score = chunk.score
        if product.id in chunk.product_ids:
            score += 3.0
        if product.category == chunk.category:
            score += 1.0
        elif chunk.category not in {"safety", "repair"}:
            score -= 1.0
        if set(product.hero_ingredients).intersection(chunk.ingredients):
            score += 1.0
        if set(profile.skin_types).intersection(chunk.skin_types):
            score += 0.5
        relevant.append(_clone_chunk_with_score(chunk, score))
    relevant.sort(key=lambda item: item.score, reverse=True)
    return relevant[:top_k]


def _chunk_relevant_to_product(chunk: KnowledgeChunk, product: Product, profile: UserProfile) -> bool:
    if product.id in chunk.product_ids:
        return True
    if chunk.category in {"safety", "repair"}:
        profile_skin_match = set(profile.skin_types).intersection(chunk.skin_types)
        product_skin_match = set(product.suitable_skin_types).intersection(chunk.skin_types)
        avoidance_match = set(profile.avoided_ingredients).intersection(product.free_from_ingredients)
        if profile_skin_match and product_skin_match:
            return True
        if avoidance_match and set(profile.avoided_ingredients).intersection(chunk.ingredients):
            return True
        return False
    if product.category != chunk.category:
        return False
    if set(product.hero_ingredients).intersection(chunk.ingredients):
        return True
    if set(product.suitable_skin_types).intersection(chunk.skin_types):
        return True
    if set(profile.scenarios).intersection(chunk.scenarios):
        return True
    return False


def build_query_terms(profile: UserProfile) -> set[str]:
    terms: set[str] = set(_tokenize(profile.raw_query))
    terms.update(profile.skin_types)
    terms.update(profile.concerns)
    terms.update(profile.desired_categories)
    terms.update(profile.preferred_ingredients)
    terms.update(profile.avoided_ingredients)
    terms.update(profile.finish_preferences)
    terms.update(profile.scenarios)
    for canonical, aliases in CN_TERM_ALIASES.items():
        if any(alias in profile.raw_query for alias in aliases):
            terms.add(canonical)
            terms.update(aliases)
    return {term for term in terms if term}


def build_evidence_reason(chunk: KnowledgeChunk, product: Product, profile: UserProfile) -> str:
    if chunk.category == "safety" or chunk.evidence_type == "safety":
        if set(profile.avoided_ingredients).intersection(product.free_from_ingredients):
            return "知识库提示这类人群更适合优先考虑避开特定刺激成分的配方。"
        return "知识库提示当前肤况更适合先走低刺激、保守路线。"
    if set(profile.skin_types).intersection(chunk.skin_types):
        return "知识库里有与当前肤质相匹配的选品建议。"
    if set(profile.concerns).intersection(chunk.concerns):
        return "知识库里有与当前核心诉求相匹配的功效建议。"
    if set(profile.scenarios).intersection(chunk.scenarios):
        return "知识库里有与当前使用场景相匹配的建议。"
    if set(product.hero_ingredients).intersection(chunk.ingredients):
        return "知识库中提到的关键成分与这款产品的核心成分一致。"
    return "知识库中有可支撑这款产品的相关选品依据。"


def _recall_score(chunk: KnowledgeChunk, query_terms: set[str], profile: UserProfile) -> float:
    searchable = _build_searchable_terms(chunk)
    overlap = query_terms.intersection(searchable)
    score = float(len(overlap))
    if set(profile.skin_types).intersection(chunk.skin_types):
        score += 1.0
    if set(profile.concerns).intersection(chunk.concerns):
        score += 1.0
    if set(profile.preferred_ingredients).intersection(chunk.ingredients):
        score += 0.8
    if set(profile.scenarios).intersection(chunk.scenarios):
        score += 0.8
    if set(profile.finish_preferences).intersection(chunk.finish_preferences):
        score += 0.6
    return score


def _rerank_score(
    chunk: KnowledgeChunk,
    query_terms: set[str],
    profile: UserProfile,
    prefer_safety: bool = False,
) -> float:
    searchable = _build_searchable_terms(chunk)
    overlap = len(query_terms.intersection(searchable))
    score = float(overlap)

    if set(profile.skin_types).intersection(chunk.skin_types):
        score += 1.5
    if set(profile.concerns).intersection(chunk.concerns):
        score += 1.5
    if set(profile.desired_categories).intersection({chunk.category}):
        score += 1.2
    elif profile.desired_categories and chunk.category not in {"safety", "repair"}:
        score -= 0.8
    if set(profile.preferred_ingredients).intersection(chunk.ingredients):
        score += 1.0
    if set(profile.scenarios).intersection(chunk.scenarios):
        score += 0.8
    if set(profile.finish_preferences).intersection(chunk.finish_preferences):
        score += 0.8
    if set(profile.avoided_ingredients).intersection(chunk.ingredients):
        score += 1.2 if prefer_safety or chunk.category == "safety" else 0.2
    if chunk.category == "repair" and any(item in profile.concerns for item in ("barrier_support", "soothing")):
        score += 0.8
    if prefer_safety and (chunk.category in {"safety", "repair"} or chunk.evidence_type == "safety"):
        score += 1.5
    return score


def _build_searchable_terms(chunk: KnowledgeChunk) -> set[str]:
    searchable = set(_tokenize(" ".join([chunk.title, chunk.content, " ".join(chunk.tags)])))
    searchable.update(chunk.tags)
    searchable.update(chunk.concerns)
    searchable.update(chunk.skin_types)
    searchable.update(chunk.ingredients)
    searchable.update(chunk.scenarios)
    searchable.update(chunk.finish_preferences)
    searchable.add(chunk.category)
    searchable.add(chunk.evidence_type)
    return searchable


def _dedupe_chunks(chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
    seen: set[str] = set()
    deduped: list[KnowledgeChunk] = []
    for chunk in chunks:
        signature = f"{chunk.category}:{chunk.title}"
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(chunk)
    return deduped


def _clone_chunk_with_score(chunk: KnowledgeChunk, score: float) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk.id,
        title=chunk.title,
        category=chunk.category,
        content=chunk.content,
        tags=list(chunk.tags),
        product_ids=list(chunk.product_ids),
        concerns=list(chunk.concerns),
        skin_types=list(chunk.skin_types),
        ingredients=list(chunk.ingredients),
        scenarios=list(chunk.scenarios),
        finish_preferences=list(chunk.finish_preferences),
        evidence_type=chunk.evidence_type,
        score=score,
    )


def _infer_evidence_type(category: str) -> str:
    if category == "safety":
        return "safety"
    if category == "repair":
        return "repair"
    return "general"


def _tokenize(text: str) -> list[str]:
    base_terms = TOKEN_PATTERN.findall(text.lower())
    cn_terms: list[str] = []
    for canonical, aliases in CN_TERM_ALIASES.items():
        if canonical in text or any(alias in text for alias in aliases):
            cn_terms.append(canonical)
            cn_terms.extend(alias for alias in aliases if alias in text)
    return base_terms + cn_terms
