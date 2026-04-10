#!/usr/bin/env python3
"""memory CLI — case-based reasoning memory layer for rafayels-engineering.

Usage:
    memory init                                 # Initialize DB + schema
    memory write --phase plan --query "..." [--plan ...] [--json]
    memory signal <case_id> <type> <value> [--source ...] [--json]
    memory query "<text>" --phase plan --k 3 [--json|--md]
    memory read <case_id> [--json]
    memory list [--phase ...] [--status ...] [--limit N] [--json]
    memory update <case_id> [--title ...] [--tags ...] [--json]
    memory delete <case_id> --confirm-token <token> [--json]
    memory link <case_id_a> <case_id_b> [--json]
    memory promote <case_id> [--json]
    memory prune [--reward-below 0.3] [--older-than 90] [--confirm] [--json]
    memory report [--stats|--stale] [--json]
    memory doctor [--json]
    memory export [--output FILE] [--json]
    memory import <file> [--json]
    memory seed [--from docs/solutions/] [--json]
    memory daemon-stop [--json]

Exit codes:
    0   success
    1   not found
    2   validation error
    3   storage error
   75   memory unavailable (EX_TEMPFAIL — dependencies missing). Workflows should
        tolerate this and proceed without memory injection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

# Sibling imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


EXIT_SUCCESS = 0
EXIT_NOT_FOUND = 1
EXIT_VALIDATION = 2
EXIT_STORAGE = 3
EXIT_UNAVAILABLE = 75  # EX_TEMPFAIL


def _emit_json(obj, fp=sys.stdout) -> None:
    fp.write(json.dumps(obj, default=str) + "\n")


def _emit_error(msg: str, code: str, *, as_json: bool = False) -> None:
    if as_json:
        sys.stderr.write(json.dumps({"error": msg, "code": code}) + "\n")
    else:
        sys.stderr.write(f"[memory] {msg}\n")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_init(args) -> int:
    from db import connect, init_schema

    try:
        conn = connect()
        init_schema(conn)
    except ImportError as exc:
        _emit_error(f"dependencies missing: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE
    except (RuntimeError, OSError) as exc:
        _emit_error(f"init failed: {exc}", "init_failed", as_json=args.json)
        return EXIT_STORAGE

    db_path = Path.home() / ".claude" / "plugins" / "rafayels-engineering" / "memory.db"
    if args.json:
        _emit_json({"status": "ok", "db_path": str(db_path)})
    else:
        print(f"memory initialized at {db_path}")
    return EXIT_SUCCESS


def cmd_write(args) -> int:
    from capture import write_case
    from db import connect
    from embedder import EmbedderUnavailable

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    tags = json.loads(args.tags) if args.tags else []

    try:
        case_id = write_case(
            conn,
            phase=args.phase,
            query=args.query,
            case_type=args.type,
            title=args.title,
            plan=args.plan,
            trajectory=args.trajectory,
            outcome=args.outcome,
            tags=tags,
            project=args.project,
        )
    except ValueError as exc:
        _emit_error(str(exc), "validation", as_json=args.json)
        return EXIT_VALIDATION
    except EmbedderUnavailable as exc:
        _emit_error(str(exc), "embedder_unavailable", as_json=args.json)
        return EXIT_UNAVAILABLE
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _emit_error(str(exc), "unknown", as_json=args.json)
        return EXIT_STORAGE

    if args.json:
        _emit_json({"case_id": case_id, "status": "quarantine"})
    else:
        print(f"case {case_id} written (status=quarantine)")
    return EXIT_SUCCESS


def cmd_signal(args) -> int:
    from capture import add_signal
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    try:
        add_signal(
            conn,
            case_id=args.case_id,
            signal_type=args.signal_type,
            value=args.value,
            source=args.source,
        )
    except ValueError as exc:
        _emit_error(str(exc), "validation", as_json=args.json)
        return EXIT_VALIDATION

    if args.json:
        _emit_json({"status": "ok", "case_id": args.case_id, "signal_type": args.signal_type})
    else:
        print(f"signal added: case {args.case_id} {args.signal_type}={args.value}")
    return EXIT_SUCCESS


def cmd_query(args) -> int:
    from db import connect
    from retrieve import format_for_injection, query as retrieve_query, results_to_json

    # Note: query writes to `retrievals` table for cap-penalty tracking,
    # so we need a read-write connection, not readonly.
    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    exclude = []
    if args.exclude:
        exclude = [int(x) for x in args.exclude.split(",") if x]

    try:
        results = retrieve_query(
            conn,
            text=args.text,
            phase=args.phase,
            k=args.k,
            workflow_run_id=args.run_id,
            exclude_case_ids=exclude,
        )
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _emit_error(str(exc), "query_failed", as_json=args.json)
        return EXIT_STORAGE

    if args.json or args.format == "json":
        _emit_json({"results": results_to_json(results), "count": len(results)})
    else:
        md = format_for_injection(results)
        if md:
            print(md)
    return EXIT_SUCCESS


def cmd_read(args) -> int:
    from audit import read_case
    from db import connect

    try:
        conn = connect(readonly=True)
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    case = read_case(conn, args.case_id)
    if case is None:
        _emit_error(f"case {args.case_id} not found", "not_found", as_json=args.json)
        return EXIT_NOT_FOUND

    if args.json:
        _emit_json(case.to_dict())
    else:
        print(f"Case #{case.case_id} [{case.status}] reward={case.reward:.2f}")
        if case.title:
            print(f"Title: {case.title}")
        print(f"Phase: {case.phase}")
        print(f"Query: {case.query}")
        if case.plan:
            print(f"Plan: {case.plan}")
        if case.outcome:
            print(f"Outcome: {case.outcome}")
    return EXIT_SUCCESS


def cmd_list(args) -> int:
    from audit import list_cases
    from db import connect

    try:
        conn = connect(readonly=True)
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    cases = list_cases(
        conn,
        phase=args.phase,
        status=args.status,
        project=args.project,
        tag=args.tag,
        limit=args.limit,
    )

    if args.json:
        _emit_json([c.to_dict() for c in cases])
    else:
        for c in cases:
            print(
                f"  #{c.case_id:>5} [{c.status:>10}] reward={c.reward:.2f} "
                f"{c.phase:<10} {c.title or c.query[:60]}"
            )
        print(f"total: {len(cases)}")
    return EXIT_SUCCESS


def cmd_update(args) -> int:
    from capture import update_case
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    tags = json.loads(args.tags) if args.tags else None
    update_case(
        conn,
        args.case_id,
        title=args.title,
        tags=tags,
        outcome=args.outcome,
    )

    if args.json:
        _emit_json({"status": "ok", "case_id": args.case_id})
    else:
        print(f"case {args.case_id} updated")
    return EXIT_SUCCESS


def cmd_delete(args) -> int:
    from capture import delete_case
    from db import connect

    # Two-step confirmation: agent reads the case, gets a token, then deletes
    import hashlib

    expected_token = hashlib.sha256(f"delete:{args.case_id}".encode()).hexdigest()[:8]
    if args.confirm_token != expected_token:
        _emit_error(
            f"missing --confirm-token. Expected: {expected_token}",
            "confirmation_required",
            as_json=args.json,
        )
        return EXIT_VALIDATION

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    delete_case(conn, args.case_id)
    if args.json:
        _emit_json({"status": "deleted", "case_id": args.case_id})
    else:
        print(f"case {args.case_id} deleted")
    return EXIT_SUCCESS


def cmd_link(args) -> int:
    from capture import link_cases
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    try:
        link_cases(conn, args.case_id_a, args.case_id_b, link_type=args.type)
    except ValueError as exc:
        _emit_error(str(exc), "validation", as_json=args.json)
        return EXIT_VALIDATION

    if args.json:
        _emit_json(
            {"status": "linked", "case_id_a": args.case_id_a, "case_id_b": args.case_id_b}
        )
    else:
        print(f"linked {args.case_id_a} <-> {args.case_id_b}")
    return EXIT_SUCCESS


def cmd_promote(args) -> int:
    from capture import promote
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    promote(conn, args.case_id)
    if args.json:
        _emit_json({"status": "promoted", "case_id": args.case_id})
    else:
        print(f"case {args.case_id} promoted")
    return EXIT_SUCCESS


def cmd_prune(args) -> int:
    from capture import prune
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    dry_run = not args.confirm
    archived = prune(
        conn,
        reward_below=args.reward_below,
        older_than_days=args.older_than,
        dry_run=dry_run,
    )

    if args.json:
        _emit_json(
            {
                "status": "dry_run" if dry_run else "archived",
                "count": len(archived),
                "case_ids": archived,
            }
        )
    else:
        if dry_run:
            print(f"[dry-run] would archive {len(archived)} cases: {archived}")
            print("Add --confirm to actually archive.")
        else:
            print(f"archived {len(archived)} cases")
    return EXIT_SUCCESS


def cmd_report(args) -> int:
    from audit import report_stale, report_stats
    from db import connect

    try:
        conn = connect(readonly=True)
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    if args.stale:
        data = report_stale(conn, older_than_days=args.older_than)
    else:
        data = report_stats(conn)

    if args.json:
        _emit_json(data)
    else:
        if args.stale:
            print(f"Stale cases (older than {args.older_than} days):")
            for item in data:
                print(
                    f"  #{item['case_id']} [{item['status']}] "
                    f"reward={item['reward']:.2f} age={item['age_days']}d "
                    f"{item['title'] or ''}"
                )
        else:
            print("Memory Layer Statistics")
            print(f"  total cases:   {data['total_cases']}")
            print(f"  total signals: {data['total_signals']}")
            print(f"  by status:     {data['cases_by_status']}")
            print(f"  by phase:      {data['cases_by_phase']}")
            print(f"  reward dist:   {data['reward_distribution']}")
            print(f"  by signal:     {data['signals_by_type']}")
    return EXIT_SUCCESS


def cmd_doctor(args) -> int:
    from audit import doctor
    from db import connect, user_scope_db_path

    conn = None
    if user_scope_db_path().exists():
        try:
            conn = connect(readonly=True)
        except ImportError:
            pass

    data = doctor(conn)

    if args.json:
        _emit_json(data)
    else:
        print(f"memory status: {data['status']}")
        for check in data["checks"]:
            status_marker = {"ok": "✓", "warm": "✓", "running": "✓"}.get(
                check["status"], "✗"
            )
            detail = check.get("detail", "")
            print(f"  {status_marker} {check['name']:<30} [{check['status']}] {detail}")
            if "fix" in check:
                print(f"    fix: {check['fix']}")

    return EXIT_SUCCESS if data["status"] == "healthy" else EXIT_UNAVAILABLE


def cmd_export(args) -> int:
    from audit import export_jsonl
    from db import connect

    try:
        conn = connect(readonly=True)
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    output = Path(args.output) if args.output else None
    count = export_jsonl(conn, output)
    if args.json:
        _emit_json({"status": "ok", "records_exported": count})
    else:
        sys.stderr.write(f"[memory] exported {count} records\n")
    return EXIT_SUCCESS


def cmd_import(args) -> int:
    from audit import import_jsonl
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    result = import_jsonl(conn, Path(args.input))
    if args.json:
        _emit_json({"status": "ok", **result})
    else:
        print(
            f"imported {result['cases_imported']} cases, "
            f"{result['signals_imported']} signals"
        )
    return EXIT_SUCCESS


def cmd_seed(args) -> int:
    from audit import seed_from_solutions
    from db import connect

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    src = Path(args.source) if args.source else None
    count = seed_from_solutions(conn, src)
    if args.json:
        _emit_json({"status": "ok", "cases_seeded": count})
    else:
        print(f"seeded {count} cases from {src or 'docs/solutions/'}")
    return EXIT_SUCCESS


def cmd_daemon_stop(args) -> int:
    from embedder import stop_daemon

    ok = stop_daemon()
    if args.json:
        _emit_json({"status": "stopped" if ok else "not_running"})
    else:
        print("daemon stopped" if ok else "daemon was not running")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory",
        description="Case-based memory layer for rafayels-engineering plugin.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p = subparsers.add_parser("init", help="Initialize DB + schema")
    p.set_defaults(func=cmd_init)

    # write
    p = subparsers.add_parser("write", help="Write a new case")
    p.add_argument("--phase", required=True, choices=["brainstorm", "plan", "work", "review", "compound", "other"])
    p.add_argument("--query", required=True, help="What the user was trying to do")
    p.add_argument("--type", choices=["bug", "pattern", "decision", "solution"])
    p.add_argument("--title")
    p.add_argument("--plan")
    p.add_argument("--trajectory")
    p.add_argument("--outcome")
    p.add_argument("--tags", help="JSON array of tags")
    p.add_argument("--project")
    p.set_defaults(func=cmd_write)

    # signal
    p = subparsers.add_parser("signal", help="Append a signal to an existing case")
    p.add_argument("case_id", type=int)
    p.add_argument("signal_type", choices=["merge", "ci", "approval", "review", "regression"])
    p.add_argument("value", type=float, help="Signal value in [-1.0, 1.0]")
    p.add_argument("--source")
    p.set_defaults(func=cmd_signal)

    # query
    p = subparsers.add_parser("query", help="Retrieve top-K relevant cases")
    p.add_argument("text", help="Query text")
    p.add_argument("--phase", required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--run-id", help="workflow_run_id for cross-phase dedup")
    p.add_argument("--exclude", help="Comma-separated case_ids to exclude")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.set_defaults(func=cmd_query)

    # read
    p = subparsers.add_parser("read", help="Read a single case by ID")
    p.add_argument("case_id", type=int)
    p.set_defaults(func=cmd_read)

    # list
    p = subparsers.add_parser("list", help="List cases with optional filters")
    p.add_argument("--phase")
    p.add_argument("--status")
    p.add_argument("--project")
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_list)

    # update
    p = subparsers.add_parser("update", help="Update mutable fields on a case")
    p.add_argument("case_id", type=int)
    p.add_argument("--title")
    p.add_argument("--tags", help="JSON array")
    p.add_argument("--outcome")
    p.set_defaults(func=cmd_update)

    # delete
    p = subparsers.add_parser("delete", help="Hard-delete a case (requires --confirm-token)")
    p.add_argument("case_id", type=int)
    p.add_argument("--confirm-token", required=True, help="Expected: sha256('delete:<id>')[:8]")
    p.set_defaults(func=cmd_delete)

    # link
    p = subparsers.add_parser("link", help="Mark two cases as related")
    p.add_argument("case_id_a", type=int)
    p.add_argument("case_id_b", type=int)
    p.add_argument("--type", default="related")
    p.set_defaults(func=cmd_link)

    # promote
    p = subparsers.add_parser("promote", help="Pin a case as promoted (never auto-archived)")
    p.add_argument("case_id", type=int)
    p.set_defaults(func=cmd_promote)

    # prune
    p = subparsers.add_parser("prune", help="Archive low-reward cases (dry-run by default)")
    p.add_argument("--reward-below", type=float, default=0.3)
    p.add_argument("--older-than", type=int, default=90, help="age in days")
    p.add_argument("--confirm", action="store_true", help="actually archive (default is dry-run)")
    p.set_defaults(func=cmd_prune)

    # report
    p = subparsers.add_parser("report", help="Aggregate statistics or stale-case report")
    p.add_argument("--stats", action="store_true", default=True)
    p.add_argument("--stale", action="store_true")
    p.add_argument("--older-than", type=int, default=90)
    p.set_defaults(func=cmd_report)

    # doctor
    p = subparsers.add_parser("doctor", help="Self-diagnose memory layer readiness")
    p.set_defaults(func=cmd_doctor)

    # export / import
    p = subparsers.add_parser("export", help="Export all cases + signals as JSONL")
    p.add_argument("--output", help="Output file (default: stdout)")
    p.set_defaults(func=cmd_export)

    p = subparsers.add_parser("import", help="Import cases + signals from JSONL")
    p.add_argument("input", help="Input JSONL file")
    p.set_defaults(func=cmd_import)

    # seed
    p = subparsers.add_parser("seed", help="Bootstrap from docs/solutions/")
    p.add_argument("--source", help="Path to solutions directory")
    p.set_defaults(func=cmd_seed)

    # daemon-stop
    p = subparsers.add_parser("daemon-stop", help="Request the embedder daemon to stop")
    p.set_defaults(func=cmd_daemon_stop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        sys.stderr.write("\n[memory] interrupted\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
