"""Resolve animation assets while keeping a static-portrait fallback."""

from __future__ import annotations

from pathlib import Path


class AvatarAssetCatalog:
    def __init__(self, asset_directory: Path) -> None:
        self.asset_directory = asset_directory

    def path_for(self, state: str) -> Path:
        animation = self.asset_directory / f"momo-{state}.gif"
        if animation.is_file():
            return animation
        return self.asset_directory / "momo-avatar.png"
