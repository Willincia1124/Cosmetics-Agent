from __future__ import annotations

from .models import Recommendation, UserProfile


HIGH_RISK_TERMS = ("孕", "怀孕", "皮炎", "激素", "破皮", "烂脸", "医院")


def build_global_cautions(profile: UserProfile, recommendations: list[Recommendation]) -> list[str]:
    cautions: list[str] = []

    if any(term in profile.raw_query for term in HIGH_RISK_TERMS):
        cautions.append("你提到的情况偏敏感或带有医疗风险，建议把本推荐当作日常消费建议，并优先咨询医生或专业皮肤科意见。")

    if "sensitive" in profile.skin_types:
        cautions.append("如果你是敏感肌，建议先做局部试用，再决定是否长期使用。")

    if "acne_prone" in profile.skin_types:
        cautions.append("痘肌更适合从清爽、低刺激配方开始，避免一次叠加太多高活性产品。")

    if not recommendations:
        cautions.append("当前产品库里没有特别匹配的结果，后续可以扩充更多品牌和品类。")

    return cautions

