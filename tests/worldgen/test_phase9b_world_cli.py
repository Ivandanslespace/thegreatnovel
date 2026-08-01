from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tgn.core.hashing import canonical_json
from tgn.worldgen import WorldGenError
import tgn.worldgen.__main__ as cli_module
from tgn.worldgen.__main__ import main

from .conftest import write_json


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tgn.worldgen", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_help_exposes_only_phase9b1_commands():
    result = _run("--help")
    assert result.returncode == 0
    assert "validate" in result.stdout
    assert "compile" in result.stdout
    assert "verify" in result.stdout
    assert "start" not in result.stdout


def test_validate_success_is_json_only_and_creates_no_files(
    tmp_path, input_files
):
    request_path, draft_path = input_files
    result = _run(
        "validate",
        "--request",
        str(request_path),
        "--draft",
        str(draft_path),
        "--seed",
        "cli-seed",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["valid"] is True
    assert payload["preview"]["compiler_id"] == "phase9b-bounded-world-v1"
    assert not list(tmp_path.glob("compiled/**"))


def test_validate_failure_returns_all_machine_issues_without_traceback(
    tmp_path, sample_request, sample_draft
):
    del sample_draft["labels"]["target"]
    sample_draft["rules"] = {"reward": 99}
    request_path = write_json(tmp_path / "request.json", sample_request)
    draft_path = write_json(tmp_path / "draft.json", sample_draft)
    result = _run(
        "validate",
        "--request",
        str(request_path),
        "--draft",
        str(draft_path),
        "--seed",
        "cli-seed",
    )
    assert result.returncode != 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["valid"] is False
    assert [(item["code"], item["path"]) for item in payload["errors"]] == [
        ("MISSING_FIELD", "/labels/target"),
        ("UNKNOWN_FIELD", "/rules"),
    ]
    assert "Traceback" not in result.stdout


def test_compile_and_verify_cli_round_trip(tmp_path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "cli"
    compiled = _run(
        "compile",
        "--request",
        str(request_path),
        "--draft",
        str(draft_path),
        "--seed",
        "cli-seed",
        "--output-dir",
        str(output),
    )
    assert compiled.returncode == 0
    assert json.loads(compiled.stdout)["ok"] is True

    verified = _run("verify", "--bundle-dir", str(output))
    assert verified.returncode == 0
    payload = json.loads(verified.stdout)
    assert payload["ok"] is True
    assert payload["verification"]["valid"] is True


def test_compile_cli_rejects_existing_target(tmp_path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "existing"
    output.mkdir(parents=True)
    first = _run(
        "compile",
        "--request",
        str(request_path),
        "--draft",
        str(draft_path),
        "--seed",
        "cli-seed",
        "--output-dir",
        str(output),
    )
    assert first.returncode != 0
    assert json.loads(first.stdout)["error"]["code"] == "BUNDLE_ALREADY_EXISTS"


def test_verify_cli_reports_tamper_without_repair(tmp_path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "cli-tamper"
    compiled = _run(
        "compile",
        "--request",
        str(request_path),
        "--draft",
        str(draft_path),
        "--seed",
        "cli-seed",
        "--output-dir",
        str(output),
    )
    assert compiled.returncode == 0
    report_path = output / "compile_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["bootstrap"]["events"] = 99
    report_path.write_text(canonical_json(report), encoding="utf-8")
    verified = _run("verify", "--bundle-dir", str(output))
    assert verified.returncode != 0
    assert json.loads(verified.stdout)["error"]["code"] == "BUNDLE_INTEGRITY_MISMATCH"
    assert report_path.exists()


def test_direct_main_validate_and_compile_commands_emit_machine_json(
    tmp_path, input_files, capsys
):
    request_path, draft_path = input_files
    assert (
        main(
            [
                "validate",
                "--request",
                str(request_path),
                "--draft",
                str(draft_path),
                "--seed",
                "direct-seed",
            ]
        )
        == 0
    )
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["valid"] is True

    output = tmp_path / "compiled" / "direct"
    assert (
        main(
            [
                "compile",
                "--request",
                str(request_path),
                "--draft",
                str(draft_path),
                "--seed",
                "direct-seed",
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    compile_payload = json.loads(capsys.readouterr().out)
    assert compile_payload["ok"] is True

    assert main(["verify", "--bundle-dir", str(output)]) == 0
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_payload["verification"]["valid"] is True


def test_direct_main_reports_validation_parse_and_domain_errors(
    tmp_path, input_files, capsys, monkeypatch
):
    request_path, draft_path = input_files
    invalid_request = tmp_path / "invalid-request.json"
    invalid_request.write_text("not json", encoding="utf-8")
    assert (
        main(
            [
                "validate",
                "--request",
                str(invalid_request),
                "--draft",
                str(draft_path),
                "--seed",
                "seed",
            ]
        )
        == 2
    )
    parse_payload = json.loads(capsys.readouterr().out)
    assert parse_payload["error"]["code"] == "INVALID_JSON"

    invalid_draft = tmp_path / "invalid-draft.json"
    invalid_draft.write_text('{"schema_version": 1}', encoding="utf-8")
    assert (
        main(
            [
                "validate",
                "--request",
                str(request_path),
                "--draft",
                str(invalid_draft),
                "--seed",
                "seed",
            ]
        )
        == 2
    )
    schema_payload = json.loads(capsys.readouterr().out)
    assert schema_payload["error"]["code"] == "INVALID_SCHEMA"

    assert (
        main(
            [
                "validate",
                "--request",
                str(request_path),
                "--draft",
                str(draft_path),
                "--seed",
                "",
            ]
        )
        == 2
    )
    domain_validate_payload = json.loads(capsys.readouterr().out)
    assert domain_validate_payload["error"]["code"] == "INVALID_TEXT"

    def fail_compile(*args, **kwargs):
        raise WorldGenError("BOOTSTRAP_FAILED", "forced compile failure")

    monkeypatch.setattr(cli_module, "compile_bundle", fail_compile)
    output = tmp_path / "output"
    assert (
        main(
            [
                "compile",
                "--request",
                str(request_path),
                "--draft",
                str(draft_path),
                "--seed",
                "seed",
                "--output-dir",
                str(output),
            ]
        )
        == 2
    )
    domain_payload = json.loads(capsys.readouterr().out)
    assert domain_payload["error"]["code"] == "BOOTSTRAP_FAILED"


def test_direct_main_reports_unexpected_verify_failure(capsys, monkeypatch, tmp_path):
    def fail_verify(*args, **kwargs):
        raise RuntimeError("forced unexpected failure")

    monkeypatch.setattr(cli_module, "verify_bundle", fail_verify)
    assert main(["verify", "--bundle-dir", str(tmp_path / "bundle")]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "BUNDLE_INTEGRITY_MISMATCH"
    assert payload["errors"] == []
