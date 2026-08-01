from __future__ import annotations

from pathlib import Path

import pytest

from tgn.core.hashing import canonical_json
from tgn.session import SessionService

from tests.gameplay.phase75_helpers import make_phase75_state


@pytest.fixture
def phase75_initial_state_file(tmp_path: Path) -> Path:
    path = tmp_path / "initial-state.json"
    path.write_text(
        canonical_json(make_phase75_state().__dict__), encoding="utf-8"
    )
    return path


@pytest.fixture
def session_factory(tmp_path: Path, phase75_initial_state_file: Path):
    def create(*, name: str = "session-001", max_decisions: int = 50):
        session_dir = tmp_path / name
        result = SessionService.start(
            session_dir,
            session_id=name,
            actor_id="player",
            max_decisions=max_decisions,
            initial_state_path=phase75_initial_state_file,
        )
        return session_dir, result

    return create


def choice_for(request: dict, action_type: str) -> dict:
    return next(
        choice for choice in request["choices"] if choice["action_type"] == action_type
    )
