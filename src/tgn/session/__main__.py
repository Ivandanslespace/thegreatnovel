"""Command-line entry point for the one-shot Phase 9A session protocol."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from ..core.hashing import canonical_json
from .models import SessionError
from .service import SessionService


class _JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SessionError("INVALID_ARGUMENTS", message)


def _add_session_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session-dir", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = _JSONArgumentParser(prog="python -m tgn.session")
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=_JSONArgumentParser
    )

    start = subparsers.add_parser("start")
    _add_session_dir(start)
    start.add_argument("--session-id", required=True)
    start.add_argument("--actor-id", required=True)
    start.add_argument("--max-decisions", required=True, type=int)
    start.add_argument("--initial-state", required=True)

    for name in ("next", "status", "verify"):
        command = subparsers.add_parser(name)
        _add_session_dir(command)

    choose = subparsers.add_parser("choose")
    _add_session_dir(choose)
    choose.add_argument("--request-fingerprint", required=True)
    choose.add_argument("--choice-id", required=True)

    stop = subparsers.add_parser("stop")
    _add_session_dir(stop)
    stop.add_argument("--request-fingerprint", required=True)
    return parser


def _dispatch(arguments: argparse.Namespace) -> dict:
    if arguments.command == "start":
        return SessionService.start(
            arguments.session_dir,
            session_id=arguments.session_id,
            actor_id=arguments.actor_id,
            max_decisions=arguments.max_decisions,
            initial_state_path=arguments.initial_state,
        )
    service = SessionService(arguments.session_dir)
    if arguments.command == "next":
        return service.next()
    if arguments.command == "choose":
        return service.choose(
            request_fingerprint=arguments.request_fingerprint,
            choice_id=arguments.choice_id,
        )
    if arguments.command == "stop":
        return service.stop(request_fingerprint=arguments.request_fingerprint)
    if arguments.command == "status":
        return service.status()
    if arguments.command == "verify":
        return service.verify()
    raise SessionError("INVALID_ARGUMENTS", "unknown command")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        result = _dispatch(arguments)
    except SessionError as exc:
        print(
            canonical_json(
                {
                    "ok": False,
                    "error": {"code": exc.code, "message": exc.message},
                }
            )
        )
        return 1
    except Exception:
        print(
            canonical_json(
                {
                    "ok": False,
                    "error": {
                        "code": "SESSION_INTEGRITY_MISMATCH",
                        "message": "session command failed",
                    },
                }
            )
        )
        return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess smoke tests
    sys.exit(main())
