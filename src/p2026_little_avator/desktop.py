"""PySide6 desktop companion UI for the Little Avatar MVP."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests
from PySide6.QtCore import QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QMovie, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .avatar_assets import AvatarAssetCatalog
from .avatar_state import AnimationPlan, AvatarStateController
from .chat import ChatPanel

API_BASE_URL = os.environ.get("LITTLE_AVATAR_API_URL", "http://127.0.0.1:8765")
DISPLAY_NAME = os.environ.get("LITTLE_AVATAR_DISPLAY_NAME", "Momo")


class AvatarLabel(QLabel):
    clicked = Signal()
    menu_requested = Signal(QPoint)
    drag_started = Signal()
    dragged = Signal(QPoint)
    drag_released = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._press_pos: QPoint | None = None
        self._origin_pos: QPoint | None = None
        self._moved = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._origin_pos = self._press_pos
            self._moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is not None:
            current = event.globalPosition().toPoint()
            delta = current - self._press_pos
            if not self._moved and self._origin_pos is not None and (current - self._origin_pos).manhattanLength() > 4:
                self._moved = True
                self.drag_started.emit()
            if self._moved:
                self.dragged.emit(delta)
            self._press_pos = current
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press_pos is not None and not self._moved and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif self._moved and event.button() == Qt.MouseButton.LeftButton:
            self.drag_released.emit()
        self._press_pos = None
        self._origin_pos = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu_requested.emit(event.globalPos())
        event.accept()


class SseListener(QObject):
    event_received = Signal(object)
    connection_changed = Signal(str)

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self._stop = threading.Event()
        self._last_event_id: str | None = None
        self._thread = threading.Thread(target=self._run, name="little-avatar-sse", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        retry_seconds = 1
        while not self._stop.is_set():
            headers = {"Accept": "text/event-stream"}
            if self._last_event_id:
                headers["Last-Event-ID"] = self._last_event_id
            try:
                self.connection_changed.emit("已連線")
                with requests.get(f"{self.base_url}/api/events", headers=headers, stream=True, timeout=(3, 45)) as response:
                    response.raise_for_status()
                    retry_seconds = 1
                    event_type = "message"
                    data_lines: list[str] = []
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if self._stop.is_set():
                            return
                        line = raw_line or ""
                        if not line:
                            if data_lines:
                                self.event_received.emit({"type": event_type, "data": json.loads("\n".join(data_lines))})
                            event_type, data_lines = "message", []
                            continue
                        if line.startswith("id:"):
                            self._last_event_id = line[3:].strip()
                        elif line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].strip())
            except (requests.RequestException, json.JSONDecodeError):
                self.connection_changed.emit("離線模式")
                self._stop.wait(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 20)


class AvatarWindow(QWidget):
    local_message = Signal(str, str)

    def __init__(self, base_url: str = API_BASE_URL) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.base_url = base_url.rstrip("/")
        self.display_name = DISPLAY_NAME
        self._muted_until = 0.0
        self._bubble_visible = False
        self._state = AvatarStateController()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(self.display_name)
        self._build_ui()
        self._play_plan(self._state.current)
        self.chat_panel = ChatPanel(self.base_url, display_name=self.display_name)
        self.chat_panel.start_conversation()
        self.chat_panel.thinking_changed.connect(self._chat_thinking_changed)
        self.local_message.connect(self.set_message)
        self._listener = SseListener(self.base_url)
        self._listener.event_received.connect(self.handle_event)
        self._listener.connection_changed.connect(self._set_connection)
        self._listener.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self.bubble = QFrame()
        self.bubble.setObjectName("bubble")
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(14, 12, 14, 10)
        self.title = QLabel(self.display_name)
        self.title.setObjectName("bubbleTitle")
        self.message = QLabel("點我一下，有事找我嗎？")
        self.message.setWordWrap(True)
        self.connection = QLabel("連線中")
        self.connection.setObjectName("connection")
        buttons = QHBoxLayout()
        ask = QPushButton("給建議")
        tease = QPushButton("逗我")
        chat = QPushButton("聊天")
        mute = QPushButton("安靜 1 小時")
        ask.clicked.connect(lambda: self.send_action("ask_suggestion"))
        tease.clicked.connect(lambda: self.send_action("tease"))
        chat.clicked.connect(self.open_chat)
        mute.clicked.connect(self.mute_for_an_hour)
        buttons.addWidget(ask)
        buttons.addWidget(tease)
        buttons.addWidget(chat)
        bubble_layout.addWidget(self.title)
        bubble_layout.addWidget(self.message)
        bubble_layout.addWidget(self.connection)
        bubble_layout.addLayout(buttons)
        close_avatar = QPushButton("關閉 Momo")
        close_avatar.setObjectName("closeAvatar")
        close_avatar.clicked.connect(self.quit_avatar)
        bubble_layout.addWidget(close_avatar)
        layout.addWidget(self.bubble)

        self.avatar = AvatarLabel()
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._assets = AvatarAssetCatalog(Path(__file__).parent / "assets")
        self.avatar.setFixedHeight(270)
        self._opacity_effect = QGraphicsOpacityEffect(self.avatar)
        self._opacity_effect.setOpacity(1.0)
        self.avatar.setGraphicsEffect(self._opacity_effect)
        self.avatar.clicked.connect(self.open_chat)
        self.avatar.menu_requested.connect(self._show_avatar_menu)
        self.avatar.drag_started.connect(self._drag_started)
        self.avatar.dragged.connect(self._drag_by)
        self.avatar.drag_released.connect(self._drag_released)
        layout.addWidget(self.avatar)
        self.bubble.hide()
        self.setStyleSheet(
            "#bubble { background: rgba(255, 255, 255, 238); border: 2px solid #c9b6ff; border-radius: 16px; }"
            "#bubbleTitle { color: #6d4bb8; font-size: 15px; font-weight: 700; }"
            "#connection { color: #7a718c; font-size: 11px; }"
            "QPushButton { background: #f5eaff; border: 0; border-radius: 10px; padding: 6px 8px; color: #553b8d; }"
            "QPushButton:hover { background: #dfcdf7; }"
            "#closeAvatar { background: #fff0f4; color: #9e3f63; }"
            "#closeAvatar:hover { background: #ffdbe6; }"
        )

    def closeEvent(self, event: Any) -> None:
        self._listener.stop()
        self.chat_panel.close()
        super().closeEvent(event)

    def _drag_by(self, delta: QPoint) -> None:
        self.move(self.pos() + delta)
        self.chat_panel.follow_anchor(self.avatar)

    def _drag_started(self) -> None:
        self._play_plan(self._state.drag_started())

    def _drag_released(self) -> None:
        self._play_plan(self._state.drag_released())

    def _set_connection(self, status: str) -> None:
        self.connection.setText(status)

    def toggle_bubble(self) -> None:
        self._bubble_visible = not self._bubble_visible
        self.bubble.setVisible(self._bubble_visible)
        self._play_plan(self._state.play("greeting" if self._bubble_visible else "idle"))

    def open_chat(self) -> None:
        self.chat_panel.show_near(self.avatar)
        self._play_plan(self._state.play("greeting"))

    def _chat_thinking_changed(self, thinking: bool) -> None:
        self._play_plan(self._state.play("thinking" if thinking else "idle"))

    def _show_avatar_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        close = menu.addAction("關閉 Momo")
        selected = menu.exec(position)
        if selected == close:
            self.quit_avatar()

    def quit_avatar(self) -> None:
        """Close the desktop companion and stop its SSE listener."""
        self.close()
        application = QApplication.instance()
        if application is not None:
            application.quit()

    def set_message(self, title: str, text: str, show: bool = True) -> None:
        self.title.setText(title)
        self.message.setText(text)
        self._bubble_visible = show
        self.bubble.setVisible(show)

    def mute_for_an_hour(self) -> None:
        self._muted_until = time.time() + 3600
        self.set_message("Momo", "好啦，我一小時內不主動吵你。加油！")
        self._play_plan(self._state.play("sleeping"))
        self.send_action("mute", {"until": self._muted_until})

    def send_action(self, action: str, payload: dict[str, Any] | None = None) -> None:
        if action == "ask_suggestion":
            self.set_message("Momo", "讓我想一下～")
            self._play_plan(self._state.play("thinking"))
        elif action == "tease":
            self.set_message("Momo", "哎唷，妳很會喔？")
            self._play_plan(self._state.play("happy"))

        def post() -> None:
            try:
                requests.post(
                    f"{self.base_url}/api/interactions",
                    json={"action": action, "payload": payload or {}},
                    timeout=3,
                ).raise_for_status()
            except requests.RequestException:
                if action == "ask_suggestion":
                    self.local_message.emit("Momo", "後台現在不在線，但我還是在這裡陪妳。")

        threading.Thread(target=post, name="little-avatar-action", daemon=True).start()

    def handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        data = event.get("data", {})
        if event_type == "suggestion":
            if time.time() >= self._muted_until:
                plan = self._state.receive_suggestion(data)
                if plan.state != "drag":
                    self.set_message(str(data.get("title", "Momo")), str(data.get("text", "有個小提醒給妳。")))
                    self._play_plan(plan)
        elif event_type == "avatar_state":
            self._play_plan(self._state.play(str(data.get("state", "idle"))))
        elif event_type == "admin_notification":
            self.set_message(
                str(data.get("title", self.display_name)),
                str(data.get("text", "You have a local admin notification.")),
            )
            context_id = data.get("context_id")
            if isinstance(context_id, str) and context_id:
                self.chat_panel.load_peer_transcript(context_id)
            self._play_plan(self._state.play("happy"))

    def _play_plan(self, plan: AnimationPlan) -> None:
        """Play an animation plan, falling back to a still portrait when needed."""
        if plan.state == "sleeping":
            self._opacity_effect.setOpacity(0.78)
        else:
            self._opacity_effect.setOpacity(1.0)
        path = self._assets.path_for(plan.state)
        self._release_current_movie()
        if path.suffix.lower() != ".gif":
            pixmap = QPixmap(str(path))
            self.avatar.setPixmap(pixmap.scaledToHeight(250, Qt.TransformationMode.SmoothTransformation))
            return
        self._movie = QMovie(str(path))
        self._movie.setScaledSize(QSize(250, 250))
        self._movie.finished.connect(self._animation_finished)
        if not plan.loops:
            self._movie.frameChanged.connect(
                lambda frame_number, movie=self._movie: self._one_shot_frame_changed(movie, frame_number)
            )
        self.avatar.setMovie(self._movie)
        self._movie.start()

    def _one_shot_frame_changed(self, movie: QMovie, frame_number: int) -> None:
        """Finish a one-shot plan even when its GIF metadata loops forever."""
        if movie is not getattr(self, "_movie", None):
            return
        frame_count = movie.frameCount()
        if frame_count <= 0 or frame_number < frame_count - 1:
            return
        movie.stop()
        self._animation_finished()

    def _release_current_movie(self) -> None:
        """Detach and dispose the prior decoder before another avatar state starts."""
        movie = getattr(self, "_movie", None)
        if movie is None:
            return
        self.avatar.setMovie(None)
        movie.stop()
        movie.deleteLater()
        self._movie = None

    def _animation_finished(self) -> None:
        plan = self._state.animation_finished()
        if plan.state == "happy" and self._state.visible_suggestion is not None:
            suggestion = self._state.visible_suggestion
            self.set_message(str(suggestion.get("title", "Momo")), str(suggestion.get("text", "有個小提醒給妳。")))
        self._play_plan(plan)


def run() -> None:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(True)
    window = AvatarWindow()
    window.show()
    raise SystemExit(app.exec())
