"""Thin Campaign adapter over the frozen WorldPack, Projection, and Session APIs."""

from __future__ import annotations

import copy
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .. import projection as frozen_projection
from .. import session as frozen_session
from ..session import SessionError
from .common import copy_files, read_canonical_json, sha256_bytes, write_canonical_json
from .models import (
    CAMPAIGN_FORMAT_ID,
    CAMPAIGN_SCHEMA_VERSION,
    CampaignError,
    CampaignManifest,
)
from . import publication
from .verification import (
    CAMPAIGN_FILE,
    load_projection_map,
    load_projection_manifest,
    verify_external_pair,
    verify_published_campaign,
)
from ..projection import PROJECTION_FILES
from ..worldgen import BUNDLE_FILES
from ..llm_player import build_llm_decision_request
from ..gameplay.expedition import build_observation
from ..core.models import GameState


def _input_error(message: str) -> CampaignError:
    return CampaignError("INVALID_CAMPAIGN_INPUT", message)


def _validate_create_input(
    campaign_dir: str | Path,
    world_bundle_dir: str | Path,
    projection_bundle_dir: str | Path,
    campaign_id: Any,
    actor_id: Any,
    max_decisions: Any,
) -> tuple[Path, Path, Path]:
    try:
        target = Path(campaign_dir)
        world_root = Path(world_bundle_dir)
        projection_root = Path(projection_bundle_dir)
    except (TypeError, ValueError) as exc:
        raise _input_error("Campaign paths are invalid") from exc
    if not isinstance(campaign_id, str) or not _stable_id(campaign_id):
        raise _input_error("campaign_id is invalid")
    if not isinstance(actor_id, str) or not _stable_id(actor_id):
        raise _input_error("actor_id is invalid")
    if type(max_decisions) is not int or max_decisions <= 0:
        raise _input_error("max_decisions must be a positive integer")
    return target, world_root, projection_root


def _stable_id(value: str) -> bool:
    import re

    return re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}\Z", value) is not None


def _validate_operation_argument(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise _input_error(f"{field} must be a string")
    return value


def _map_session_error(error: SessionError, *, bootstrap: bool = False) -> CampaignError:
    if error.code in {"STALE_REQUEST", "UNKNOWN_CHOICE", "SESSION_TERMINAL"} and not bootstrap:
        messages = {
            "STALE_REQUEST": "request fingerprint is stale",
            "UNKNOWN_CHOICE": "choice_id is not currently legal",
            "SESSION_TERMINAL": "session is not accepting decisions",
        }
        return CampaignError(error.code, messages[error.code])
    if bootstrap:
        return CampaignError("SESSION_BOOTSTRAP_FAILED", "Phase 9A Session bootstrap failed")
    if error.code == "SESSION_NOT_FOUND":
        return CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session is missing")
    return CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session is invalid")


def _sqlite_initial_hash(session_dir: Path, campaign_id: str) -> str:
    try:
        connection = sqlite3.connect(session_dir.joinpath("campaign.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT initial_state_hash FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as exc:
        raise CampaignError("SESSION_BOOTSTRAP_FAILED", "Phase 9A Session SQLite bootstrap failed") from exc
    if row is None or not isinstance(row[0], str):
        raise CampaignError("SESSION_BOOTSTRAP_FAILED", "Phase 9A Session Campaign row is missing")
    return row[0]


def _response(verified, *, include_verification: bool = False, result: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "campaign": verified.manifest.to_dict(),
        "session": copy.deepcopy(verified.session_summary),
        "canonical_request": (
            verified.current_request.to_dict() if verified.current_request is not None else None
        ),
        "player_presentation": (
            verified.current_presentation.to_dict()
            if verified.current_presentation is not None
            else None
        ),
    }
    if result is not None:
        payload["result"] = copy.deepcopy(result)
    if include_verification:
        payload["verification"] = copy.deepcopy(verified.verification)
    return payload


class CampaignService:
    """One-shot Campaign facade; every public operation reopens the tree."""

    def __init__(self, campaign_dir: str | Path) -> None:
        try:
            self.campaign_dir = Path(campaign_dir)
        except (TypeError, ValueError) as exc:
            raise _input_error("campaign_dir is invalid") from exc

    @classmethod
    def create(
        cls,
        campaign_dir: str | Path,
        *,
        world_bundle_dir: str | Path,
        projection_bundle_dir: str | Path,
        campaign_id: str,
        actor_id: str,
        max_decisions: int,
    ) -> dict[str, Any]:
        target, world_root, projection_root = _validate_create_input(
            campaign_dir,
            world_bundle_dir,
            projection_bundle_dir,
            campaign_id,
            actor_id,
            max_decisions,
        )
        try:
            publication.assert_publication_capability()
        except publication._NoReplaceUnavailable as exc:
            raise CampaignError(
                "CAMPAIGN_PUBLICATION_UNAVAILABLE",
                "atomic Campaign publication is unavailable",
            ) from exc

        lock_path = publication.publication_lock_path(target)
        if target.exists() or lock_path.exists():
            raise CampaignError("CAMPAIGN_ALREADY_EXISTS", "Campaign target or publication lock already exists")

        source_verification, _ = verify_external_pair(world_root, projection_root)
        temporary: Path | None = None
        lock_fd: int | None = None
        lock_owned = False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
            (temporary / "world").mkdir()
            (temporary / "projection").mkdir()
            copy_files(world_root, temporary / "world", sorted(BUNDLE_FILES))
            copy_files(projection_root, temporary / "projection", sorted(PROJECTION_FILES))

            copied_source, copied_projection = verify_external_pair(
                temporary / "world", temporary / "projection"
            )
            if copied_source != source_verification:
                # The copied bytes are authoritative; the external result is never reused.
                source_verification = copied_source
            if (
                copied_projection.get("source_worldpack_hash") != copied_source.get("worldpack_hash")
                or copied_projection.get("source_initial_state_hash")
                != copied_source.get("initial_state_hash")
            ):
                raise CampaignError("PROJECTION_SOURCE_MISMATCH", "copied Projection source binding is invalid")

            try:
                frozen_session.start_session(
                    temporary / "session",
                    session_id=campaign_id,
                    actor_id=actor_id,
                    max_decisions=max_decisions,
                    initial_state_path=temporary / "world" / "initial_state.json",
                )
                frozen_session.verify_session(temporary / "session")
            except SessionError as exc:
                raise _map_session_error(exc, bootstrap=True) from exc
            except CampaignError:
                raise
            except Exception as exc:
                raise CampaignError("SESSION_BOOTSTRAP_FAILED", "Phase 9A Session bootstrap failed") from exc

            initial_state_value = read_canonical_json(temporary / "world" / "initial_state.json")
            initial_state = GameState(**copy.deepcopy(initial_state_value))
            initial_request = build_llm_decision_request(build_observation(initial_state), 1)
            projection_map, projection_value = load_projection_map(temporary / "projection")
            initial_presentation = frozen_projection.build_player_presentation(initial_request, projection_map)
            projection_manifest = load_projection_manifest(temporary / "projection")
            world_manifest = read_canonical_json(temporary / "world" / "bundle.json")
            artifact_hashes = {
                "worldpack_hash": sha256_bytes((temporary / "world" / "compiled_worldpack.json").read_bytes()),
                "source_initial_state_hash": sha256_bytes((temporary / "world" / "initial_state.json").read_bytes()),
                "world_bundle_manifest_hash": sha256_bytes((temporary / "world" / "bundle.json").read_bytes()),
                "player_projection_hash": sha256_bytes((temporary / "projection" / "player_projection.json").read_bytes()),
                "projection_bundle_manifest_hash": sha256_bytes((temporary / "projection" / "projection_manifest.json").read_bytes()),
            }
            if artifact_hashes["worldpack_hash"] != source_verification["worldpack_hash"] or artifact_hashes["source_initial_state_hash"] != source_verification["initial_state_hash"]:
                raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "copied WorldPack hashes changed")
            initial_session_hash = _sqlite_initial_hash(temporary / "session", campaign_id)
            if initial_session_hash != artifact_hashes["source_initial_state_hash"]:
                raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "initial Session state binding is invalid")
            manifest = CampaignManifest(
                schema_version=CAMPAIGN_SCHEMA_VERSION,
                campaign_format_id=CAMPAIGN_FORMAT_ID,
                campaign_id=campaign_id,
                worldpack_hash=artifact_hashes["worldpack_hash"],
                source_initial_state_hash=artifact_hashes["source_initial_state_hash"],
                world_bundle_manifest_hash=artifact_hashes["world_bundle_manifest_hash"],
                player_projection_hash=artifact_hashes["player_projection_hash"],
                projection_bundle_manifest_hash=artifact_hashes["projection_bundle_manifest_hash"],
                initial_request_fingerprint=initial_request.request_fingerprint,
                initial_presentation_hash=frozen_projection.presentation_hash(initial_presentation),
                session_id=campaign_id,
                actor_id=actor_id,
                max_decisions=max_decisions,
                initial_session_state_hash=initial_session_hash,
            )
            if projection_manifest.get("player_projection_hash") != frozen_projection.projection_hash(projection_map) or world_manifest.get("worldpack_hash") != manifest.worldpack_hash:
                raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "nested artifact bindings are invalid")
            if (
                projection_value.get("source_worldpack_hash") != manifest.worldpack_hash
                or projection_value.get("source_initial_state_hash") != manifest.source_initial_state_hash
            ):
                raise CampaignError("PROJECTION_SOURCE_MISMATCH", "Projection source binding is invalid")
            write_canonical_json(temporary / CAMPAIGN_FILE, manifest.to_dict())
            verified = verify_published_campaign(temporary, bootstrap=True)

            try:
                lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                lock_owned = True
            except FileExistsError as exc:
                raise CampaignError("CAMPAIGN_ALREADY_EXISTS", "Campaign publication lock already exists") from exc
            if target.exists():
                raise CampaignError("CAMPAIGN_ALREADY_EXISTS", "Campaign target appeared before publication")
            try:
                publication._publish_directory_no_replace(temporary, target)
            except FileExistsError as exc:
                raise CampaignError("CAMPAIGN_ALREADY_EXISTS", "Campaign target appeared during publication") from exc
            except publication._NoReplaceUnavailable as exc:
                raise CampaignError("CAMPAIGN_PUBLICATION_UNAVAILABLE", "atomic Campaign publication is unavailable") from exc
            temporary = None
            return _response(verified)
        except CampaignError:
            raise
        except Exception as exc:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "Campaign creation failed") from exc
        finally:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except OSError:
                    pass
            if lock_owned:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
            if temporary is not None:
                shutil.rmtree(temporary, ignore_errors=True)

    def _verified(self):
        try:
            return verify_published_campaign(self.campaign_dir)
        except SessionError as exc:
            raise _map_session_error(exc) from exc

    def next(self) -> dict[str, Any]:
        return _response(self._verified())

    def status(self) -> dict[str, Any]:
        verified = self._verified()
        return {
            "ok": True,
            "campaign": verified.manifest.to_dict(),
            "session": copy.deepcopy(verified.session_summary),
        }

    def choose(self, *, request_fingerprint: str, choice_id: str) -> dict[str, Any]:
        _validate_operation_argument(request_fingerprint, "request_fingerprint")
        _validate_operation_argument(choice_id, "choice_id")
        self._verified()
        try:
            result = frozen_session.choose_session(
                self.campaign_dir / "session",
                request_fingerprint=request_fingerprint,
                choice_id=choice_id,
            )
        except SessionError as exc:
            raise _map_session_error(exc) from exc
        except Exception as exc:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session operation failed") from exc
        return _response(self._verified(), result=result.get("result"))

    def stop(self, *, request_fingerprint: str) -> dict[str, Any]:
        _validate_operation_argument(request_fingerprint, "request_fingerprint")
        self._verified()
        try:
            frozen_session.stop_session(
                self.campaign_dir / "session",
                request_fingerprint=request_fingerprint,
            )
        except SessionError as exc:
            raise _map_session_error(exc) from exc
        except Exception as exc:
            raise CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "published Campaign Session operation failed") from exc
        return _response(self._verified())

    def verify(self) -> dict[str, Any]:
        return _response(self._verified(), include_verification=True)


def create_campaign(
    campaign_dir: str | Path,
    *,
    world_bundle_dir: str | Path,
    projection_bundle_dir: str | Path,
    campaign_id: str,
    actor_id: str,
    max_decisions: int,
) -> dict[str, Any]:
    return CampaignService.create(
        campaign_dir,
        world_bundle_dir=world_bundle_dir,
        projection_bundle_dir=projection_bundle_dir,
        campaign_id=campaign_id,
        actor_id=actor_id,
        max_decisions=max_decisions,
    )


def next_campaign(campaign_dir: str | Path) -> dict[str, Any]:
    return CampaignService(campaign_dir).next()


def choose_campaign(
    campaign_dir: str | Path, *, request_fingerprint: str, choice_id: str
) -> dict[str, Any]:
    return CampaignService(campaign_dir).choose(
        request_fingerprint=request_fingerprint,
        choice_id=choice_id,
    )


def stop_campaign(campaign_dir: str | Path, *, request_fingerprint: str) -> dict[str, Any]:
    return CampaignService(campaign_dir).stop(request_fingerprint=request_fingerprint)


def status_campaign(campaign_dir: str | Path) -> dict[str, Any]:
    return CampaignService(campaign_dir).status()


def verify_campaign(campaign_dir: str | Path) -> dict[str, Any]:
    return CampaignService(campaign_dir).verify()


__all__ = [
    "CampaignService",
    "choose_campaign",
    "create_campaign",
    "next_campaign",
    "status_campaign",
    "stop_campaign",
    "verify_campaign",
]
