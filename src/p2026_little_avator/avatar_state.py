"""Public animation-state seam for the desktop companion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnimationPlan:
    state: str
    loops: bool


class AvatarStateController:
    _LOOPING_STATES = frozenset({"idle"})

    def __init__(self) -> None:
        self.current = AnimationPlan("idle", loops=True)
        self.visible_suggestion: dict[str, Any] | None = None
        self._queued_suggestion: dict[str, Any] | None = None

    def play(self, state: str) -> AnimationPlan:
        self.current = AnimationPlan(state, loops=state in self._LOOPING_STATES)
        return self.current

    def animation_finished(self) -> AnimationPlan:
        if self.current.state == "drop" and self._queued_suggestion is not None:
            self.visible_suggestion = self._queued_suggestion
            self._queued_suggestion = None
            return self.play("happy")
        if not self.current.loops:
            self.current = AnimationPlan("idle", loops=True)
        return self.current

    def drag_started(self) -> AnimationPlan:
        return self.play("drag")

    def receive_suggestion(self, suggestion: dict[str, Any]) -> AnimationPlan:
        if self.current.state == "drag":
            self._queued_suggestion = suggestion
            return self.current
        self.visible_suggestion = suggestion
        return self.play("happy")

    def drag_released(self) -> AnimationPlan:
        return self.play("drop")
