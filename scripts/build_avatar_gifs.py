"""Build the MVP's lightweight transparent GIF set from the original Momo art."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance

ASSET_DIR = Path(__file__).parents[1] / "src" / "p2026_little_avator" / "assets"
SIZE = (512, 768)
FRAME_COUNT = 24
FRAME_DURATION_MS = 100


def offsets_for(state: str, index: int) -> tuple[int, int, float, float]:
    """Return x/y offset, rotation, and opacity for one key frame."""
    phase = index / FRAME_COUNT
    wave = [0, 1, 2, 3, 3, 2, 1, 0, -1, -2, -3, -3, -2, -1, 0, 1, 2, 3, 3, 2, 1, 0, -1, -2][index]
    if state == "idle":
        return (0, -abs(wave), 0.0, 1.0)
    if state == "greeting":
        return (wave * 2, -2, wave * 0.8, 1.0)
    if state == "drag":
        return (wave, -4, -4.0, 1.0)
    if state == "drop":
        bounce = -18 if index < 7 else (index - 7) * 2
        return (0, min(bounce, 12), 0.0, 1.0)
    if state == "thinking":
        return (wave, -4 - abs(wave), wave * 0.25, 1.0)
    if state == "happy":
        return (wave * 2, -abs(wave) * 3, wave * 0.45, 1.0)
    if state == "sleeping":
        return (0, abs(wave), 0.0, 0.72)
    raise ValueError(f"Unknown avatar state: {state}")


def build_gif(state: str, portrait: Image.Image) -> None:
    frames: list[Image.Image] = []
    for index in range(FRAME_COUNT):
        x_offset, y_offset, angle, opacity = offsets_for(state, index)
        frame = Image.new("RGBA", SIZE, (0, 0, 0, 0))
        character = portrait.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
        if opacity < 1:
            alpha = character.getchannel("A")
            alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
            character.putalpha(alpha)
        frame.alpha_composite(character, dest=(x_offset, y_offset))
        frames.append(frame)

    destination = ASSET_DIR / f"momo-{state}.gif"
    save_options = {
        "save_all": True,
        "append_images": frames[1:],
        "duration": FRAME_DURATION_MS,
        "disposal": 2,
        "transparency": 0,
        "optimize": True,
    }
    if state in {"idle", "drag"}:
        save_options["loop"] = 0
    frames[0].save(destination, **save_options)


def main() -> None:
    portrait = Image.open(ASSET_DIR / "momo-avatar.png").convert("RGBA").resize(SIZE, Image.Resampling.LANCZOS)
    for state in ("idle", "greeting", "drag", "drop", "thinking", "happy", "sleeping"):
        build_gif(state, portrait)


if __name__ == "__main__":
    main()
