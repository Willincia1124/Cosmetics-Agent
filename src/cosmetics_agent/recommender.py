from __future__ import annotations

from .catalog import PRODUCTS
from .models import KnowledgeChunk, Product, Recommendation, UserProfile
from .rag import evidence_for_product


def retrieve_candidates(profile: UserProfile) -> list[Product]:
    candidates = PRODUCTS
    if profile.desired_categories:
        candidates = [product for product in candidates if product.category in profile.desired_categories]
    return candidates


def score_product(
    product: Product,
    profile: UserProfile,
    retrieved_knowledge: list[KnowledgeChunk] | None = None,
) -> Recommendation:
    score = 0.0
    reasons: list[str] = []
    cautions: list[str] = []
    evidence: list[KnowledgeChunk] = []

    if profile.budget_max is not None:
        if product.price <= profile.budget_max:
            score += 2.0
            reasons.append(f"价格 {product.price} 元，在你的预算范围内")
        else:
            score -= 3.0
            cautions.append(f"价格 {product.price} 元，超出当前预算上限")

    if profile.budget_min is not None and product.price >= profile.budget_min:
        score += 0.5

    if not profile.budget_min and not profile.budget_max:
        score += 0.5

    skin_match = set(profile.skin_types).intersection(product.suitable_skin_types)
    if skin_match:
        score += 3.0
        reasons.append("产品适配你的肤质特征")

    skin_conflict = set(profile.skin_types).intersection(product.avoid_for_skin_types)
    if skin_conflict:
        score -= 4.0
        cautions.append("产品质地或定位与你的肤质存在冲突")

    matched_concerns = set(profile.concerns).intersection(product.benefits)
    if matched_concerns:
        score += 3.0
        reasons.append("核心功效和你的诉求比较匹配")

    preferred = set(profile.preferred_ingredients).intersection(product.hero_ingredients)
    if preferred:
        score += 1.5
        reasons.append("含有你偏好的成分")

    avoided = set(profile.avoided_ingredients).intersection(product.hero_ingredients)
    if avoided:
        score -= 5.0
        cautions.append("包含你明确想避开的成分")

    matching_free_from = set(profile.avoided_ingredients).intersection(product.free_from_ingredients)
    if matching_free_from:
        score += 1.5
        reasons.append("配方避开了你明确不想要的成分")

    if "light" in profile.finish_preferences and product.finish in {"light", "gel", "matte", "natural"}:
        score += 1.0
        reasons.append("肤感或妆效偏清爽轻薄")
    if "glowy" in profile.finish_preferences and product.finish in {"glowy", "cream", "rich"}:
        score += 1.0
        reasons.append("肤感或妆效偏滋润/光泽")
    if "matte" in profile.finish_preferences and product.finish == "matte":
        score += 1.0
        reasons.append("妆效偏雾面")

    if "daily" in profile.scenarios and "daily" in product.benefits:
        score += 0.5
    if "summer" in profile.scenarios and "清爽" in product.tags:
        score += 0.5
    if "winter" in profile.scenarios and any(tag in product.tags for tag in ("保湿", "秋冬")):
        score += 0.5

    if retrieved_knowledge:
        evidence = evidence_for_product(product, profile, retrieved_knowledge)
        if evidence:
            score += min(2.0, 0.8 * len(evidence))
            reasons.append("命中了与该产品相关的知识库依据")

    if not reasons:
        reasons.append("综合表现均衡，可作为备选")

    return Recommendation(product=product, score=score, reasons=reasons, cautions=cautions, evidence=evidence)


def recommend_products(
    profile: UserProfile,
    top_k: int = 3,
    retrieved_knowledge: list[KnowledgeChunk] | None = None,
) -> list[Recommendation]:
    scored = [score_product(product, profile, retrieved_knowledge) for product in retrieve_candidates(profile)]
    filtered = [item for item in scored if item.score > -2.5]
    ranked = sorted(filtered, key=lambda item: item.score, reverse=True)
    top_items = ranked[:top_k]
    names = [item.product.name for item in top_items]
    for item in top_items:
        item.alternatives = [name for name in names if name != item.product.name][:2]
    return top_items
