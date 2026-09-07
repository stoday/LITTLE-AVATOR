from pathlib import Path

from p2026_little_avator.skill_host import (
    SkillRuntimeContext,
    load_momo_notes_runtime,
    momo_notes_skill_directory,
)


def test_momo_notes_is_the_one_explicitly_configured_skill() -> None:
    skill_directory = momo_notes_skill_directory()

    assert skill_directory.name == "momo-notes"
    assert (skill_directory / "SKILL.md").is_file()
    instructions = (skill_directory / "SKILL.md").read_text(encoding="utf-8")
    assert "不得用\n`read_skill_resource` 讀取 `schedule.md`" in instructions
    assert "它是本機 Avatar 資料" in instructions
    assert "`python_execute` 執行 `scripts/note_cli.py`" in instructions


def test_explicit_momo_notes_runtime_uses_given_avatar_data_directory(tmp_path: Path) -> None:
    runtime = load_momo_notes_runtime(SkillRuntimeContext(data_directory=tmp_path))

    runtime.store.create_note("只由明確設定的 momo-notes 建立")

    assert "只由明確設定的 momo-notes 建立" in runtime.read_document()
