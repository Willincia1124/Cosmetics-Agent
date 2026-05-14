from __future__ import annotations

import argparse
import sys

from .agent import BeautyAdvisorAgent
from .config import VectorStoreConfig
from .evals import DEFAULT_EVAL_DATASET, format_eval_run, run_evals
from .knowledge_enrichment import KnowledgeEnricher
from .knowledge_review import approve_candidates
from .memory import SessionMemory
from .parser import parse_user_query
from .rag import retrieve_knowledge, vector_store_enabled
from .toolbox import ResearchToolbox


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local CLI beauty advisor agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Run a single recommendation query")
    chat_parser.add_argument("--query", required=True, help="User query in Chinese")
    chat_parser.add_argument("--top-k", type=int, default=3, help="Number of recommendations")
    chat_parser.add_argument("--session-id", default="default-session", help="Session id for short-term memory")
    chat_parser.add_argument("--user-id", default="local-user", help="User id for long-term memory")
    chat_parser.add_argument("--message-window", type=int, default=6, help="Recent raw message window before compression")

    repl_parser = subparsers.add_parser("repl", help="Start an interactive shell")
    repl_parser.add_argument("--top-k", type=int, default=3, help="Number of recommendations")
    repl_parser.add_argument("--session-id", default="default-session", help="Session id for short-term memory")
    repl_parser.add_argument("--user-id", default="local-user", help="User id for long-term memory")
    repl_parser.add_argument("--message-window", type=int, default=6, help="Recent raw message window before compression")

    kb_parser = subparsers.add_parser("kb", help="Inspect retrieved knowledge chunks")
    kb_parser.add_argument("--query", required=True, help="User query in Chinese")
    kb_parser.add_argument("--top-k", type=int, default=5, help="Number of knowledge chunks")

    enrich_parser = subparsers.add_parser("enrich-kb", help="Generate staged knowledge candidates from products and public web data")
    enrich_parser.add_argument("--category", help="Only enrich one category")
    enrich_parser.add_argument("--product-id", help="Only enrich one product id")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of products")
    enrich_parser.add_argument("--dry-run", action="store_true", help="Run without writing staging/report files")
    enrich_parser.add_argument("--output-dir", help="Base output directory for staging/report/snapshot files")
    enrich_parser.add_argument("--source-mode", default="public_web", help="Source mode, default public_web")

    approve_parser = subparsers.add_parser("approve-kb", help="Approve staged knowledge candidates into formal knowledge base")
    approve_parser.add_argument("--approve-file", required=True, help="Path to staging jsonl file")
    approve_parser.add_argument("--output-dir", help="Base output directory for snapshot files")

    memory_parser = subparsers.add_parser("memory", help="Inspect persisted short-term and long-term memory")
    memory_parser.add_argument("--session-id", default="default-session", help="Session id for short-term memory")
    memory_parser.add_argument("--user-id", default="local-user", help="User id for long-term memory")
    memory_parser.add_argument("--message-window", type=int, default=6, help="Recent raw message window")

    eval_parser = subparsers.add_parser("eval", help="Run offline evaluation cases")
    eval_parser.add_argument("--dataset", default=str(DEFAULT_EVAL_DATASET), help="Path to JSONL eval dataset")
    eval_parser.add_argument("--case-id", help="Only run a single eval case")
    return parser


def run_chat(query: str, top_k: int, session_id: str, user_id: str, message_window: int) -> int:
    agent = BeautyAdvisorAgent(
        memory=SessionMemory(
            session_id=session_id,
            user_id=user_id,
            message_window=message_window,
        )
    )
    print(agent.render(query, top_k=top_k))
    return 0


def run_repl(top_k: int, session_id: str, user_id: str, message_window: int) -> int:
    agent = BeautyAdvisorAgent(
        memory=SessionMemory(
            session_id=session_id,
            user_id=user_id,
            message_window=message_window,
        )
    )
    print("Cosmetics Agent CLI 已启动，输入你的需求，输入 exit 或 quit 退出。")
    print("如果设置了 LIVE_TOOLS_ENABLED=1，agent 会尝试联网补充购买链接和网页摘要。")
    print(f"当前 session_id={session_id}，user_id={user_id}，message_window={message_window}")
    while True:
        try:
            query = input("\n你> ").strip()
        except EOFError:
            print()
            return 0

        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            return 0

        print()
        print(agent.render(query, top_k=top_k))


def run_kb(query: str, top_k: int) -> int:
    profile = parse_user_query(query)
    chunks = retrieve_knowledge(profile, top_k=top_k)
    vector_mode = "Chroma hybrid retrieval" if vector_store_enabled() else "Lexical fallback retrieval"
    print(f"检索模式：{vector_mode}")
    if not chunks:
        print("没有检索到知识库片段。")
        return 0

    for index, chunk in enumerate(chunks, start=1):
        print(f"{index}. {chunk.title} | category={chunk.category} | score={chunk.score:.1f}")
        print(f"   {chunk.content}")
    return 0


def run_memory(session_id: str, user_id: str, message_window: int) -> int:
    memory = SessionMemory(session_id=session_id, user_id=user_id, message_window=message_window)
    print("=== 短期记忆摘要 ===")
    print(memory.get_session_summary() or "暂无")
    print()
    print("=== 最近消息 ===")
    recent = memory.get_recent_messages()
    if not recent:
        print("暂无")
    else:
        for item in recent:
            print(f"- {item['role']}: {item['content']}")
    print()
    print("=== 长期记忆 ===")
    long_term = memory.get_long_term_memories(limit=10)
    if not long_term:
        print("暂无")
    else:
        for item in long_term:
            print(f"- {item['memory_type']}: {item['content']}")
    return 0


def run_enrich_kb(
    category: str | None,
    product_id: str | None,
    limit: int | None,
    dry_run: bool,
    output_dir: str | None,
    source_mode: str,
) -> int:
    agent = BeautyAdvisorAgent()
    enricher = KnowledgeEnricher(ResearchToolbox(), llm=agent.llm)
    report = enricher.run(
        category=category,
        product_id=product_id,
        limit=limit,
        dry_run=dry_run,
        output_dir=output_dir,
        source_mode=source_mode,
    )
    print("=== Knowledge Enrichment Report ===")
    print(f"run_id: {report.run_id}")
    print(f"source_mode: {report.source_mode}")
    print(f"processed_products: {report.processed_products}")
    print(f"generated_candidates: {report.generated_candidates}")
    print(f"kept_candidates: {report.kept_candidates}")
    print(f"rejected_candidates: {report.rejected_candidates}")
    print(f"deduped_candidates: {report.deduped_candidates}")
    if report.failed_products:
        print("failed_products:")
        for item in report.failed_products:
            print(f"- {item['product_id']}: {item['error']}")
    if not dry_run:
        print(f"output_file: {report.output_file}")
        print(f"report_file: {report.report_file}")
    return 0


def run_approve_kb(approve_file: str, output_dir: str | None) -> int:
    result = approve_candidates(staging_file=approve_file, output_dir=output_dir)
    print("=== Knowledge Approve Result ===")
    print(f"approved_count: {result['approved_count']}")
    print(f"snapshot_path: {result['snapshot_path']}")
    print(f"archived_file: {result['archived_file']}")
    return 0


def run_eval(dataset: str, case_id: str | None) -> int:
    try:
        result = run_evals(dataset_path=dataset, case_id=case_id)
    except ValueError as exc:
        print(f"Eval error: {exc}")
        return 1
    print(format_eval_run(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    _ = VectorStoreConfig.from_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "chat":
        return run_chat(args.query, args.top_k, args.session_id, args.user_id, args.message_window)
    if args.command == "repl":
        return run_repl(args.top_k, args.session_id, args.user_id, args.message_window)
    if args.command == "kb":
        return run_kb(args.query, args.top_k)
    if args.command == "memory":
        return run_memory(args.session_id, args.user_id, args.message_window)
    if args.command == "enrich-kb":
        return run_enrich_kb(
            args.category,
            args.product_id,
            args.limit,
            args.dry_run,
            args.output_dir,
            args.source_mode,
        )
    if args.command == "approve-kb":
        return run_approve_kb(args.approve_file, args.output_dir)
    if args.command == "eval":
        return run_eval(args.dataset, args.case_id)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
