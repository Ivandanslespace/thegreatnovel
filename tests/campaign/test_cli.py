from __future__ import annotations

import json
import runpy
import sys
import warnings

from tgn.campaign.__main__ import main
import tgn.campaign.__main__ as cli

from .conftest import choice_for


def run_cli(capsys, argv: list[str]) -> tuple[int, dict]:
    code = main(argv)
    output = capsys.readouterr().out.strip()
    assert "Traceback" not in output
    return code, json.loads(output)


def test_cli_success_envelopes(capsys, bundle_pair, tmp_path) -> None:
    target = tmp_path / "campaign"
    base = [
        "--campaign-dir",
        str(target),
    ]
    code, created = run_cli(
        capsys,
        [
            "create",
            *base,
            "--world-bundle-dir",
            str(bundle_pair[0]),
            "--projection-bundle-dir",
            str(bundle_pair[1]),
            "--campaign-id",
            "campaign-001",
            "--actor-id",
            "player",
            "--max-decisions",
            "10",
        ],
    )
    assert code == 0
    assert created["ok"] is True
    request = created["canonical_request"]
    choice = choice_for(request, "DROP")

    code, next_payload = run_cli(capsys, ["next", *base])
    assert code == 0
    assert next_payload["canonical_request"] == request

    code, chosen = run_cli(
        capsys,
        [
            "choose",
            *base,
            "--request-fingerprint",
            request["request_fingerprint"],
            "--choice-id",
            choice["choice_id"],
        ],
    )
    assert code == 0
    assert chosen["result"]["choice_id"] == choice["choice_id"]

    code, status = run_cli(capsys, ["status", *base])
    assert code == 0
    assert status["ok"] is True
    code, verified = run_cli(capsys, ["verify", *base])
    assert code == 0
    assert verified["verification"]["valid"] is True

    current = next_payload = chosen["canonical_request"]
    code, stopped = run_cli(
        capsys,
        [
            "stop",
            *base,
            "--request-fingerprint",
            current["request_fingerprint"],
        ],
    )
    assert code == 0
    assert stopped["canonical_request"] is None


def test_cli_expected_errors_are_json_and_exit_two(capsys, tmp_path) -> None:
    code, payload = run_cli(capsys, ["status", "--campaign-dir", str(tmp_path / "missing")])
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "CAMPAIGN_NOT_FOUND"
    assert set(payload) == {"ok", "error"}

    code, payload = run_cli(capsys, ["not-a-command"])
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_CAMPAIGN_INPUT"


def test_cli_stale_request_preserves_safe_message(capsys, campaign_factory) -> None:
    target, created = campaign_factory()
    code, payload = run_cli(
        capsys,
        [
            "choose",
            "--campaign-dir",
            str(target),
            "--request-fingerprint",
            "f" * 64,
            "--choice-id",
            created["canonical_request"]["choices"][0]["choice_id"],
        ],
    )
    assert code == 2
    assert payload == {
        "ok": False,
        "error": {"code": "STALE_REQUEST", "message": "request fingerprint is stale"},
    }


def test_cli_hides_unexpected_exception_and_serialization_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_dispatch", lambda _arguments: (_ for _ in ()).throw(RuntimeError("raw")))
    assert main(["status", "--campaign-dir", "missing"]) == 2
    output = capsys.readouterr().out
    assert "raw" not in output
    assert "CAMPAIGN_INTEGRITY_MISMATCH" in output

    monkeypatch.setattr(cli, "_dispatch", lambda _arguments: {"ok": True})
    monkeypatch.setattr(cli, "canonical_json", lambda _payload: (_ for _ in ()).throw(TypeError("bad")))
    assert main(["status", "--campaign-dir", "missing"]) == 2
    output = capsys.readouterr().out
    assert output.strip() == '{"error":{"code":"CAMPAIGN_INTEGRITY_MISMATCH","message":"Campaign boundary failure"},"ok":false}'


def test_module_entrypoint_executes_without_traceback(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "argv", ["python -m tgn.campaign", "status", "--campaign-dir", str(tmp_path / "missing")])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with __import__("pytest").raises(SystemExit) as raised:
            runpy.run_module("tgn.campaign.__main__", run_name="__main__")
    assert raised.value.code == 2
    assert "Traceback" not in capsys.readouterr().out
