from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SkinType = Literal["dry", "oily", "combination", "sensitive", "acne_prone", "normal", "unknown"]
Category = Literal["cleanser", "serum", "moisturizer", "sunscreen", "foundation", "lip"]


@dataclass(slots=True)
class Product:
    id: str
    name: str
    brand: str
    category: Category
    price: int
    benefits: list[str]
    suitable_skin_types: list[SkinType]
    avoid_for_skin_types: list[SkinType]
    finish: str = ""
    tags: list[str] = field(default_factory=list)
    hero_ingredients: list[str] = field(default_factory=list)
    free_from_ingredients: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(slots=True)
class UserProfile:
    raw_query: str
    skin_types: list[SkinType] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    desired_categories: list[Category] = field(default_factory=list)
    excluded_categories: list[Category] = field(default_factory=list)
    preferred_ingredients: list[str] = field(default_factory=list)
    avoided_ingredients: list[str] = field(default_factory=list)
    finish_preferences: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    budget_min: int | None = None
    budget_max: int | None = None


@dataclass(slots=True)
class Recommendation:
    product: Product
    score: float
    reasons: list[str]
    cautions: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    evidence: list["KnowledgeChunk"] = field(default_factory=list)
    purchase_links: list["PurchaseLink"] = field(default_factory=list)
    live_insights: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KnowledgeChunk:
    id: str
    title: str
    category: str
    content: str
    tags: list[str] = field(default_factory=list)
    product_ids: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    skin_types: list[str] = field(default_factory=list)
    ingredients: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(slots=True)
class AgentResponse:
    profile: UserProfile
    recommendations: list[Recommendation]
    clarifying_questions: list[str]
    summary: str
    retrieved_knowledge: list[KnowledgeChunk] = field(default_factory=list)
    llm_enabled: bool = False
    live_tools_enabled: bool = False
    tool_events: list["ToolEvent"] = field(default_factory=list)
    session_summary: str = ""
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    long_term_memories: list[dict[str, str]] = field(default_factory=list)
    react_steps: list["ReActStep"] = field(default_factory=list)


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    domain: str = ""


@dataclass(slots=True)
class ExtractedProductInfo:
    name: str
    brand: str
    price_text: str
    summary: str
    source_url: str


@dataclass(slots=True)
class PurchaseLink:
    title: str
    url: str
    platform: str
    price_text: str = ""
    seller_type: str = ""


@dataclass(slots=True)
class ToolEvent:
    tool_name: str
    status: str
    input_summary: str
    output_summary: str


@dataclass(slots=True)
class ReActStep:
    step_index: int
    thought: str
    action: str
    observation: str
