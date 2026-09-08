"""Discovery and runtime loading for developer-installed Skills."""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType


_SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skills_root() -> Path:
    """Return the root containing Skills packaged with LITTLE_AVATOR."""
    configured = os.getenv("LITTLE_AVATAR_SKILLS_DIR", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(__file__).resolve().parents[2] / "skills",
        Path(sys.prefix) / "skills",
        Path(sys.prefix),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            return candidate.resolve()
    raise FileNotFoundError("LITTLE_AVATOR skills root is unavailable")


def skill_directory(name: str) -> Path:
    """Resolve one direct child Skill without allowing path traversal."""
    if not _SKILL_NAME_PATTERN.fullmatch(name):
        raise ValueError("skill name must use lowercase letters, numbers, and hyphens")
    directory = skills_root() / name
    if not directory.is_dir() or not (directory / "SKILL.md").is_file():
        raise FileNotFoundError(f"skill is unavailable: {name}")
    return directory


def skill_directories() -> list[str]:
    """Return every developer-installed Skill directory packaged with this app."""
    root = skills_root()
    return [
        str(candidate)
        for candidate in sorted(root.iterdir(), key=lambda path: path.name)
        if candidate.is_dir() and (candidate / "SKILL.md").is_file()
    ]


@lru_cache(maxsize=None)
def load_skill_runtime(skill_name: str) -> ModuleType:
    """Load a Skill's optional scripts/runtime.py module."""
    root = skill_directory(skill_name)
    scripts_root = root / "scripts"
    runtime_file = scripts_root / "runtime.py"
    if not runtime_file.is_file():
        raise FileNotFoundError(f"skill runtime is unavailable: {runtime_file}")

    package_name = f"_little_avatar_skill_{skill_name.replace('-', '_')}"
    _ensure_package(package_name, root)
    scripts_name = f"{package_name}.scripts"
    _ensure_package(scripts_name, scripts_root)

    runtime_name = f"{scripts_name}.runtime"
    module = sys.modules.get(runtime_name)
    if module is not None:
        return module

    spec = importlib.util.spec_from_file_location(runtime_name, runtime_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import runtime for skill: {skill_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[runtime_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package(name: str, directory: Path) -> None:
    if name in sys.modules:
        return
    package = ModuleType(name)
    package.__path__ = [str(directory)]  # type: ignore[attr-defined]
    sys.modules[name] = package
