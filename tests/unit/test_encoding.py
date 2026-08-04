from __future__ import annotations

import pytest

from novel_authoring.ingest.encoding import SourceDecodeError, decode_source

ENCODINGS = ["utf-8", "utf-8-sig", "gb18030"]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("中文路径".encode(), "utf-8"),
        (b"\xef\xbb\xbf" + "带签名".encode(), "utf-8-sig"),
        ("简体中文编码".encode("gb18030"), "gb18030"),
    ],
)
def test_decode_supported_encodings(payload: bytes, expected: str) -> None:
    text, encoding = decode_source(payload, ENCODINGS)
    assert text
    assert encoding == expected


def test_decode_failure_does_not_mutate_payload() -> None:
    payload = b"\xff\xfe\x00\x81"
    before = bytes(payload)
    with pytest.raises(SourceDecodeError):
        decode_source(payload, ["utf-8"])
    assert payload == before

