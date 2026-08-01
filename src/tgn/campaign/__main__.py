"""CLI for the bounded Phase 9B2B Campaign boundary."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ..core.hashing import canonical_json
from .common import safe_json_error
from .models import CampaignError
from .service import (
    choose_campaign,
    create_campaign,
    next_campaign,
    status_campaign,
    stop_campaign,
    verify_campaign,
)


class _JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CampaignError("INVALID_CAMPAIGN_INPUT", "malformed Campaign command")


def build_parser() -> argparse.ArgumentParser:
    parser = _JSONArgumentParser(prog="python -m tgn.campaign")
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=_JSONArgumentParser
    )
    create = subparsers.add_parser("create")
    create.add_argument("--campaign-dir", required=True)
    create.add_argument("--world-bundle-dir", required=True)
    create.add_argument("--projection-bundle-dir", required=True)
    create.add_argument("--campaign-id", required=True)
    create.add_argument("--actor-id", required=True)
    create.add_argument("--max-decisions", required=True, type=int)

    for name in ("next", "status", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--campaign-dir", required=True)

    choose = subparsers.add_parser("choose")
    choose.add_argument("--campaign-dir", required=True)
    choose.add_argument("--request-fingerprint", required=True)
    choose.add_argument("--choice-id", required=True)

    stop = subparsers.add_parser("stop")
    stop.add_argument("--campaign-dir", required=True)
    stop.add_argument("--request-fingerprint", required=True)
    return parser


def _dispatch(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "create":
        return create_campaign(
            arguments.campaign_dir,
            world_bundle_dir=arguments.world_bundle_dir,
            projection_bundle_dir=arguments.projection_bundle_dir,
            campaign_id=arguments.campaign_id,
            actor_id=arguments.actor_id,
            max_decisions=arguments.max_decisions,
        )
    if arguments.command == "next":
        return next_campaign(arguments.campaign_dir)
    if arguments.command == "choose":
        return choose_campaign(
            arguments.campaign_dir,
            request_fingerprint=arguments.request_fingerprint,
            choice_id=arguments.choice_id,
        )
    if arguments.command == "stop":
        return stop_campaign(
            arguments.campaign_dir,
            request_fingerprint=arguments.request_fingerprint,
        )
    if arguments.command == "status":
        return status_campaign(arguments.campaign_dir)
    return verify_campaign(arguments.campaign_dir)


def main(argv: list[str] | None = None) -> int:
    try:
        payload = _dispatch(build_parser().parse_args(argv))
        exit_code = 0
    except CampaignError as exc:
        payload = safe_json_error(exc)
        exit_code = 2
    except Exception:
        payload = safe_json_error(
            CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "Campaign boundary failure")
        )
        exit_code = 2
    try:
        output = canonical_json(payload)
    except (TypeError, ValueError):
        output = '{"error":{"code":"CAMPAIGN_INTEGRITY_MISMATCH","message":"Campaign boundary failure"},"ok":false}'
        exit_code = 2
    print(output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
