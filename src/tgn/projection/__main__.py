"""CLI for the bounded Phase 9B2A projection sidecar."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json
from ..worldgen.models import WorldGenError
from .bundle import compile_projection_bundle, preview_projection, verify_projection_bundle
from .common import assert_canonical_utf8, safe_issue_text, safe_issue_value
from .compiler import compile_projection


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tgn.projection",
        description="Compile and verify a bounded Phase 9B2A player projection.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--source-bundle-dir", "--bundle-dir", dest="source_bundle_dir", required=True, type=Path)
    validate.add_argument("--draft", "--projection-draft", dest="draft", required=True, type=Path)

    compile_command = subparsers.add_parser("compile")
    compile_command.add_argument("--source-bundle-dir", "--bundle-dir", dest="source_bundle_dir", required=True, type=Path)
    compile_command.add_argument("--draft", "--projection-draft", dest="draft", required=True, type=Path)
    compile_command.add_argument("--output-dir", "--projection-dir", dest="output_dir", required=True, type=Path)

    for name in ("verify", "preview"):
        command = subparsers.add_parser(name)
        command.add_argument("--source-bundle-dir", "--bundle-dir", dest="source_bundle_dir", required=True, type=Path)
        command.add_argument("--projection-dir", "--output-dir", dest="projection_dir", required=True, type=Path)
    return parser


def _failure(error: WorldGenError) -> dict[str, Any]:
    payload = {
        "ok": False,
        "error": {
            "code": safe_issue_text(error.code),
            "message": safe_issue_text(error.message),
        },
        "errors": [
            {
                "code": safe_issue_text(item.code),
                "path": safe_issue_text(item.path),
                "message": safe_issue_text(item.message),
                "expected": safe_issue_value(item.expected),
                "actual": safe_issue_value(item.actual),
                "allowed_values": safe_issue_value(item.allowed_values),
            }
            for item in error.issues
        ],
    }
    assert_canonical_utf8(payload)
    return payload


def _validate_command(args: argparse.Namespace) -> dict[str, Any]:
    result = compile_projection(args.source_bundle_dir, args.draft)
    return {
        "ok": True,
        "valid": True,
        "errors": [],
        "preview": {
            "projection_compiler_id": result.projection.projection_compiler_id,
            "source_worldpack_hash": result.projection.source_worldpack_hash,
            "source_initial_state_hash": result.projection.source_initial_state_hash,
            "projection_hash": result.projection_hash,
            "initial_request_fingerprint": result.initial_request.request_fingerprint,
            "initial_presentation_hash": result.presentation_hash,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            payload = _validate_command(args)
        elif args.command == "compile":
            payload = compile_projection_bundle(args.source_bundle_dir, args.draft, args.output_dir)
        elif args.command == "verify":
            payload = {"ok": True, "valid": True, "verification": verify_projection_bundle(args.source_bundle_dir, args.projection_dir)}
        else:
            payload = {"ok": True, "valid": True, **preview_projection(args.source_bundle_dir, args.projection_dir)}
        exit_code = 0
    except WorldGenError as exc:
        payload = _failure(exc)
        exit_code = 2
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "PROJECTION_INTEGRITY_MISMATCH",
                "message": "unexpected projection boundary failure",
            },
            "errors": [],
        }
        exit_code = 2
    try:
        output = canonical_json(payload)
        output.encode("utf-8")
    except Exception:
        output = (
            '{"error":{"code":"PROJECTION_INTEGRITY_MISMATCH",'
            '"message":"unexpected projection boundary failure"},'
            '"errors":[],"ok":false}'
        )
    print(output)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
