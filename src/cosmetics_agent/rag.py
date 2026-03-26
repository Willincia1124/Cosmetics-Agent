from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .models import KnowledgeChunk, Product, UserProfile


TOKEN_PATTERN = re.compile(r"[a-z0-9_+.-]+", re.IGNORECASE)


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
                )
            )
    return chunks


def retrieve_knowledge(profile: UserProfile, top_k: int = 5) -> list[KnowledgeChunk]:
    query_terms = build_query_terms(profile)
    if not query_terms:
        return []

    ranked: list[KnowledgeChunk] = []
    for chunk in load_knowledge_base():
        if not _chunk_allowed_for_profile(chunk, profile):
            continue
        score = score_chunk(chunk, query_terms, profile)
        if score <= 0:
            continue
        ranked.append(
            KnowledgeChunk(
                id=chunk.id,
                title=chunk.title,
                category=chunk.category,
                content=chunk.content,
                tags=list(chunk.tags),
                product_ids=list(chunk.product_ids),
                concerns=list(chunk.concerns),
                skin_types=list(chunk.skin_types),
                ingredients=list(chunk.ingredients),
                score=score,
            )
        )
    return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]


def _chunk_allowed_for_profile(chunk: KnowledgeChunk, profile: UserProfile) -> bool:
    if not profile.desired_categories:
        return True
    if chunk.category in profile.desired_categories or chunk.category in {"safety", "repair"}:
        return True
    if set(profile.preferred_ingredients).intersection(chunk.ingredients):
        return True
    return False


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
        if score > chunk.score:
            relevant.append(
                KnowledgeChunk(
                    id=chunk.id,
                    title=chunk.title,
                    category=chunk.category,
                    content=chunk.content,
                    tags=list(chunk.tags),
                    product_ids=list(chunk.product_ids),
                    concerns=list(chunk.concerns),
                    skin_types=list(chunk.skin_types),
                    ingredients=list(chunk.ingredients),
                    score=score,
                )
            )
    return sorted(relevant, key=lambda item: item.score, reverse=True)[:top_k]


def _chunk_relevant_to_product(chunk: KnowledgeChunk, product: Product, profile: UserProfile) -> bool:
    if product.id in chunk.product_ids:
        return True
    if chunk.category in {"safety", "repair"} and set(profile.skin_types).intersection(chunk.skin_types):
        return True
    if product.category != chunk.category:
        return False
    if set(product.hero_ingredients).intersection(chunk.ingredients):
        return True
    if set(product.suitable_skin_types).intersection(chunk.skin_types):
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
    return {term for term in terms if term}


def score_chunk(chunk: KnowledgeChunk, query_terms: set[str], profile: UserProfile) -> float:
    score = 0.0
    searchable = set(_tokenize(" ".join([chunk.title, chunk.content, " ".join(chunk.tags)])))
    searchable.update(chunk.tags)
    searchable.update(chunk.concerns)
    searchable.update(chunk.skin_types)
    searchable.update(chunk.ingredients)
    searchable.add(chunk.category)

    overlap = query_terms.intersection(searchable)
    score += float(len(overlap))

    if set(profile.skin_types).intersection(chunk.skin_types):
        score += 1.5
    if set(profile.concerns).intersection(chunk.concerns):
        score += 1.5
    if set(profile.desired_categories).intersection({chunk.category}):
        score += 1.0
    elif profile.desired_categories and chunk.category not in {"safety", "repair"}:
        score -= 1.5
    if set(profile.preferred_ingredients).intersection(chunk.ingredients):
        score += 1.0
    if set(profile.avoided_ingredients).intersection(chunk.ingredients) and chunk.category == "safety":
        score += 0.5

    return score


def _tokenize(text: str) -> list[str]:
    base_terms = TOKEN_PATTERN.findall(text.lower())
    cn_terms: list[str] = []
    known_cn_tokens = (
        "防晒",
        "油皮",
        "混油皮",
        "混油",
        "痘肌",
        "敏感肌",
        "敏感",
        "干皮",
        "通勤",
        "清爽",
        "保湿",
        "修护",
        "维稳",
        "底妆",
        "雾面",
        "持妆",
        "香精",
        "低刺激",
        "神经酰胺",
        "烟酰胺",
        "泛醇",
    )
    for token in known_cn_tokens:
        if token in text:
            cn_terms.append(token)
    return base_terms + cn_terms
