from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

from .models import AgentResponse, UserProfile


DEFAULT_MEMORY_DIR = Path(__file__).resolve().parents[2] / ".cosmetics_agent"
DEFAULT_DB_PATH = DEFAULT_MEMORY_DIR / "memory.db"


class MemoryStore:
    """SQLite-backed memory store for short-term and long-term memory."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def load_session(self, session_id: str) -> tuple[UserProfile | None, str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json, summary FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None, ""
        profile = _profile_from_json(row["profile_json"]) if row["profile_json"] else None
        return profile, row["summary"] or ""

    def save_session(self, session_id: str, profile: UserProfile, summary: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_state (session_id, profile_json, summary, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session_id, _profile_to_json(profile), summary),
            )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (session_id, role, content),
            )

    def fetch_messages(self, session_id: str) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content
                FROM session_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [{"id": str(row["id"]), "role": row["role"], "content": row["content"]} for row in rows]

    def delete_messages(self, message_ids: list[int]) -> None:
        if not message_ids:
            return
        placeholders = ",".join("?" for _ in message_ids)
        with self._connect() as conn:
            conn.execute(f"DELETE FROM session_messages WHERE id IN ({placeholders})", message_ids)

    def load_long_term_profile(self, user_id: str) -> UserProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None or not row["profile_json"]:
            return None
        return _profile_from_json(row["profile_json"])

    def save_long_term_profile(self, user_id: str, profile: UserProfile) -> None:
        stable = _extract_stable_profile(profile)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (user_id, profile_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, _profile_to_json(stable)),
            )

    def add_long_term_memory(self, user_id: str, memory_type: str, content: str, tags: list[str]) -> None:
        if not content.strip():
            return
        with self._connect() as conn:
            exists = conn.execute(
                """
                SELECT 1
                FROM user_memories
                WHERE user_id = ? AND memory_type = ? AND content = ?
                LIMIT 1
                """,
                (user_id, memory_type, content),
            ).fetchone()
            if exists is not None:
                return
            conn.execute(
                """
                INSERT INTO user_memories (user_id, memory_type, content, tags_json, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (user_id, memory_type, content, json.dumps(tags, ensure_ascii=False)),
            )

    def fetch_long_term_memories(self, user_id: str, limit: int = 5) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT memory_type, content, tags_json, MAX(created_at) AS created_at
                FROM user_memories
                WHERE user_id = ?
                GROUP BY memory_type, content, tags_json
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [
            {
                "memory_type": row["memory_type"],
                "content": row["content"],
                "tags": row["tags_json"] or "[]",
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def clear_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))

    def clear_user_memory(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_memories WHERE user_id = ?", (user_id,))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    profile_json TEXT,
                    summary TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class SessionMemory:
    """Persistent short-term and long-term memory manager."""

    def __init__(
        self,
        session_id: str = "default-session",
        user_id: str = "local-user",
        message_window: int = 6,
        db_path: str | Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.message_window = max(2, message_window)
        self.store = MemoryStore(db_path=db_path)
        self._session_profile, self._session_summary = self.store.load_session(self.session_id)
        self._long_term_profile = self.store.load_long_term_profile(self.user_id)

    def merge(self, current: UserProfile) -> UserProfile:
        merged = current
        if self._long_term_profile is not None:
            merged = _merge_profiles(self._long_term_profile, merged)
        if self._session_profile is not None:
            merged = _merge_profiles(self._session_profile, merged)
        self._session_profile = merged
        return merged

    def remember_turn(self, user_query: str, response: AgentResponse) -> None:
        self.store.add_message(self.session_id, "user", user_query)
        assistant_note = _build_assistant_note(response)
        self.store.add_message(self.session_id, "assistant", assistant_note)

        messages = self.store.fetch_messages(self.session_id)
        if len(messages) > self.message_window:
            overflow = messages[:-self.message_window]
            compressed = _compress_messages(overflow)
            self._session_summary = _merge_summary(self._session_summary, compressed)
            overflow_ids = [int(item["id"]) for item in overflow]
            self.store.delete_messages(overflow_ids)

        self._session_profile = response.profile
        self.store.save_session(self.session_id, response.profile, self._session_summary)
        self._persist_long_term_memory(response.profile)

    def get_recent_messages(self, limit: int | None = None) -> list[dict[str, str]]:
        messages = self.store.fetch_messages(self.session_id)
        return messages[-(limit or self.message_window) :]

    def get_session_summary(self) -> str:
        return self._session_summary

    def get_long_term_memories(self, limit: int = 5) -> list[dict[str, str]]:
        return self.store.fetch_long_term_memories(self.user_id, limit=limit)

    def _persist_long_term_memory(self, profile: UserProfile) -> None:
        self._long_term_profile = _merge_profiles(self._long_term_profile, profile) if self._long_term_profile else _extract_stable_profile(profile)
        self.store.save_long_term_profile(self.user_id, self._long_term_profile)

        facts = _build_long_term_facts(profile)
        for fact in facts:
            self.store.add_long_term_memory(
                self.user_id,
                memory_type=fact["memory_type"],
                content=fact["content"],
                tags=fact["tags"],
            )

    def clear_session(self) -> None:
        self.store.clear_session(self.session_id)
        self._session_profile = None
        self._session_summary = ""

    def clear_user_memory(self) -> None:
        self.store.clear_user_memory(self.user_id)
        self._long_term_profile = None


def _profile_to_json(profile: UserProfile) -> str:
    return json.dumps(asdict(profile), ensure_ascii=False)


def _profile_from_json(payload: str) -> UserProfile:
    data = json.loads(payload)
    return UserProfile(**data)


def _merge_profiles(base: UserProfile, current: UserProfile) -> UserProfile:
    return replace(
        current,
        skin_types=current.skin_types or base.skin_types,
        concerns=_merge_unique(base.concerns, current.concerns),
        desired_categories=current.desired_categories or base.desired_categories,
        excluded_categories=_merge_unique(base.excluded_categories, current.excluded_categories),
        preferred_ingredients=_merge_unique(base.preferred_ingredients, current.preferred_ingredients),
        avoided_ingredients=_merge_unique(base.avoided_ingredients, current.avoided_ingredients),
        finish_preferences=current.finish_preferences or base.finish_preferences,
        scenarios=_merge_unique(base.scenarios, current.scenarios),
        budget_min=current.budget_min if current.budget_min is not None else base.budget_min,
        budget_max=current.budget_max if current.budget_max is not None else base.budget_max,
    )


def _extract_stable_profile(profile: UserProfile) -> UserProfile:
    return UserProfile(
        raw_query="",
        skin_types=list(profile.skin_types),
        concerns=list(profile.concerns),
        desired_categories=list(profile.desired_categories),
        excluded_categories=list(profile.excluded_categories),
        preferred_ingredients=list(profile.preferred_ingredients),
        avoided_ingredients=list(profile.avoided_ingredients),
        finish_preferences=list(profile.finish_preferences),
        scenarios=list(profile.scenarios),
        budget_min=profile.budget_min,
        budget_max=profile.budget_max,
    )


def _build_assistant_note(response: AgentResponse) -> str:
    if not response.recommendations:
        return "未找到足够匹配的推荐结果。"
    top = response.recommendations[0]
    return f"推荐了 {top.product.name}，原因包括：{'；'.join(top.reasons[:2])}。"


def _compress_messages(messages: list[dict[str, str]]) -> str:
    if not messages:
        return ""
    user_notes: list[str] = []
    assistant_notes: list[str] = []
    for item in messages:
        if item["role"] == "user":
            user_notes.append(item["content"])
        elif item["role"] == "assistant":
            assistant_notes.append(item["content"])

    summary_parts: list[str] = []
    if user_notes:
        summary_parts.append("用户之前提到：" + "；".join(note[:60] for note in user_notes[-3:]))
    if assistant_notes:
        summary_parts.append("系统此前回应：" + "；".join(note[:60] for note in assistant_notes[-2:]))
    return " ".join(summary_parts)


def _merge_summary(existing: str, new_text: str) -> str:
    parts = [item for item in [existing.strip(), new_text.strip()] if item]
    return " ".join(parts)[-800:]


def _build_long_term_facts(profile: UserProfile) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    if profile.skin_types:
        facts.append(
            {
                "memory_type": "stable_profile",
                "content": f"用户肤质特征倾向于 {'/'.join(profile.skin_types)}。",
                "tags": ["skin_type", *profile.skin_types],
            }
        )
    if profile.avoided_ingredients:
        facts.append(
            {
                "memory_type": "preference",
                "content": f"用户倾向避开 {'/'.join(profile.avoided_ingredients)}。",
                "tags": ["avoid_ingredient", *profile.avoided_ingredients],
            }
        )
    if profile.finish_preferences:
        facts.append(
            {
                "memory_type": "preference",
                "content": f"用户偏好 {'/'.join(profile.finish_preferences)} 风格的肤感或妆效。",
                "tags": ["finish", *profile.finish_preferences],
            }
        )
    return facts


def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    result = list(existing)
    for item in incoming:
        if item not in result:
            result.append(item)
    return result
