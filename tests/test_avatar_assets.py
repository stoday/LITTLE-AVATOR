from pathlib import Path

from PIL import Image

from p2026_little_avator.avatar_assets import AvatarAssetCatalog


def test_missing_state_animation_falls_back_to_static_portrait(tmp_path: Path) -> None:
    portrait = tmp_path / "momo-avatar.png"
    portrait.write_bytes(b"portrait")
    catalog = AvatarAssetCatalog(tmp_path)

    assert catalog.path_for("happy") == portrait


def test_bundled_state_gifs_are_decodable_while_actions_are_placeholders() -> None:
    asset_directory = Path(__file__).parents[1] / "src" / "p2026_little_avator" / "assets"

    for state in ("idle", "greeting", "drag", "drop", "thinking", "happy", "sleeping"):
        animation = Image.open(asset_directory / f"momo-{state}.gif")
        assert animation.n_frames > 0
        assert animation.size[0] > 0
        assert animation.size[1] > 0
