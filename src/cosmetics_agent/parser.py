from __future__ import annotations

import re

from .models import Category, SkinType, UserProfile


SKIN_TYPE_KEYWORDS: dict[SkinType, tuple[str, ...]] = {
    "dry": ("干皮", "干肌", "沙漠皮", "起皮"),
    "oily": ("油皮", "大油皮", "易出油"),
    "combination": ("混油", "混合", "混干"),
    "sensitive": ("敏感肌", "敏肌", "易敏", "泛红", "敏感"),
    "acne_prone": ("痘肌", "闭口", "粉刺", "闷痘", "易长痘"),
    "normal": ("中性皮",),
    "unknown": (),
}

CONCERN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hydrating": ("补水", "保湿", "干燥"),
    "brightening": ("提亮", "美白", "暗沉"),
    "oil_control": ("控油", "出油"),
    "anti_acne": ("祛痘", "抗痘", "不闷痘", "闭口"),
    "barrier_support": ("修护", "维稳", "屏障"),
    "soothing": ("舒缓", "泛红", "镇静"),
    "uv_protection": ("防晒", "防晒霜", "防晒乳"),
    "light_coverage": ("轻薄底妆", "伪素颜"),
    "long_wear": ("持妆", "不脱妆"),
}

CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    "cleanser": ("洁面", "洗面奶"),
    "serum": ("精华",),
    "moisturizer": ("面霜", "乳液", "保湿霜"),
    "sunscreen": ("防晒", "防晒霜", "防晒乳"),
    "foundation": ("粉底", "底妆", "气垫"),
    "lip": ("口红", "唇釉", "唇泥"),
}

PREFERRED_INGREDIENTS = ("烟酰胺", "神经酰胺", "积雪草", "角鲨烷", "玻尿酸", "泛醇")
INGREDIENT_CANONICAL = {
    "烟酰胺": "niacinamide",
    "神经酰胺": "ceramide",
    "积雪草": "centella",
    "角鲨烷": "squalane",
    "玻尿酸": "hyaluronic acid",
    "泛醇": "panthenol",
    "酒精": "alcohol_denat",
    "香精": "fragrance",
    "精油": "essential_oil",
}

SCENARIO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "daily": ("通勤", "上班", "日常"),
    "summer": ("夏天", "夏季"),
    "winter": ("冬天", "秋冬"),
    "dating": ("约会", "见面", "出片"),
    "sensitive_period": ("烂脸", "敏感期", "换季"),
}


def parse_user_query(query: str) -> UserProfile:
    profile = UserProfile(raw_query=query)

    for skin_type, keywords in SKIN_TYPE_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            profile.skin_types.append(skin_type)

    for concern, keywords in CONCERN_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            profile.concerns.append(concern)

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            profile.desired_categories.append(category)

    for ingredient in PREFERRED_INGREDIENTS:
        if ingredient in query:
            profile.preferred_ingredients.append(INGREDIENT_CANONICAL[ingredient])

    if any(token in query for token in ("不要", "避开", "不想要", "别推荐")):
        for ingredient_cn, canonical in INGREDIENT_CANONICAL.items():
            if ingredient_cn in query:
                profile.avoided_ingredients.append(canonical)

    for scenario, keywords in SCENARIO_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            profile.scenarios.append(scenario)

    if any(token in query for token in ("清爽", "轻薄", "不黏", "不厚重")):
        profile.finish_preferences.append("light")
    if any(token in query for token in ("滋润", "润", "奶油肌", "光泽")):
        profile.finish_preferences.append("glowy")
    if any(token in query for token in ("雾面", "哑光")):
        profile.finish_preferences.append("matte")

    budget_range = re.search(r"(\d{2,4})\s*[-~到至]\s*(\d{2,4})", query)
    budget_cap = re.search(r"(预算|控制在|不超过|预算在)\s*(\d{2,4})", query)
    if budget_range:
        profile.budget_min = int(budget_range.group(1))
        profile.budget_max = int(budget_range.group(2))
    elif budget_cap:
        profile.budget_max = int(budget_cap.group(2))

    if not profile.desired_categories:
        if "防晒" in profile.concerns:
            profile.desired_categories.append("sunscreen")

    return profile


def build_clarifying_questions(profile: UserProfile) -> list[str]:
    questions: list[str] = []
    if not profile.desired_categories:
        questions.append("你现在更想找哪一类产品？比如防晒、精华、面霜、底妆或唇部产品。")
    if not profile.skin_types:
        questions.append("你的肤质更接近哪一种？比如干皮、油皮、混合皮、敏感肌或痘肌。")
    if profile.budget_max is None:
        questions.append("你的预算大概是多少？我可以按平价、进阶或高配方案来推荐。")
    if any(category in ("foundation", "sunscreen") for category in profile.desired_categories) and not profile.finish_preferences:
        questions.append("你更喜欢清爽轻薄、自然服帖，还是偏滋润/光泽的妆感或肤感？")
    return questions
