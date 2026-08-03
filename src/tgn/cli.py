"""JSON CLI used by Codex to host TheGreatNovel in a chat task."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .blueprint import BlueprintError
from .errors import TGNError, error_payload
from .protocol import hello_payload, success_payload
from .service import DEFAULT_SAVES_ROOT, GameService
from .storage import CampaignStoreError, IntegrityError
from .story import NarrationError
from .worlds import ExperienceGateError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tgn", description="TheGreatNovel local deterministic host")
    parser.add_argument("--saves-root", default=str(DEFAULT_SAVES_ROOT), help="campaign save directory")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("hello", help="show protocol and capabilities")
    commands.add_parser("worlds", help="list reviewed built-in worlds")
    compile_world = commands.add_parser("compile-world", help="compile and quality-gate a custom blueprint")
    compile_world.add_argument("--file", required=True)

    start = commands.add_parser("start", help="create a campaign and commit its grounded opening")
    start.add_argument("--prompt", default="")
    start.add_argument("--campaign")
    start.add_argument("--world")
    start.add_argument("--blueprint-file")
    start.add_argument("--seed", type=int)

    commands.add_parser("list", help="list durable campaigns")
    resume = commands.add_parser("resume", help="resume a campaign or the latest active one")
    resume.add_argument("--campaign")

    for name in ("state", "actions", "pending", "verify", "export"):
        sub = commands.add_parser(name)
        sub.add_argument("--campaign", required=True)

    preview = commands.add_parser("preview", help="pure legal/cost/risk preview")
    preview.add_argument("--campaign", required=True)
    preview.add_argument("--action", required=True)
    preview.add_argument("--without-lever", action="store_true")

    act = commands.add_parser("act", help="commit exactly one engine-validated decision")
    act.add_argument("--campaign", required=True)
    accepted = act.add_mutually_exclusive_group(required=True)
    accepted.add_argument("--action")
    accepted.add_argument("--preview-token")
    act.add_argument("--request-id", required=True)
    act.add_argument("--expected-turn", type=int)
    act.add_argument("--without-lever", action="store_true")

    narrate = commands.add_parser("narrate", help="commit prose bound to the pending fact set")
    narrate.add_argument("--campaign", required=True)
    prose = narrate.add_mutually_exclusive_group(required=True)
    prose.add_argument("--prose")
    prose.add_argument("--prose-file")
    prose.add_argument("--fallback", action="store_true")

    end = commands.add_parser("end", help="commit an ending request before final prose/export")
    end.add_argument("--campaign", required=True)
    end.add_argument("--request-id", required=True)
    end.add_argument("--reason", default="player_requested")
    return parser


def _expected_error(exc: Exception) -> TGNError:
    if isinstance(exc, FileNotFoundError):
        return TGNError("NOT_FOUND", str(exc), recoverable=True)
    if isinstance(exc, IntegrityError):
        return TGNError("INTEGRITY_ERROR", str(exc), recoverable=True, details={"exception_type": type(exc).__name__})
    if isinstance(exc, (BlueprintError, ExperienceGateError)):
        details = getattr(exc, "report", {})
        return TGNError("WORLD_REJECTED", str(exc), recoverable=True, details=dict(details))
    if isinstance(exc, NarrationError):
        return TGNError("NARRATION_REJECTED", str(exc), recoverable=True)
    if isinstance(exc, CampaignStoreError):
        return TGNError("CAMPAIGN_CONFLICT", str(exc), recoverable=True, retryable=True)
    if isinstance(exc, (ValueError, TypeError)):
        return TGNError("INVALID_INPUT", str(exc), recoverable=True)
    return TGNError(
        "INTERNAL_ERROR",
        "本地游戏引擎遇到未分类错误。",
        details={"exception_type": type(exc).__name__},
    )


def _read_prose(args: argparse.Namespace) -> str | None:
    if args.prose_file:
        path = Path(args.prose_file).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path.read_text(encoding="utf-8")
    return args.prose


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "hello":
        return hello_payload()
    service = GameService(args.saves_root)
    if args.command == "worlds":
        data: Any = {"worlds": service.available_worlds()}
    elif args.command == "compile-world":
        data = service.compile_world_file(args.file)
    elif args.command == "start":
        data = service.start(
            args.prompt,
            campaign_id=args.campaign,
            world_id=args.world,
            blueprint_file=args.blueprint_file,
            seed=args.seed,
        )
    elif args.command == "list":
        data = {"campaigns": service.list_campaigns()}
    elif args.command == "resume":
        data = service.resume(args.campaign)
    elif args.command == "state":
        data = service.state(args.campaign)
    elif args.command == "actions":
        data = service.actions(args.campaign)
    elif args.command == "preview":
        data = service.preview(args.campaign, args.action, use_lever=not args.without_lever)
    elif args.command == "act":
        if args.action:
            data = service.act_by_id(
                args.campaign,
                args.action,
                args.request_id,
                use_lever=not args.without_lever,
                expected_turn=args.expected_turn,
            )
        else:
            data = service.act(args.campaign, args.preview_token, args.request_id)
    elif args.command == "pending":
        data = service.pending(args.campaign)
    elif args.command == "narrate":
        data = service.narrate(args.campaign, _read_prose(args), fallback=args.fallback)
    elif args.command == "end":
        data = service.end(args.campaign, args.request_id, args.reason)
    elif args.command == "verify":
        data = service.verify(args.campaign)
    elif args.command == "export":
        data = service.export_final(args.campaign)
    else:  # argparse prevents this branch.
        raise ValueError(f"unknown command: {args.command}")
    return success_payload(command=args.command, data=data)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = _dispatch(args)
        code = 0
    except Exception as exc:  # public CLI boundary
        payload = error_payload(_expected_error(exc))
        code = 2
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
