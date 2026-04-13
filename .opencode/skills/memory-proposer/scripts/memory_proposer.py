#!/usr/bin/env python3
"""memory-proposer CLI — detect patterns in memory bank and propose skill updates as PRs.

Separate skill from `memory/` to make the architectural layering inversion
(memory system editing plugin source) explicit and isolable.

Usage:
    memory-proposer detect [--min-cluster 5] [--min-reward 0.6] [--json]
    memory-proposer propose <pattern_id> --target-skill <name> [--json]
    memory-proposer list [--status detected] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

# Add both memory and memory-proposer scripts to path
SCRIPT_DIR = Path(__file__).parent
MEMORY_SCRIPTS = SCRIPT_DIR.parent.parent / "memory" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(MEMORY_SCRIPTS))

EXIT_SUCCESS = 0
EXIT_NOT_FOUND = 1
EXIT_VALIDATION = 2
EXIT_STORAGE = 3
EXIT_UNAVAILABLE = 75


def _emit_json(obj) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")


def _emit_error(msg: str, code: str, *, as_json: bool) -> None:
    if as_json:
        sys.stderr.write(json.dumps({"error": msg, "code": code}) + "\n")
    else:
        sys.stderr.write(f"[memory-proposer] {msg}\n")


def cmd_detect(args) -> int:
    from db import connect

    from patterns import detect_clusters, persist_cluster, summarize_cluster

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    try:
        clusters = detect_clusters(
            conn,
            min_cluster_size=args.min_cluster,
            min_reward=args.min_reward,
        )
    except RuntimeError as exc:
        _emit_error(str(exc), "detect_failed", as_json=args.json)
        return EXIT_UNAVAILABLE

    detected: list[dict] = []
    for cluster in clusters:
        summary = summarize_cluster(conn, cluster)
        pattern_id = persist_cluster(conn, cluster, summary=summary)
        detected.append(
            {
                "pattern_id": pattern_id,
                "case_count": len(cluster.case_ids),
                "avg_reward": cluster.avg_reward,
                "summary": summary,
                "case_ids": cluster.case_ids,
            }
        )

    if args.json:
        _emit_json({"patterns": detected, "count": len(detected)})
    else:
        if not detected:
            print("No pattern clusters detected.")
        else:
            print(f"Detected {len(detected)} pattern(s):")
            for p in detected:
                print(
                    f"  pattern #{p['pattern_id']:>3} "
                    f"({p['case_count']} cases, reward={p['avg_reward']:.2f}): "
                    f"{p['summary'][:80]}"
                )
    return EXIT_SUCCESS


def cmd_propose(args) -> int:
    from db import connect

    from patterns import Cluster
    from propose import ProposeError, generate_pr

    try:
        conn = connect()
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    row = conn.execute(
        "SELECT * FROM patterns WHERE pattern_id = ?", (args.pattern_id,)
    ).fetchone()
    if row is None:
        _emit_error(f"pattern {args.pattern_id} not found", "not_found", as_json=args.json)
        return EXIT_NOT_FOUND

    case_ids = json.loads(row["case_ids"])
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()

    try:
        pr_url = generate_pr(
            conn,
            pattern_id=args.pattern_id,
            target_skill=args.target_skill,
            summary=row["summary"] or "",
            case_ids=case_ids,
            avg_reward=row["avg_reward"],
            repo_root=repo_root,
        )
    except ProposeError as exc:
        _emit_error(str(exc), "propose_failed", as_json=args.json)
        return EXIT_STORAGE
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _emit_error(str(exc), "unknown", as_json=args.json)
        return EXIT_STORAGE

    if args.json:
        _emit_json({"pattern_id": args.pattern_id, "pr_url": pr_url, "status": "proposed"})
    else:
        print(f"Proposed PR for pattern #{args.pattern_id}: {pr_url}")
    return EXIT_SUCCESS


def cmd_list(args) -> int:
    from db import connect

    try:
        conn = connect(readonly=True)
    except ImportError as exc:
        _emit_error(f"deps: {exc}", "deps_missing", as_json=args.json)
        return EXIT_UNAVAILABLE

    if args.status:
        rows = conn.execute(
            "SELECT * FROM patterns WHERE status = ? ORDER BY updated DESC",
            (args.status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patterns ORDER BY updated DESC"
        ).fetchall()

    patterns = [
        {
            "pattern_id": r["pattern_id"],
            "case_count": r["case_count"],
            "avg_reward": r["avg_reward"],
            "status": r["status"],
            "summary": r["summary"],
            "pr_url": r["pr_url"],
            "created": r["created"],
            "updated": r["updated"],
        }
        for r in rows
    ]

    if args.json:
        _emit_json(patterns)
    else:
        if not patterns:
            print("No patterns.")
        else:
            for p in patterns:
                print(
                    f"  #{p['pattern_id']:>3} [{p['status']:<10}] "
                    f"cases={p['case_count']} reward={p['avg_reward']:.2f}: "
                    f"{(p['summary'] or '')[:60]}"
                )
                if p.get("pr_url"):
                    print(f"      PR: {p['pr_url']}")
    return EXIT_SUCCESS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory-proposer",
        description="Detect patterns in memory bank and propose skill updates.",
    )
    parser.add_argument("--json", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", help="Detect pattern clusters from active cases")
    p.add_argument("--min-cluster", type=int, default=None, help="default: max(5, N/100)")
    p.add_argument("--min-reward", type=float, default=0.6)
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("propose", help="Generate a draft PR for a detected pattern")
    p.add_argument("pattern_id", type=int)
    p.add_argument("--target-skill", required=True, help="Skill name to append pattern to")
    p.add_argument("--repo-root", help="Git repo root (default: cwd)")
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("list", help="List all patterns")
    p.add_argument("--status", choices=["detected", "proposed", "merged", "ignored"])
    p.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        sys.stderr.write("\n[memory-proposer] interrupted\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
