from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .knowledge_enrichment import DEFAULT_SNAPSHOTS_DIR, ensure_knowledge_dirs, normalize_title
from .models import KnowledgeChunk, StagedKnowledgeCandidate
from .rag import load_knowledge_base
from .vector_store import LocalVectorStore


KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.jsonl"


def approve_candidates(staging_file: str | Path, output_dir: str | Path | None = None) -> dict[str, object]:
    staging_path = Path(staging_file)
    if not staging_path.exists():
        raise FileNotFoundError(f"Staging file not found: {staging_path}")

    _, _, snapshots_dir = ensure_knowledge_dirs(output_dir)
    candidates = load_staged_candidates(staging_path)
    valid = [item for item in candidates if validate_approval_candidate(item)]
    deduped = dedupe_against_existing(valid)

    snapshot_path = snapshots_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-knowledge_base.jsonl"
    shutil.copy2(KNOWLEDGE_BASE_PATH, snapshot_path)

    with KNOWLEDGE_BASE_PATH.open("a", encoding="utf-8") as handle:
        for item in deduped:
            chunk = staged_to_chunk(item)
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    archive_dir = staging_path.parent / "approved"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_path = archive_dir / staging_path.name
    staging_path.replace(archived_path)

    rebuild_vector_index()
    clear_rag_caches()

    return {
        "approved_count": len(deduped),
        "snapshot_path": str(snapshot_path),
        "archived_file": str(archived_path),
    }


def load_staged_candidates(path: Path) -> list[StagedKnowledgeCandidate]:
    candidates: list[StagedKnowledgeCandidate] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            candidates.append(StagedKnowledgeCandidate(**raw))
    return candidates


def validate_approval_candidate(candidate: StagedKnowledgeCandidate) -> bool:
    if candidate.evidence_type not in {"general", "safety", "repair"}:
        return False
    if not candidate.product_ids or not candidate.content.strip():
        return False
    if candidate.evidence_type in {"safety", "repair"} and candidate.category not in {"safety", "repair"}:
        return False
    if candidate.evidence_type == "general" and candidate.category in {"safety", "repair"}:
        return False
    return True


def dedupe_against_existing(candidates: list[StagedKnowledgeCandidate]) -> list[StagedKnowledgeCandidate]:
    existing = load_knowledge_base()
    existing_keys = {build_existing_key(item) for item in existing}
    kept: dict[str, StagedKnowledgeCandidate] = {}
    for candidate in candidates:
        key = build_candidate_key(candidate)
        if key in existing_keys:
            candidate.quality_flags = [*candidate.quality_flags, "duplicate_candidate"]
            continue
        existing = kept.get(key)
        if existing is None or candidate.confidence_score > existing.confidence_score:
            kept[key] = candidate
    return list(kept.values())


def build_existing_key(chunk: KnowledgeChunk) -> str:
    return f"{chunk.category}:{normalize_title(chunk.title)}:{','.join(chunk.product_ids)}"


def build_candidate_key(candidate: StagedKnowledgeCandidate) -> str:
    return f"{candidate.category}:{normalize_title(candidate.title)}:{','.join(candidate.product_ids)}"


def staged_to_chunk(candidate: StagedKnowledgeCandidate) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=candidate.id,
        title=candidate.title,
        category=candidate.category,
        content=candidate.content,
        tags=list(candidate.tags),
        product_ids=list(candidate.product_ids),
        concerns=list(candidate.concerns),
        skin_types=list(candidate.skin_types),
        ingredients=list(candidate.ingredients),
        scenarios=list(candidate.scenarios),
        finish_preferences=list(candidate.finish_preferences),
        evidence_type=candidate.evidence_type,
    )


def clear_rag_caches() -> None:
    from . import rag

    rag.load_knowledge_base.cache_clear()


def rebuild_vector_index() -> None:
    store = LocalVectorStore()
    if not store.enabled():
        return
    store.reset_collection()
    store.upsert_knowledge_chunks(load_knowledge_base())
