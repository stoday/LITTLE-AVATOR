"""Explicit local Skill paths used by the fixed LITTLE_AVATOR roles."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class SkillRuntimeContext:
    data_directory: Path
    conversation_id: str | None = None
    turn_id: str | None = None


def momo_notes_skill_directory() -> Path:
    """Return the one Skill explicitly assigned to the configured roles."""
    return Path(__file__).resolve().parents[2] / "skills" / "momo-notes"


def load_momo_notes_runtime(context: SkillRuntimeContext) -> Any:
    """Load the explicitly assigned momo-notes public runtime."""
    root = momo_notes_skill_directory()
    runtime_file = root / "scripts" / "runtime.py"
    if not runtime_file.is_file():
        raise FileNotFoundError(f"momo-notes runtime is unavailable: {runtime_file}")
    package_name = "_little_avatar_momo_notes"
    package = sys.modules.get(package_name)
    if package is None:
        package = ModuleType(package_name)
        package.__path__ = [str(root)]  # type: ignore[attr-defined]
        sys.modules[package_name] = package
    scripts_name = f"{package_name}.scripts"
    if scripts_name not in sys.modules:
        scripts = ModuleType(scripts_name)
        scripts.__path__ = [str(root / "scripts")]  # type: ignore[attr-defined]
        sys.modules[scripts_name] = scripts
    runtime_name = f"{scripts_name}.runtime"
    module = sys.modules.get(runtime_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(runtime_name, runtime_file)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot import explicitly configured momo-notes runtime")
        module = importlib.util.module_from_spec(spec)
        sys.modules[runtime_name] = module
        spec.loader.exec_module(module)
    return module.create_runtime(context)
