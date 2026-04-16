from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import BeautyAdvisorAgent
from .formatter import format_agent_response
from .guardrails import build_global_cautions
from .memory import SessionMemory
from .models import AgentResponse


WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, description="User query in Chinese")
    session_id: str = Field(default="default-session")
    user_id: str = Field(default="local-user")
    top_k: int = Field(default=3, ge=1, le=5)
    message_window: int = Field(default=6, ge=2, le=20)


class SessionRequest(BaseModel):
    user_id: str = Field(default="local-user")
    message_window: int = Field(default=6, ge=2, le=20)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cosmetics Agent",
        version="0.1.0",
        description="Beauty advisor agent API with a lightweight chat frontend.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat")
    def chat(payload: ChatRequest) -> dict[str, Any]:
        memory = SessionMemory(
            session_id=payload.session_id,
            user_id=payload.user_id,
            message_window=payload.message_window,
        )
        agent = BeautyAdvisorAgent(memory=memory)
        response = agent.run(payload.query, top_k=payload.top_k)
        cautions = build_global_cautions(response.profile, response.recommendations)
        return serialize_agent_response(response, cautions)

    @app.get("/api/session/{session_id}")
    def get_session(session_id: str, user_id: str = "local-user", message_window: int = 6) -> dict[str, Any]:
        memory = SessionMemory(session_id=session_id, user_id=user_id, message_window=message_window)
        return {
            "session_id": session_id,
            "user_id": user_id,
            "session_summary": memory.get_session_summary(),
            "recent_messages": memory.get_recent_messages(limit=message_window),
            "long_term_memories": memory.get_long_term_memories(limit=10),
        }

    @app.post("/api/session/{session_id}/reset")
    def reset_session(session_id: str, payload: SessionRequest) -> dict[str, Any]:
        memory = SessionMemory(
            session_id=session_id,
            user_id=payload.user_id,
            message_window=payload.message_window,
        )
        memory.clear_session()
        return {"status": "ok", "session_id": session_id}

    @app.get("/")
    def index() -> FileResponse:
        index_path = WEB_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Frontend not found.")
        return FileResponse(index_path)

    return app


def serialize_agent_response(response: AgentResponse, global_cautions: list[str]) -> dict[str, Any]:
    return {
        "mode": {
            "llm_enabled": response.llm_enabled,
            "live_tools_enabled": response.live_tools_enabled,
        },
        "profile": asdict(response.profile),
        "summary": response.summary,
        "clarifying_questions": list(response.clarifying_questions),
        "retrieved_knowledge": [asdict(item) for item in response.retrieved_knowledge],
        "plan_steps": list(response.plan_steps),
        "self_check_notes": list(response.self_check_notes),
        "tool_events": [asdict(item) for item in response.tool_events],
        "react_steps": [asdict(item) for item in response.react_steps],
        "multi_agent_steps": [asdict(item) for item in response.multi_agent_steps],
        "session_summary": response.session_summary,
        "recent_messages": list(response.recent_messages),
        "long_term_memories": list(response.long_term_memories),
        "global_cautions": global_cautions,
        "recommendations": [_serialize_recommendation(item) for item in response.recommendations],
        "rendered_text": format_agent_response(response, global_cautions),
    }


def _serialize_recommendation(item) -> dict[str, Any]:
    return {
        "product": asdict(item.product),
        "score": item.score,
        "reasons": list(item.reasons),
        "cautions": list(item.cautions),
        "alternatives": list(item.alternatives),
        "evidence": [asdict(chunk) for chunk in item.evidence],
        "purchase_links": [asdict(link) for link in item.purchase_links],
        "live_insights": list(item.live_insights),
    }


app = create_app()
