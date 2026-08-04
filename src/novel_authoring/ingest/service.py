from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from novel_authoring.config import Settings
from novel_authoring.db.database import Database
from novel_authoring.domain.models import SourceFileEntry, SourceManifest
from novel_authoring.ingest.chapters import split_chapters
from novel_authoring.ingest.encoding import decode_source
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, stable_id, utc_now


class SourceAmbiguityError(RuntimeError):
    pass


class ImmutableSourceError(RuntimeError):
    pass


@dataclass
class IngestResult:
    book_id: str
    documents_imported: int = 0
    documents_unchanged: int = 0
    chapters_imported: int = 0
    warnings: list[str] = field(default_factory=list)
    manifest_path: Path | None = None


def _source_files(source_root: Path, extensions: list[str]) -> list[Path]:
    allowed = {extension.lower() for extension in extensions}
    return sorted(
        (
            path
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in allowed
        ),
        key=lambda path: path.relative_to(source_root).as_posix().casefold(),
    )


def scan_sources(book_id: str, source_root: Path, settings: Settings) -> SourceManifest:
    root = source_root.resolve()
    files = _source_files(root, settings.ingest.extensions)
    entries: list[SourceFileEntry] = []
    for index, path in enumerate(files, start=1):
        data = path.read_bytes()
        _, encoding = decode_source(data, settings.ingest.encodings)
        entries.append(
            SourceFileEntry(
                relative_path=path.relative_to(root).as_posix(),
                sha256=sha256_bytes(data),
                byte_size=len(data),
                detected_encoding=encoding,
                order_index=index,
                order_confidence=1.0 if len(files) == 1 else 0.5,
                warnings=[] if len(files) == 1 else ["多文件顺序需要作者确认"],
            )
        )
    conflicts = [] if files else ["未检测到 .txt 或 .md 源文件"]
    if len(files) > 1:
        conflicts.append("检测到多个源文件；当前仅按相对路径推断顺序，正式导入前必须确认")
    return SourceManifest(
        book_id=book_id,
        source_root=str(root),
        status="ready" if len(files) <= 1 else "needs_confirmation",
        confirmed=len(files) <= 1,
        files=entries,
        conflicts=conflicts,
        created_at=utc_now(),
    )


def write_manifest(manifest: SourceManifest, workspace_book: Path) -> Path:
    workspace_book.mkdir(parents=True, exist_ok=True)
    path = workspace_book / "source_manifest.json"
    path.write_text(json_dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return path


def load_manifest(path: Path) -> SourceManifest:
    return SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _manifest_matches_scan(manifest: SourceManifest, scanned: SourceManifest) -> bool:
    left = [(item.relative_path, item.sha256) for item in manifest.files]
    right = [(item.relative_path, item.sha256) for item in scanned.files]
    return sorted(left) == sorted(right)


def ingest_book(
    *,
    book_id: str,
    title: str,
    source_root: Path,
    workspace_root: Path,
    settings: Settings,
    confirm_order: bool = False,
    manifest_path: Path | None = None,
) -> IngestResult:
    workspace_book = workspace_root.resolve() / book_id
    scanned = scan_sources(book_id, source_root, settings)
    effective = scanned
    if manifest_path is not None:
        supplied = load_manifest(manifest_path)
        if not _manifest_matches_scan(supplied, scanned):
            raise ImmutableSourceError("manifest 与当前源文件路径/哈希不一致")
        effective = supplied
    if confirm_order:
        effective = effective.model_copy(update={"confirmed": True, "status": "ready"})
    persisted_manifest = write_manifest(effective, workspace_book)
    if not effective.files:
        raise SourceAmbiguityError(f"没有可导入源文件；manifest: {persisted_manifest}")
    if not effective.confirmed:
        raise SourceAmbiguityError(
            f"多文件顺序尚未确认；请编辑 manifest 或使用 --confirm-order：{persisted_manifest}"
        )

    for directory in (
        "agent_tasks",
        "agent_outputs",
        "boundaries",
        "candidates",
        "contracts",
        "drafts",
        "validation",
        "canon",
        "snapshots",
        "exports",
    ):
        (workspace_book / directory).mkdir(parents=True, exist_ok=True)

    database = Database(workspace_book / "state.sqlite3")
    database.initialize()
    now = utc_now()
    result = IngestResult(book_id=book_id, manifest_path=persisted_manifest)
    ordered_files = sorted(effective.files, key=lambda item: item.order_index)
    source_base = Path(effective.source_root)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO books(
                book_id, title, mode, source_root, workspace_root, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at
            """,
            (
                book_id,
                title,
                settings.default_mode,
                str(source_base),
                str(workspace_book),
                now,
                now,
            ),
        )
        for entry in ordered_files:
            path = source_base / Path(entry.relative_path)
            before_hash = sha256_file(path)
            if before_hash != entry.sha256:
                raise ImmutableSourceError(f"导入前哈希不匹配：{entry.relative_path}")
            existing = connection.execute(
                """
                SELECT document_id, sha256 FROM source_documents
                WHERE book_id=? AND relative_path=?
                """,
                (book_id, entry.relative_path),
            ).fetchone()
            if existing is not None:
                if existing["sha256"] != entry.sha256:
                    raise ImmutableSourceError(
                        f"已导入源路径内容发生变化，拒绝覆盖：{entry.relative_path}"
                    )
                result.documents_unchanged += 1
                continue

            data = path.read_bytes()
            text, encoding = decode_source(data, settings.ingest.encodings)
            split = split_chapters(
                text,
                settings.ingest.chapter_patterns,
                settings.ingest.volume_patterns,
            )
            document_id = stable_id("doc", book_id, entry.relative_path, entry.sha256)
            connection.execute(
                """
                INSERT INTO source_documents(
                    document_id, book_id, relative_path, sha256, encoding, byte_size, line_count,
                    order_index, order_confidence, status, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?)
                """,
                (
                    document_id,
                    book_id,
                    entry.relative_path,
                    entry.sha256,
                    encoding,
                    len(data),
                    len(text.splitlines()),
                    entry.order_index,
                    entry.order_confidence,
                    now,
                ),
            )
            if split.preamble:
                span_id = stable_id("span", document_id, "preamble")
                connection.execute(
                    """
                    INSERT INTO source_spans(
                        span_id, book_id, document_id, chapter_id, kind, start_line, end_line,
                        start_char, end_char, text_sha256, excerpt, created_at
                    ) VALUES (?, ?, ?, NULL, 'preamble', 1, ?, 0, ?, ?, ?, ?)
                    """,
                    (
                        span_id,
                        book_id,
                        document_id,
                        split.preamble_end_line,
                        len(split.preamble),
                        sha256_bytes(split.preamble.encode("utf-8")),
                        split.preamble[:240],
                        now,
                    ),
                )
            for chapter in split.chapters:
                chapter_id = stable_id("chapter", document_id, str(chapter.ordinal))
                content_sha = sha256_bytes(chapter.text.encode("utf-8"))
                connection.execute(
                    """
                    INSERT INTO chapters(
                        chapter_id, book_id, document_id, ordinal, raw_heading,
                        chapter_number_text, title, volume_title, start_line, end_line,
                        start_char, end_char, content, content_sha256, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chapter_id,
                        book_id,
                        document_id,
                        chapter.ordinal,
                        chapter.raw_heading,
                        chapter.chapter_number_text,
                        chapter.title,
                        chapter.volume_title,
                        chapter.start_line,
                        chapter.end_line,
                        chapter.start_char,
                        chapter.end_char,
                        chapter.text,
                        content_sha,
                        now,
                    ),
                )
                span_id = stable_id("span", chapter_id, "chapter")
                connection.execute(
                    """
                    INSERT INTO source_spans(
                        span_id, book_id, document_id, chapter_id, kind, start_line, end_line,
                        start_char, end_char, text_sha256, excerpt, created_at
                    ) VALUES (?, ?, ?, ?, 'chapter', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        span_id,
                        book_id,
                        document_id,
                        chapter_id,
                        chapter.start_line,
                        chapter.end_line,
                        chapter.start_char,
                        chapter.end_char,
                        content_sha,
                        chapter.text[:240],
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO chapter_fts(chapter_id, book_id, heading, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chapter_id, book_id, chapter.raw_heading, chapter.text),
                )
            after_hash = sha256_file(path)
            if after_hash != before_hash:
                raise ImmutableSourceError(f"导入过程中源文件发生变化：{entry.relative_path}")
            result.documents_imported += 1
            result.chapters_imported += len(split.chapters)
            result.warnings.extend(
                f"{entry.relative_path}: {warning}" for warning in split.warnings
            )
    return result


def verify_sources(book_id: str, workspace_root: Path) -> dict[str, object]:
    workspace_book = workspace_root.resolve() / book_id
    manifest_path = workspace_book / "source_manifest.json"
    manifest = load_manifest(manifest_path)
    source_root = Path(manifest.source_root)
    results: list[dict[str, object]] = []
    ok = True
    for entry in sorted(manifest.files, key=lambda item: item.order_index):
        path = source_root / Path(entry.relative_path)
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        match = exists and actual == entry.sha256
        ok = ok and match
        results.append(
            {
                "relative_path": entry.relative_path,
                "expected_sha256": entry.sha256,
                "actual_sha256": actual,
                "exists": exists,
                "match": match,
            }
        )
    return {"book_id": book_id, "ok": ok, "files": results}
