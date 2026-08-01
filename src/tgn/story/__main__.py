"""Small local CLI for the Phase 9C1 Story boundary."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from ..core.hashing import canonical_json
from .common import parse_json_bytes, read_regular_file
from .models import StoryError
from .service import commit_story, init_story, prepare_story, status_story, verify_story


class _JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise StoryError("INVALID_STORY_INPUT", message)


def build_parser() -> argparse.ArgumentParser:
    parser = _JSONArgumentParser(prog="python -m tgn.story")
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=_JSONArgumentParser
    )

    init_parser = commands.add_parser("init")
    _add_dirs(init_parser)
    init_parser.add_argument("--story-id", required=True)
    init_parser.add_argument("--locale", required=True)
    init_parser.add_argument("--voice-id", required=True)

    prepare_parser = commands.add_parser("prepare")
    _add_dirs(prepare_parser)
    prepare_parser.add_argument("--turn-id")
    prepare_parser.add_argument("--locale")

    commit_parser = commands.add_parser("commit")
    _add_dirs(commit_parser)
    commit_parser.add_argument("response", nargs="?")
    commit_parser.add_argument("--response-file", dest="response_file")

    for name in ("status", "verify"):
        command = commands.add_parser(name)
        _add_dirs(command)
    return parser


def _add_dirs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--story-dir", required=True)
    parser.add_argument("--campaign-dir", required=True)


def _read_response(arguments: argparse.Namespace) -> Any:
    response_path = arguments.response_file or arguments.response
    if not response_path:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response JSON file is required")
    if response_path == "-":
        payload = sys.stdin.buffer.read()
    else:
        try:
            payload, _ = read_regular_file(response_path)
        except (OSError, TypeError, ValueError) as exc:
            raise StoryError("NARRATION_RESPONSE_INVALID", "response JSON cannot be read") from exc
    try:
        return parse_json_bytes(payload, require_canonical=True)
    except Exception as exc:
        raise StoryError("NARRATION_RESPONSE_INVALID", "response JSON is invalid") from exc


def dispatch(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "init":
        return init_story(
            arguments.story_dir,
            campaign_dir=arguments.campaign_dir,
            story_id=arguments.story_id,
            initial_narration_locale=arguments.locale,
            initial_voice_id=arguments.voice_id,
        )
    if arguments.command == "prepare":
        return prepare_story(
            arguments.story_dir,
            campaign_dir=arguments.campaign_dir,
            turn_id=arguments.turn_id,
            narration_locale=arguments.locale,
        )
    if arguments.command == "commit":
        return commit_story(
            arguments.story_dir,
            campaign_dir=arguments.campaign_dir,
            response=_read_response(arguments),
        )
    if arguments.command == "status":
        return status_story(arguments.story_dir, campaign_dir=arguments.campaign_dir)
    if arguments.command == "verify":
        return verify_story(arguments.story_dir, campaign_dir=arguments.campaign_dir)
    raise StoryError("INVALID_STORY_INPUT", "unknown Story command")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        result = dispatch(parser.parse_args(argv))
        print(canonical_json(result))
        return 0
    except StoryError as exc:
        print(canonical_json({"ok": False, "error": exc.to_dict()}))
        return 1
    except Exception:
        print(canonical_json({"ok": False, "error": {"code": "STORY_INTEGRITY_MISMATCH", "message": "Story operation failed"}}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
