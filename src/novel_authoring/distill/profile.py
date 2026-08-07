"""Materialize the author-facing SELF_BOOK Distill view."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.db.database import Database
from novel_authoring.distill.models import DistillScope
from novel_authoring.distill.service import latest_distill_reference
from novel_authoring.edition import resolve_edition_id
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps, utc_now


class BookProfileError(RuntimeError):
    pass


class BookProfileManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_version: str = "book-profil-v1"
    book_id: str = Field(min_length=1)
    edition_id: str = Field(min_length=1)
    distill_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    dimensions: list[str] = Field(min_length=1)
    source_distill_root: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)


def _profile_root(database: Database, book_id: str) -> Path:
    root = book_root(database, book_id)
    if not (root / "book.yaml").is_file():
        raise BookProfileError("book_profil 只支持 Canonical Book Library")
    return BookLayout(root.parent).for_book(book_id).book_profil


def _write(path: Path, value: object) -> None:
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8")


def export_book_profile(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
) -> dict[str, object]:
    """Replace ``book_profil`` atomically from the latest SELF_BOOK package.

    An EXTERNAL_REFERENCE or COMPARATIVE_REFERENCE is intentionally a no-op;
    it can never replace the author's current-book profile.
    """

    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    edition = BookLayout(book_root(database, book_id).parent).for_book(book_id).edition(
        selected_edition
    )
    reference = latest_distill_reference(edition, scope=DistillScope.SELF_BOOK)
    profile_root = _profile_root(database, book_id)
    if reference is None:
        return {
            "exported": False,
            "reason": "NO_SELF_BOOK_DISTILL",
            "book_id": book_id,
            "edition_id": selected_edition,
            "profile_root": str(profile_root),
        }
    if str(reference.get("scope")) != "SELF_BOOK":
        return {
            "exported": False,
            "reason": "NON_SELF_BOOK_DISTILL_CANNOT_OVERWRITE_PROFILE",
            "book_id": book_id,
            "edition_id": selected_edition,
            "scope": reference.get("scope"),
            "profile_root": str(profile_root),
        }
    source_root = Path(str(reference.get("skill_root", ""))).expanduser().resolve()
    if not (source_root / "SKILL.md").is_file():
        raise BookProfileError("latest SELF_BOOK Distill 缺少 SKILL.md")
    dimensions = [str(item) for item in reference.get("dimensions", [])]
    if not dimensions:
        raise BookProfileError("latest SELF_BOOK Distill 没有 dimensions")
    manifest = BookProfileManifest(
        book_id=book_id,
        edition_id=selected_edition,
        distill_id=str(reference["distill_id"]),
        scope="SELF_BOOK",
        depth=str(reference.get("depth") or ""),
        dimensions=dimensions,
        source_distill_root=str(source_root),
        generated_at=utc_now(),
    )
    parent = profile_root.parent
    staging = parent / f".book_profil-stage-{uuid.uuid4().hex}"
    backup = parent / f".book_profil-backup-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        (staging / "README.md").write_text(
            "\n".join(
                [
                    "# Book Profil",
                    "",
                    "这是当前 SELF_BOOK Distill 的作者-facing 派生视图。",
                    "它不是 Canon、Runtime State 或 Edition 权威；"
                    "更新前一版本仍保留在 Distill Package。",
                    "",
                    f"- book_id: `{manifest.book_id}`",
                    f"- edition_id: `{manifest.edition_id}`",
                    f"- distill_id: `{manifest.distill_id}`",
                    f"- scope: `{manifest.scope}`",
                    f"- dimensions: {', '.join(manifest.dimensions)}",
                    "",
                    f"来源 Package：`{manifest.source_distill_root}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _write(staging / "profile_manifest.json", manifest.model_dump(mode="json"))
        copied: list[str] = []
        for dimension in dimensions:
            source = source_root / f"{dimension}.md"
            if not source.is_file() or not source.read_text(encoding="utf-8").strip():
                raise BookProfileError(f"SELF_BOOK Distill 缺少有效维度文件：{dimension}.md")
            shutil.copyfile(source, staging / source.name)
            copied.append(source.name)
        for optional in ("synthesis.md", "craft-controls.md"):
            source = source_root / optional
            if source.is_file() and source.read_text(encoding="utf-8").strip():
                shutil.copyfile(source, staging / optional)
                copied.append(optional)
        if profile_root.exists():
            profile_root.replace(backup)
        staging.replace(profile_root)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if not profile_root.exists() and backup.exists():
            backup.replace(profile_root)
        raise
    return {
        "exported": True,
        "book_id": book_id,
        "edition_id": selected_edition,
        "distill_id": manifest.distill_id,
        "scope": manifest.scope,
        "profile_root": str(profile_root),
        "manifest": str(profile_root / "profile_manifest.json"),
        "files": ["README.md", "profile_manifest.json", *copied],
    }


__all__ = ["BookProfileError", "BookProfileManifest", "export_book_profile"]
