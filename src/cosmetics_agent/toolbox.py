from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from .models import ExtractedProductInfo, PurchaseLink, SearchResult, ToolEvent


DUCKDUCKGO_HTML_SEARCH = "https://html.duckduckgo.com/html/"
COMMON_SHOPPING_DOMAINS = (
    "sephora.com",
    "ulta.com",
    "amazon.com",
    "walmart.com",
    "target.com",
    "lookfantastic.com",
    "yesstyle.com",
    "tmall.com",
    "jd.com",
)
BANNED_RESULT_HINTS = ("reddit.com", "youtube.com", "tiktok.com", "instagram.com", "facebook.com")


class ResearchToolbox:
    """Live web tools used by the beauty advisor agent."""

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web for product or brand information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                            "preferred_domains": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_products",
                    "description": "Search product pages on shopping or official sites.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "brand": {"type": "string"},
                            "top_k": {"type": "integer", "default": 5},
                            "preferred_domains": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["product_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_product_info",
                    "description": "Extract a quick product summary from a product page URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_purchase_links",
                    "description": "Find purchase links for a product, preferably official or major shopping sites.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_name": {"type": "string"},
                            "brand": {"type": "string"},
                            "top_k": {"type": "integer", "default": 3},
                            "preferred_platforms": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["product_name"],
                    },
                },
            },
        ]

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "search_web":
            results = self.search_web(
                query=str(arguments.get("query", "")),
                top_k=int(arguments.get("top_k", 5)),
                preferred_domains=_as_str_list(arguments.get("preferred_domains")),
            )
            return {"results": [_search_result_to_dict(item) for item in results]}
        if tool_name == "search_products":
            results = self.search_products(
                product_name=str(arguments.get("product_name", "")),
                brand=str(arguments.get("brand", "")),
                top_k=int(arguments.get("top_k", 5)),
                preferred_domains=_as_str_list(arguments.get("preferred_domains")),
            )
            return {"results": [_search_result_to_dict(item) for item in results]}
        if tool_name == "extract_product_info":
            result = self.extract_product_info(url=str(arguments.get("url", "")))
            return {"result": _product_info_to_dict(result) if result else None}
        if tool_name == "get_purchase_links":
            results = self.get_purchase_links(
                product_name=str(arguments.get("product_name", "")),
                brand=str(arguments.get("brand", "")),
                top_k=int(arguments.get("top_k", 3)),
                preferred_platforms=_as_str_list(arguments.get("preferred_platforms")),
            )
            return {"results": [_purchase_link_to_dict(item) for item in results]}
        raise ValueError(f"Unknown tool: {tool_name}")

    def search_web(self, query: str, top_k: int = 5, preferred_domains: list[str] | None = None) -> list[SearchResult]:
        return self._search(query, top_k=top_k, preferred_domains=preferred_domains)

    def search_products(
        self,
        product_name: str,
        brand: str = "",
        top_k: int = 5,
        preferred_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        shopping_domains = preferred_domains or list(COMMON_SHOPPING_DOMAINS)
        query = " ".join(part for part in [brand, product_name, "buy"] if part)
        results = self._search(query, top_k=max(top_k * 2, 6), preferred_domains=shopping_domains)
        filtered = [item for item in results if item.domain and not _is_banned_domain(item.domain)]
        return filtered[:top_k]

    def extract_product_info(self, url: str) -> ExtractedProductInfo | None:
        if not url:
            return None
        html = self._fetch(url)
        if not html:
            return None
        title = _first_match(html, r"<title[^>]*>(.*?)</title>") or ""
        meta_desc = _first_match(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']') or ""
        og_title = _first_match(html, r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']') or ""
        price_text = _extract_price(html)
        cleaned_title = _clean_html_text(og_title or title)
        summary = _clean_html_text(meta_desc)[:240]
        brand = _infer_brand_from_title(cleaned_title)
        return ExtractedProductInfo(
            name=cleaned_title[:160] or url,
            brand=brand,
            price_text=price_text,
            summary=summary,
            source_url=url,
        )

    def get_purchase_links(
        self,
        product_name: str,
        brand: str = "",
        top_k: int = 3,
        preferred_platforms: list[str] | None = None,
    ) -> list[PurchaseLink]:
        domains = preferred_platforms or list(COMMON_SHOPPING_DOMAINS)
        results = self.search_products(product_name=product_name, brand=brand, top_k=max(top_k * 2, 6), preferred_domains=domains)
        links: list[PurchaseLink] = []
        for result in results:
            if _is_banned_domain(result.domain):
                continue
            links.append(
                PurchaseLink(
                    title=result.title,
                    url=result.url,
                    platform=result.domain,
                    price_text=_extract_inline_price(result.title + " " + result.snippet),
                    seller_type="official_or_marketplace",
                )
            )
            if len(links) >= top_k:
                break
        return links

    def _search(self, query: str, top_k: int = 5, preferred_domains: list[str] | None = None) -> list[SearchResult]:
        if not query.strip():
            return []
        domain_suffix = ""
        if preferred_domains:
            domain_suffix = " " + " OR ".join(f"site:{domain}" for domain in preferred_domains[:4])
        params = urllib.parse.urlencode({"q": query + domain_suffix})
        html = self._fetch(f"{DUCKDUCKGO_HTML_SEARCH}?{params}")
        if not html:
            return []
        parsed = _parse_duckduckgo_results(html)
        if preferred_domains:
            preferred_set = tuple(domain.lower() for domain in preferred_domains)
            parsed.sort(key=lambda item: (0 if item.domain.endswith(preferred_set) else 1, item.title.lower()))
        return parsed[:top_k]

    def _fetch(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                )
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""


def build_tool_event(tool_name: str, status: str, input_summary: str, output_summary: str) -> ToolEvent:
    return ToolEvent(
        tool_name=tool_name,
        status=status,
        input_summary=input_summary,
        output_summary=output_summary,
    )


def _parse_duckduckgo_results(html: str) -> list[SearchResult]:
    blocks = re.findall(r'(?s)<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>.*?(?:<a[^>]*class="result__snippet"|<div[^>]*class="result__snippet")[^>]*>(.*?)</(?:a|div)>', html)
    results: list[SearchResult] = []
    for href, raw_title, raw_snippet in blocks:
        url = _resolve_duckduckgo_url(unescape(href))
        domain = urllib.parse.urlparse(url).netloc.lower()
        results.append(
            SearchResult(
                title=_clean_html_text(raw_title),
                url=url,
                snippet=_clean_html_text(raw_snippet),
                source="duckduckgo",
                domain=domain,
            )
        )

    if results:
        return results

    lite_blocks = re.findall(r'(?s)<a rel="nofollow" href="(.*?)"[^>]*>(.*?)</a>', html)
    for href, raw_title in lite_blocks:
        url = _resolve_duckduckgo_url(unescape(href))
        if not url.startswith("http"):
            continue
        domain = urllib.parse.urlparse(url).netloc.lower()
        results.append(
            SearchResult(
                title=_clean_html_text(raw_title),
                url=url,
                source="duckduckgo",
                domain=domain,
            )
        )
    return results


def _resolve_duckduckgo_url(url: str) -> str:
    if "duckduckgo.com/l/" not in url:
        return url
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return urllib.parse.unquote(query["uddg"][0])
    return url


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _extract_price(html: str) -> str:
    for pattern in (
        r'"price"\s*:\s*"([^"]+)"',
        r'content=["\']([$€£]\s?\d[\d.,]*)["\']',
        r'([$€£]\s?\d[\d.,]*)',
    ):
        value = _first_match(html, pattern)
        if value:
            return _clean_html_text(value)
    return ""


def _extract_inline_price(text: str) -> str:
    return _first_match(text, r'([$€£]\s?\d[\d.,]*)') or ""


def _infer_brand_from_title(title: str) -> str:
    if " - " in title:
        return title.split(" - ", 1)[0][:60]
    if "|" in title:
        return title.split("|", 1)[0][:60].strip()
    return ""


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _is_banned_domain(domain: str) -> bool:
    return any(hint in domain for hint in BANNED_RESULT_HINTS)


def _search_result_to_dict(item: SearchResult) -> dict[str, str]:
    return {
        "title": item.title,
        "url": item.url,
        "snippet": item.snippet,
        "source": item.source,
        "domain": item.domain,
    }


def _product_info_to_dict(item: ExtractedProductInfo) -> dict[str, str]:
    return {
        "name": item.name,
        "brand": item.brand,
        "price_text": item.price_text,
        "summary": item.summary,
        "source_url": item.source_url,
    }


def _purchase_link_to_dict(item: PurchaseLink) -> dict[str, str]:
    return {
        "title": item.title,
        "url": item.url,
        "platform": item.platform,
        "price_text": item.price_text,
        "seller_type": item.seller_type,
    }
