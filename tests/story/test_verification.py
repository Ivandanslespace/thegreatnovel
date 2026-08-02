from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tgn.story import StoryError, init_story
from tgn.story.common import canonical_bytes
from tgn.story.verification import load_story_view, story_files_unchanged
import tgn.story.verification as verification_module


def test_file_and_directory_observable_fallback_identity() -> None:
    fallback_stat = SimpleNamespace(st_dev=0, st_ino=0, st_file_attributes=7, st_ctime_ns=9, st_mode=10)
    assert verification_module._file_identity(fallback_stat) == ("fallback", 7, 9, 10)
    directory = verification_module.StoryDirectoryObservable(
        relative_path=".",
        mode=10,
        device=0,
        inode=0,
        file_attributes=7,
        ctime_ns=9,
        mtime_ns=11,
    )
    assert directory.identity == (10, 7, 9)


def test_story_view_not_found_root_type_and_extra_tree(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_NOT_FOUND"
    file_root = tmp_path / "file-root"
    file_root.write_text("not a directory", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        load_story_view(file_root)
    assert error.value.code == "INVALID_STORY_INPUT"

    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    extra = story / "extra"
    extra.write_text("extra", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    extra.unlink()

    novel = story / "novel.md"
    novel.write_text("future", encoding="utf-8")
    view = load_story_view(story)
    assert view.novel is not None
    assert view.novel_bytes == b"future"
    novel.unlink()


def test_story_view_canonical_schema_and_special_directory_boundaries(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    manifest = story / "story.json"
    manifest.write_text('{ "schema_version": 1 }', encoding="utf-8")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    manifest.unlink()
    manifest.write_bytes(canonical_bytes({"bad": True}))
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    manifest.unlink()
    # Restore a valid immutable root through a fresh Story directory rather
    # than writing a second manifest by hand.
    shutil.rmtree(story)
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    requests = story / "requests"
    requests.rename(story / "requests-real")
    try:
        requests.symlink_to(story / "requests-real", target_is_directory=True)
    except (OSError, NotImplementedError):
        shutil.rmtree(story / "requests-real")
        pytest.skip("directory symlink creation unavailable on this platform")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_story_view_artifact_filename_and_read_only_observable(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    view = load_story_view(story)
    assert story_files_unchanged(story, view.files) is True
    invalid = story / "requests" / "not-a-turn.json"
    invalid.write_bytes(b"{}")
    assert story_files_unchanged(story, view.files) is False
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_story_view_read_and_filename_failure_paths(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose = __import__("tests.story.test_service", fromlist=["_choose"])._choose
    _choose(campaign, "DROP")
    request = __import__("tgn.story", fromlist=["prepare_story"]).prepare_story(story, campaign_dir=campaign)["request"]
    request_path = story / "requests" / "turn-000001.json"

    invalid_json = story / "requests" / "turn-0000010.json"
    invalid_json.write_bytes(b"{}")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    invalid_json.unlink()

    request_path.write_bytes(canonical_bytes({"bad": True}))
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    request_path.write_bytes(canonical_bytes(request))

    request_path.rename(story / "requests" / "turn-000002.json")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    (story / "requests" / "turn-000002.json").rename(request_path)

    original_children = verification_module.list_actual_children
    def failing_children(path):
        if Path(path).name == "requests":
            raise OSError("directory race")
        return original_children(path)
    monkeypatch.setattr(verification_module, "list_actual_children", failing_children)
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_story_view_root_and_directory_errors(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    original_lstat = verification_module.os.lstat
    monkeypatch.setattr(verification_module.os, "lstat", lambda *_args: (_ for _ in ()).throw(OSError("inspect")))
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "INVALID_STORY_INPUT"
    monkeypatch.setattr(verification_module.os, "lstat", original_lstat)

    turns = story / "turns"
    turns.rmdir()
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_story_view_duplicate_and_low_level_read_errors(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    with pytest.raises(StoryError):
        verification_module._read_turn_file(story / "requests", "not-a-turn.json")
    with pytest.raises(StoryError):
        verification_module._read_turn_file(story / "requests", "turn-0000010.json")
    monkeypatch.setattr(verification_module, "read_regular_file", lambda *_args: (_ for _ in ()).throw(StoryError("STORY_INTEGRITY_MISMATCH", "read")))
    with pytest.raises(StoryError):
        verification_module._read_turn_file(story / "requests", "turn-000001.json")

    # Recreate a clean Story and make one artifact directory a regular file.
    import shutil
    shutil.rmtree(story)
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    shutil.rmtree(story / "requests")
    (story / "requests").write_text("not a directory", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        load_story_view(story)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
