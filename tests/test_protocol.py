from tgn.errors import TGNError, error_payload
from tgn.protocol import PROTOCOL_VERSION, hello_payload


def test_hello_declares_the_authoritative_protocol() -> None:
    payload = hello_payload()
    assert payload["protocol"] == PROTOCOL_VERSION
    assert payload["ok"] is True
    assert "deterministic_resolution" in payload["data"]["capabilities"]


def test_public_error_does_not_leak_exception_text() -> None:
    payload = error_payload(RuntimeError("secret path"))
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "secret path" not in str(payload)


def test_typed_error_preserves_recovery_contract() -> None:
    payload = error_payload(TGNError("STALE_PREVIEW", "预览已失效", recoverable=True))
    assert payload["error"]["recoverable"] is True

