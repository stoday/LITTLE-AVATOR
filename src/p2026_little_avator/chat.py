"""Conversation panel and REST/SSE client for talking with Momo's Agent."""

from __future__ import annotations

import json
import threading
from typing import Any

import requests
from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ConversationClient(QObject):
    turn_started = Signal(str)
    answer_chunk = Signal(str)
    completed = Signal()
    failed = Signal(str)

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.conversation_id: str | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._listener: threading.Thread | None = None

    def start(self) -> None:
        """Create one session and keep its event stream open while Momo runs."""
        if self._listener is None:
            self._listener = threading.Thread(target=self._connect_and_consume, name="momo-conversation-sse", daemon=True)
            self._listener.start()

    def stop(self) -> None:
        self._stop.set()

    def send(self, content: str) -> None:
        threading.Thread(target=self._send, args=(content,), name="momo-chat", daemon=True).start()

    def _send(self, content: str) -> None:
        try:
            self.start()
            if not self._ready.wait(5) or self.conversation_id is None:
                raise requests.RequestException("conversation is not ready")
            response = requests.post(
                f"{self.base_url}/api/conversations/{self.conversation_id}/messages",
                json={"content": content},
                timeout=10,
            )
            response.raise_for_status()
        except (KeyError, ValueError, requests.RequestException):
            self.failed.emit("Momo 現在連不上大腦，請稍後再試一次。")

    def _connect_and_consume(self) -> None:
        try:
            response = requests.post(f"{self.base_url}/api/conversations", timeout=5)
            response.raise_for_status()
            self.conversation_id = str(response.json()["conversation_id"])
            self._ready.set()
            self._consume_events()
        except (KeyError, ValueError, requests.RequestException):
            self._ready.set()
            self.failed.emit("Momo 現在連不上大腦，請稍後再試一次。")

    def _consume_events(self) -> None:
        assert self.conversation_id is not None
        event_type = "message"
        data_lines: list[str] = []
        with requests.get(
            f"{self.base_url}/api/conversations/{self.conversation_id}/events",
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=(5, 120),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if self._stop.is_set():
                    return
                line = raw_line or ""
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif not line and data_lines:
                    data = json.loads("\n".join(data_lines))
                    if event_type == "turn_started":
                        self.turn_started.emit(str(data.get("origin", "user")))
                    elif event_type == "answer":
                        self.answer_chunk.emit(str(data.get("text", "")))
                    elif event_type == "completed":
                        self.completed.emit()
                    elif event_type == "error":
                        self.failed.emit(str(data.get("message", "Momo 暫時無法回覆。")))
                        return
                    event_type, data_lines = "message", []


class ChatPanel(QFrame):
    """A small, independently closable conversation window anchored beside Momo."""

    thinking_changed = Signal(bool)
    _ANCHOR_GAP = 14

    def __init__(self, base_url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self._last_message = ""
        self._has_answer_text = False
        self._thinking_frame = 0
        self._thinking_frames = ("◜", "◠", "◝", "◞", "◡", "◟")
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(150)
        self._thinking_timer.timeout.connect(self._advance_thinking_indicator)
        self._client = ConversationClient(base_url)
        self._build_ui()
        self._turn_origin = "user"
        self._client.turn_started.connect(self._turn_started)
        self._client.answer_chunk.connect(self._append_answer)
        self._client.completed.connect(self._completed)
        self._client.failed.connect(self._failed)

    def start_conversation(self) -> None:
        self._client.start()

    def closeEvent(self, event: object) -> None:
        self._client.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.setWindowTitle("和 Momo 聊天")
        self.setMinimumSize(340, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.thinking_indicator = QLabel()
        self.thinking_indicator.setObjectName("thinkingIndicator")
        self.thinking_indicator.hide()
        self.transcript.setPlaceholderText("和 Momo 打個招呼吧！")
        self.input = QLineEdit()
        self.input.setPlaceholderText("輸入訊息…")
        self.input.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("送出")
        self.send_button.clicked.connect(self.send_message)
        self.retry_button = QPushButton("重試")
        self.retry_button.clicked.connect(self.retry)
        self.retry_button.hide()
        close_button = QPushButton("×")
        close_button.setToolTip("關閉對話")
        close_button.clicked.connect(self.hide)
        controls = QHBoxLayout()
        controls.addWidget(self.input)
        controls.addWidget(self.send_button)
        controls.addWidget(self.retry_button)
        controls.addWidget(close_button)
        layout.addWidget(self.transcript)
        layout.addWidget(self.thinking_indicator)
        layout.addLayout(controls)
        self.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 245); border: 2px solid #c9b6ff; border-radius: 16px; }"
            "QTextEdit, QLineEdit { border: 1px solid #dfcdf7; border-radius: 8px; padding: 7px; }"
            "QLineEdit { selection-background-color: #e6dcff; selection-color: #3d2866; }"
            "#thinkingIndicator { color: #6d4bb8; font-weight: 600; padding: 2px 4px; }"
            "QPushButton { background: #f5eaff; border: 0; border-radius: 8px; padding: 7px 10px; color: #553b8d; }"
        )

    def show_near(self, anchor: QWidget) -> None:
        self.adjustSize()
        self.move(self._position_near(anchor))
        self.show()
        self.raise_()
        self.input.setFocus()

    def follow_anchor(self, anchor: QWidget) -> None:
        """Keep an already visible conversation panel attached to Momo."""
        if self.isVisible():
            self.move(self._position_near(anchor))

    def _position_near(self, anchor: QWidget) -> QPoint:
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        anchor_center = anchor_rect.center()
        screen = QGuiApplication.screenAt(anchor_center) or QGuiApplication.primaryScreen()
        if screen is None:
            return anchor_top_left

        available = screen.availableGeometry()
        panel_size = QSize(self.width(), self.height())
        candidates = (
            QPoint(anchor_center.x() - panel_size.width() // 2, anchor_rect.top() - self._ANCHOR_GAP - panel_size.height()),
            QPoint(anchor_rect.left() - self._ANCHOR_GAP - panel_size.width(), anchor_center.y() - panel_size.height() // 2),
            QPoint(anchor_rect.right() + self._ANCHOR_GAP + 1, anchor_center.y() - panel_size.height() // 2),
            QPoint(anchor_center.x() - panel_size.width() // 2, anchor_rect.bottom() + self._ANCHOR_GAP + 1),
        )
        for position in candidates:
            if available.contains(QRect(position, panel_size)):
                return position

        preferred = candidates[0]
        maximum_x = max(available.left(), available.right() - panel_size.width() + 1)
        maximum_y = max(available.top(), available.bottom() - panel_size.height() + 1)
        return QPoint(
            min(max(preferred.x(), available.left()), maximum_x),
            min(max(preferred.y(), available.top()), maximum_y),
        )

    def send_message(self) -> None:
        content = self.input.text().strip()
        if not content:
            return
        self._last_message = content
        self.input.clear()
        self.transcript.append(f"你：{content}")
        self._set_busy(True)
        self._client.send(content)

    def _turn_started(self, origin: str) -> None:
        self._turn_origin = origin
        self._has_answer_text = False
        if origin == "user":
            self._set_busy(True)

    def retry(self) -> None:
        if self._last_message:
            self._set_busy(True)
            self._client.send(self._last_message)

    def _append_answer(self, text: str) -> None:
        if not text:
            return
        if not self._has_answer_text:
            self._has_answer_text = True
            self._stop_thinking_indicator()
            self.transcript.append("Momo（提醒）：" if self._turn_origin == "reminder" else "Momo：")
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.transcript.setTextCursor(cursor)

    def _completed(self) -> None:
        if not self._has_answer_text:
            self.transcript.append("Momo: No reply received. Please try again.")
        self.transcript.append("")
        self._set_busy(False)
        self.input.setFocus()

    def _failed(self, message: str) -> None:
        self.transcript.append(f"\nMomo：{message}")
        self.retry_button.show()
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        if busy:
            self._has_answer_text = False
            self._start_thinking_indicator()
            self.retry_button.hide()
        else:
            self._stop_thinking_indicator()
        self.thinking_changed.emit(busy)

    def _start_thinking_indicator(self) -> None:
        self._thinking_frame = 0
        self._update_thinking_indicator()
        self.thinking_indicator.show()
        self._thinking_timer.start()

    def _stop_thinking_indicator(self) -> None:
        self._thinking_timer.stop()
        self.thinking_indicator.hide()

    def _advance_thinking_indicator(self) -> None:
        self._thinking_frame = (self._thinking_frame + 1) % len(self._thinking_frames)
        self._update_thinking_indicator()

    def _update_thinking_indicator(self) -> None:
        frame = self._thinking_frames[self._thinking_frame]
        self.thinking_indicator.setText(f"Momo 正在思考中 {frame}")
