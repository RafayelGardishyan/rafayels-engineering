from __future__ import annotations

import argparse
import difflib
import json
import sys

import resolver
import wizard
from resolver import ConfigMalformedError, ConfigMissingError, ProjectConfigError


def _print_error(error: ProjectConfigError) -> None:
    print(f"error: {error}", file=sys.stderr)
    if error.fix:
        print(f"  fix: {error.fix}", file=sys.stderr)


def _emit_json(payload: dict[str, object]) -> None:
    json.dump(payload, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


def _require_known_key(dotted_key: str) -> None:
    if dotted_key in resolver.SCHEMA:
        return
    suggestion = difflib.get_close_matches(dotted_key, resolver.SCHEMA.keys(), n=1, cutoff=0.0)
    message = f"Unknown config key '{dotted_key}'."
    if suggestion:
        message = f"{message} Did you mean '{suggestion[0]}'?"
    raise ConfigMissingError(
        message,
        reason="unknown",
        fix="Run `project-config keys` to list valid config keys.",
    )


def _sorted_config(config: resolver.ProjectConfig) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for key in sorted(resolver.SCHEMA):
        rows.append((key, resolver.lookup(config, key), config.source_map[key]))
    return rows


def _parse_assignment(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    key, value = raw.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    if key not in resolver.SCHEMA:
        suggestion = difflib.get_close_matches(key, resolver.SCHEMA.keys(), n=1)
        message = f"unknown config key '{key}'"
        if suggestion:
            message = f"{message}; did you mean '{suggestion[0]}'?"
        raise argparse.ArgumentTypeError(message)
    return key, value


def _cmd_get(args: argparse.Namespace) -> int:
    _require_known_key(args.key)
    config = resolver.load_config()
    value = resolver.lookup(config, args.key)
    if args.json:
        _emit_json({"key": args.key, "value": value, "source": config.source_map[args.key]})
    else:
        print(value)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    config = resolver.load_config()
    rows = _sorted_config(config)
    if args.json:
        _emit_json(
            {
                "config": {key: value for key, value, _ in rows},
                "source_map": {key: source for key, _, source in rows},
                "project_root": str(config.project_root),
            }
        )
    else:
        for key, value, source in rows:
            print(f"{key}\t{value}\t({source})")
    return 0


def _cmd_check(_: argparse.Namespace) -> int:
    resolver.load_config()
    return 0


def _cmd_where(args: argparse.Namespace) -> int:
    _require_known_key(args.key)
    config = resolver.load_config()
    print(config.source_map[args.key])
    return 0


def _cmd_keys(_: argparse.Namespace) -> int:
    for key in sorted(resolver.SCHEMA):
        print(key)
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    if args.non_interactive:
        values = dict(args.set_values)
        try:
            result = wizard.run_non_interactive(values, force=args.force)
        except FileExistsError as exc:
            raise ProjectConfigError(
                str(exc),
                fix="Re-run with `project-config init --non-interactive --force` to overwrite.",
            ) from exc
        print(result["path_written"])
        return 0
    wizard.run_interactive()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("key")
    get_parser.add_argument("--json", action="store_true")
    get_parser.set_defaults(func=_cmd_get)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=_cmd_list)

    check_parser = subparsers.add_parser("check")
    check_parser.set_defaults(func=_cmd_check)

    where_parser = subparsers.add_parser("where")
    where_parser.add_argument("key")
    where_parser.set_defaults(func=_cmd_where)

    keys_parser = subparsers.add_parser("keys")
    keys_parser.set_defaults(func=_cmd_keys)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--non-interactive", action="store_true")
    init_parser.add_argument("--set", dest="set_values", action="append", type=_parse_assignment, default=[])
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=_cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigMissingError as error:
        _print_error(error)
        return 2 if error.reason == "missing" else 1
    except ConfigMalformedError as error:
        _print_error(error)
        return 3
    except ProjectConfigError as error:
        _print_error(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
