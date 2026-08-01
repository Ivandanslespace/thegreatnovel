"""CLI for the Phase 9B1 bounded world compiler."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json
from .bundle import compile_bundle, verify_bundle
from .compiler import (
    _assert_canonical_utf8,
    _safe_issue_value,
    _safe_issue_text,
    compile_world,
    load_and_validate_documents,
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
    payload = {
        "ok": False,
        "error": {
            "code": _safe_issue_text(error.code),
            "message": _safe_issue_text(error.message),
        },
        "errors": [
            {
                "code": _safe_issue_text(issue.code),
                "path": _safe_issue_text(issue.path),
                "message": _safe_issue_text(issue.message),
                "expected": _safe_issue_value(issue.expected),
                "actual": _safe_issue_value(issue.actual),
                "allowed_values": _safe_issue_value(issue.allowed_values),
            }
            for issue in error.issues
        ],
    }
    _assert_canonical_utf8(payload)
    return payload


def _validate_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        request, draft = load_and_validate_documents(
            str(args.request), str(args.draft)
        )
    except WorldGenError as exc:
        failure = _failure(exc)
        failure["valid"] = False
        return failure, 2
    try:
        compilation = compile_world(request, draft, args.seed)
    except WorldGenError as exc:
        failure = _failure(exc)
        failure["valid"] = False
        return failure, 2
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
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "BUNDLE_INTEGRITY_MISMATCH",
                "message": "unexpected worldgen boundary failure",
            },
            "errors": [],
        }
        exit_code = 2
    try:
        output = canonical_json(payload)
        output.encode("utf-8")
    except Exception:
        output = (
            '{"error":{"code":"BUNDLE_INTEGRITY_MISMATCH",'
            '"message":"unexpected worldgen boundary failure"},'
            '"errors":[],"ok":false}'
        )
    print(output)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
