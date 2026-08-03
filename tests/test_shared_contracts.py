from __future__ import annotations

import math

import pytest

from tgn.hashing import canonical_json, sha256_json


def test_canonical_hash_ignores_mapping_insertion_order() -> None:
    left = {"世界": "霜港", "turn": 1}
    right = {"turn": 1, "世界": "霜港"}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_json(left) == sha256_json(right)


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_json({"bad": math.nan})

