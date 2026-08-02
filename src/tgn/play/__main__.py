"""CLI for the PC1 local playable client."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from ..core.hashing import canonical_json
from .common import PlayError, parse_nonnegative_integer, parse_positive_integer
from .narrator_process import DEFAULT_NARRATOR_TIMEOUT, validate_timeout
from .service import DEFAULT_VOICE_ID, PlayService


class _PlayArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PlayError("INVALID_PLAY_INPUT", "malformed Playable Client command")


def _add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True)


def _add_narrator(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--narrator-exec")
    parser.add_argument("--narrator-arg", action="append", default=[])
    parser.add_argument("--narrator-timeout", default=str(DEFAULT_NARRATOR_TIMEOUT))


def build_parser() -> argparse.ArgumentParser:
    parser = _PlayArgumentParser(prog="python -m tgn.play")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_PlayArgumentParser)

    new = commands.add_parser("new")
    _add_workspace(new)
    new.add_argument("--world-bundle-dir", required=True)
    new.add_argument("--projection-bundle-dir", required=True)
    new.add_argument("--campaign-id", required=True)
    new.add_argument("--story-id", required=True)
    new.add_argument("--actor-id", required=True)
    new.add_argument("--max-decisions", required=True)
    new.add_argument("--locale", required=True)
    new.add_argument("--voice-id", required=True)
    _add_narrator(new)

    resume = commands.add_parser("resume")
    _add_workspace(resume)
    resume.add_argument("--locale")
    resume.add_argument("--story-id")
    resume.add_argument("--voice-id", default=DEFAULT_VOICE_ID)
    _add_narrator(resume)

    narrate = commands.add_parser("narrate")
    _add_workspace(narrate)
    narrate.add_argument("--response-file", required=True)

    for name in ("status", "verify"):
        command = commands.add_parser(name)
        _add_workspace(command)

    export = commands.add_parser("export")
    _add_workspace(export)
    export.add_argument("--mode", required=True)
    export.add_argument("--accepted-decisions")
    return parser


def _narrator_argv(arguments: argparse.Namespace) -> tuple[list[str] | None, float]:
    try:
        timeout = validate_timeout(arguments.narrator_timeout)
    except PlayError:
        raise
    if arguments.narrator_exec is None:
        if arguments.narrator_arg:
            raise PlayError("INVALID_PLAY_INPUT", "narrator arguments require narrator executable")
        return None, timeout
    if not isinstance(arguments.narrator_exec, str) or not arguments.narrator_exec or "\x00" in arguments.narrator_exec:
        raise PlayError("INVALID_PLAY_INPUT", "narrator executable is invalid")
    if not isinstance(arguments.narrator_arg, list) or not all(
        isinstance(item, str) and item and "\x00" not in item for item in arguments.narrator_arg
    ):
        raise PlayError("INVALID_PLAY_INPUT", "narrator arguments are invalid")
    return [arguments.narrator_exec, *arguments.narrator_arg], timeout


def dispatch(arguments: argparse.Namespace, *, input_fn=input, output_fn=print) -> dict[str, Any]:
    if arguments.command == "new":
        max_decisions = parse_positive_integer(arguments.max_decisions, "max_decisions")
        argv, timeout = _narrator_argv(arguments)
        service = PlayService(arguments.workspace)
        return service.new(
            world_bundle_dir=arguments.world_bundle_dir,
            projection_bundle_dir=arguments.projection_bundle_dir,
            campaign_id=arguments.campaign_id,
            story_id=arguments.story_id,
            actor_id=arguments.actor_id,
            max_decisions=max_decisions,
            locale=arguments.locale,
            voice_id=arguments.voice_id,
            narrator_argv=argv,
            narrator_timeout=timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    if arguments.command == "resume":
        argv, timeout = _narrator_argv(arguments)
        service = PlayService(arguments.workspace)
        return service.resume(
            locale=arguments.locale,
            story_id=arguments.story_id,
            voice_id=arguments.voice_id,
            narrator_argv=argv,
            narrator_timeout=timeout,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    if arguments.command == "narrate":
        service = PlayService(arguments.workspace)
        return service.narrate(response_file=arguments.response_file, output_fn=output_fn)
    if arguments.command == "status":
        service = PlayService(arguments.workspace)
        return service.status()
    if arguments.command == "verify":
        service = PlayService(arguments.workspace)
        return service.verify()
    if arguments.command == "export":
        accepted = None
        if arguments.accepted_decisions is not None:
            accepted = parse_nonnegative_integer(arguments.accepted_decisions, "accepted_decisions")
        service = PlayService(arguments.workspace)
        return service.export(mode=arguments.mode, accepted_decisions=accepted)
    raise PlayError("INVALID_PLAY_INPUT", "unknown Playable Client command")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        result = dispatch(arguments)
        print(canonical_json(result))
        return 0
    except PlayError as exc:
        print(canonical_json({"ok": False, "error": exc.to_dict()}))
        return exc.exit_code
    except Exception:
        print(canonical_json({"ok": False, "error": {"code": "PLAY_STORY_FAILED", "message": "Playable Client boundary failed"}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
