from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class LLMConfig:
    provider: str
    api_key: str
    model: str
    base_url: str
    app_name: str = "Cosmetics-Agent"
    site_url: str = "http://localhost"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        provider = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()

        if provider in {"ark", "doubao"}:
            api_key = os.getenv("ARK_API_KEY", "").strip()
            if not api_key:
                return None
            base_url = os.getenv(
                "ARK_BASE_URL",
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            ).strip()
            return cls(
                provider="ark",
                api_key=api_key,
                model=os.getenv("LLM_MODEL", "doubao-seed-1-6-250615").strip(),
                base_url=base_url,
            )

        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                return None
            return cls(
                provider="openrouter",
                api_key=api_key,
                model=os.getenv("LLM_MODEL", "openrouter/free").strip(),
                base_url="https://openrouter.ai/api/v1/chat/completions",
                app_name=os.getenv("OPENROUTER_APP_NAME", "Cosmetics-Agent").strip(),
                site_url=os.getenv("OPENROUTER_SITE_URL", "http://localhost").strip(),
            )

        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not api_key:
                return None
            return cls(
                provider="groq",
                api_key=api_key,
                model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b").strip(),
                base_url="https://api.groq.com/openai/v1/chat/completions",
            )

        if provider == "together":
            api_key = os.getenv("TOGETHER_API_KEY", "").strip()
            if not api_key:
                return None
            return cls(
                provider="together",
                api_key=api_key,
                model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b").strip(),
                base_url="https://api.together.xyz/v1/chat/completions",
            )

        return None


@dataclass(slots=True)
class ToolConfig:
    enabled: bool
    timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> "ToolConfig":
        raw_enabled = os.getenv("LIVE_TOOLS_ENABLED", "").strip().lower()
        enabled = raw_enabled in {"1", "true", "yes", "on"}
        timeout_seconds = int(os.getenv("LIVE_TOOLS_TIMEOUT", "20").strip() or "20")
        return cls(enabled=enabled, timeout_seconds=timeout_seconds)
