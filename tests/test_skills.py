from pathlib import Path

import pytest

from p2026_little_avator.skills import (
    load_skill_runtime,
    skill_directories,
    skill_directory,
    skills_root,
)


def test_skill_directories_discovers_every_installed_skill() -> None:
    directories = [Path(path) for path in skill_directories()]

    assert [directory.name for directory in directories] == ["dtri-meeting-room", "momo-notes"]
    assert all((directory / "SKILL.md").is_file() for directory in directories)


def test_skill_directory_rejects_non_child_paths() -> None:
    with pytest.raises(ValueError, match="skill name"):
        skill_directory("../momo-notes")


def test_meeting_room_skill_defines_remaining_today_semantics() -> None:
    instructions = (skill_directory("dtri-meeting-room") / "SKILL.md").read_text(encoding="utf-8")

    assert "開始時間早於 runtime 當地時間的時段必須排除" in instructions
    assert "只保存過濾後仍可借的時段" in instructions


def test_skills_root_accepts_an_explicit_installation_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "installed-skills"
    root.mkdir()
    monkeypatch.setenv("LITTLE_AVATAR_SKILLS_DIR", str(root))

    assert skills_root() == root.resolve()


def test_momo_notes_runtime_uses_given_avatar_data_directory(tmp_path: Path) -> None:
    runtime = load_skill_runtime("momo-notes").create_runtime(data_directory=tmp_path)

    runtime.store.create_note("只由 momo-notes runtime 建立")

    assert "只由 momo-notes runtime 建立" in runtime.read_document()
