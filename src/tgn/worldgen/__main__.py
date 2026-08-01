"""CLI for the Phase 9B1 bounded world compiler."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json
from .bundle import compile_bundle, verify_bundle
from .compiler import (
    compile_world,
    load_document,
    validate_documents,
)
from .models import WorldGenError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tgn.worldgen",
        description="Compile and verify a bounded Phase 9B1 World Draft.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "compile"):
        command = subparsers.add_parser(name)
        command.add_argument("--request", required=True, type=Path)
        command.add_argument("--draft", required=True, type=Path)
        command.add_argument("--seed", required=True)
        if name == "compile":
            command.add_argument("--output-dir", required=True, type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-dir", required=True, type=Path)
    return parser


def _failure(error: WorldGenError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": error.error_dict(),
        "errors": error.issues_dict(),
    }


def _load_validation_inputs(
    request_path: Path, draft_path: Path
) -> tuple[Any, Any, list[Any]]:
    values: list[Any] = []
    issues: list[Any] = []
    for path in (request_path, draft_path):
        try:
            values.append(load_document(str(path)))
        except WorldGenError as exc:
            values.append(None)
            issues.extend(exc.issues)
    return values[0], values[1], issues


def _validate_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    request_value, draft_value, parse_issues = _load_validation_inputs(
        args.request, args.draft
    )
    if parse_issues:
        return {
            "ok": False,
            "valid": False,
            "errors": [issue.to_dict() for issue in parse_issues],
            "error": {"code": parse_issues[0].code, "message": "input validation failed"},
        }, 2
    request, draft, issues = validate_documents(request_value, draft_value)
    if issues or request is None or draft is None:
        return {
            "ok": False,
            "valid": False,
            "errors": [issue.to_dict() for issue in issues],
            "error": {"code": "INVALID_SCHEMA", "message": "input validation failed"},
        }, 2
    try:
        compilation = compile_world(request, draft, args.seed)
    except WorldGenError as exc:
        return {
            "ok": False,
            "valid": False,
            "error": exc.error_dict(),
            "errors": exc.issues_dict(),
        }, 2
    return {
        "ok": True,
        "valid": True,
        "errors": [],
        "preview": {
            "compiler_id": compilation.report["compiler_id"],
            "world_id": compilation.draft.world_id,
            "worldpack_hash": compilation.worldpack_hash,
            "initial_state_hash": compilation.initial_state_hash,
        },
    }, 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            payload, exit_code = _validate_command(args)
        elif args.command == "compile":
            payload = compile_bundle(
                args.request,
                args.draft,
                args.seed,
                args.output_dir,
            )
            exit_code = 0
        else:
            verification = verify_bundle(args.bundle_dir)
            payload = {"ok": True, "valid": True, "verification": verification}
            exit_code = 0
    except WorldGenError as exc:
        payload = _failure(exc)
        exit_code = 2
    except Exception as exc:
        payload = {
            "ok": False,
            "error": {"code": "BUNDLE_INTEGRITY_MISMATCH", "message": str(exc)},
            "errors": [],
        }
        exit_code = 2
    print(canonical_json(payload))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
