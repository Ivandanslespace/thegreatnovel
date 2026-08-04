from __future__ import annotations


class SourceDecodeError(ValueError):
    pass


def decode_source(data: bytes, encodings: list[str]) -> tuple[str, str]:
    if data.startswith(b"\xef\xbb\xbf") and "utf-8-sig" in encodings:
        return data.decode("utf-8-sig"), "utf-8-sig"

    failures: list[str] = []
    ordered = [encoding for encoding in encodings if encoding.lower() != "utf-8-sig"]
    for encoding in ordered:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            failures.append(f"{encoding}: byte {exc.start}")
    raise SourceDecodeError("无法解码源文件；尝试结果：" + "; ".join(failures))

