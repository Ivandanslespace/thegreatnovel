from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from novel_authoring.cli import app
from novel_authoring.config import load_settings
from novel_authoring.ingest.service import ingest_book
from novel_authoring.utils import sha256_file


def _ingested_workspace(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "中文原文"
    source.mkdir()
    source_file = source / "短篇.md"
    source_file.write_text("## 第一章 起点\n只有合成文本。\n", encoding="utf-8")
    workspace = tmp_path / "中文工作区"
    ingest_book(
        book_id="cli-book",
        title="CLI 合成书",
        source_root=source,
        workspace_root=workspace,
        settings=load_settings(),
    )
    return workspace, source_file


def test_directive_status_and_export_are_auditable(tmp_path: Path) -> None:
    workspace, source_file = _ingested_workspace(tmp_path)
    source_hash = sha256_file(source_file)
    runner = CliRunner()

    directive = runner.invoke(
        app,
        [
            "directive",
            "add",
            "--book-id",
            "cli-book",
            "--workspace",
            str(workspace),
            "--type",
            "requirement",
            "--content",
            "下一章必须让主角主动选择",
        ],
    )
    assert directive.exit_code == 0, directive.output
    directive_payload = json.loads(directive.output)
    assert directive_payload["status"] == "ACTIVE"
    assert directive_payload["through_event_seq"] == 1

    status = runner.invoke(
        app,
        ["status", "--book-id", "cli-book", "--workspace", str(workspace)],
    )
    assert status.exit_code == 0, status.output
    status_payload = json.loads(status.output)
    assert status_payload["counts"]["author_directives"] == 1
    assert status_payload["projection"]["through_event_seq"] == 1
    assert status_payload["unresolved_hard_conflicts"] == 0

    exported = runner.invoke(
        app,
        ["export", "--book-id", "cli-book", "--workspace", str(workspace)],
    )
    assert exported.exit_code == 0, exported.output
    export_payload = json.loads(exported.output)
    export_path = Path(export_payload["path"])
    assert (export_path / "manifest.json").is_file()
    assert (export_path / "canon_projection.json").is_file()
    assert (export_path / "audit.json").is_file()
    assert sha256_file(source_file) == source_hash


def test_cli_failures_return_nonzero_codes(tmp_path: Path) -> None:
    workspace, _ = _ingested_workspace(tmp_path)
    runner = CliRunner()

    missing_status = runner.invoke(
        app,
        ["status", "--book-id", "missing", "--workspace", str(workspace)],
    )
    assert missing_status.exit_code == 2

    missing_approval = runner.invoke(
        app,
        [
            "approve",
            "--book-id",
            "cli-book",
            "--workspace",
            str(workspace),
            "--draft-id",
            "draft_missing",
            "--confirm",
            "批准写入正史",
        ],
    )
    assert missing_approval.exit_code == 6
    assert "草稿不存在" in missing_approval.output


def test_cli_help_exposes_required_command_surface() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "init",
        "ingest",
        "status",
        "source",
        "extract",
        "reconcile",
        "directive",
        "diagnose",
        "plan-next",
        "contract",
        "boundary",
        "draft",
        "approve",
        "rebuild",
        "snapshot",
        "export",
    ):
        assert command in result.output
