"""天赋与装备使用的统一字母评级。"""

from __future__ import annotations

from typing import Any


# 从低到高，便于计算“评级提升/降低若干档”。
RATING_SCALE = ("G", "F", "E", "D", "C", "B", "A", "S", "SS", "SSS")
RATING_INDEX = {rating: index for index, rating in enumerate(RATING_SCALE)}


def normalize_rating(value: Any, default: str = "G") -> str:
    """把评级规范化为统一字母；非法或空值使用指定默认评级。"""
    candidate = str(value or "").strip().upper()
    if candidate in RATING_INDEX:
        return candidate
    fallback = str(default or "G").strip().upper()
    return fallback if fallback in RATING_INDEX else "G"


def shift_rating(value: Any, steps: int) -> str:
    """按档位升降评级，并在 G/SSS 两端封顶。"""
    current = RATING_INDEX[normalize_rating(value)]
    target = max(0, min(len(RATING_SCALE) - 1, current + int(steps)))
    return RATING_SCALE[target]
