"""Conversation panel and REST/SSE client for talking with Momo's Agent."""

from __future__ import annotations

import json
import os
import threading
from math import ceil
from typing import Any

import requests
from PySide6.QtCore import QObject, QPoint, QRect, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QGuiApplication, QInputMethodEvent, QKeyEvent, QPainter, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ConversationClient(QObject):
    turn_started = Signal(str)
    answer_chunk = Signal(str)
    status_changed = Signal(str)
    a2a_transcript_ready = Signal(str, str)
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
                    elif event_type == "status":
                        self.status_changed.emit(str(data.get("text", "")))
                    elif event_type == "a2a_transcript":
                        self.a2a_transcript_ready.emit(
                            str(data.get("context_id", "")),
                            str(data.get("summary", "Discussion complete.")),
                        )
                    elif event_type == "completed":
                        self.completed.emit()
                    elif event_type == "error":
                        self.failed.emit(str(data.get("message", "Momo 暫時無法回覆。")))
                        return
                    event_type, data_lines = "message", []


class CollaborationClient(QObject):
    completed = Signal(dict)
    failed = Signal(str)
    confirmation_completed = Signal(dict)
    transcript_loaded = Signal(list)

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")

    def start(self, contact_name: str, content: str) -> None:
        threading.Thread(target=self._start, args=(contact_name, content), daemon=True).start()

    def _start(self, contact_name: str, content: str) -> None:
        try:
            response = requests.post(
                f"{self.base_url}/api/admin/delegations",
                json={"contactName": contact_name, "request": content}, timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            transcript_response = requests.get(
                f"{self.base_url}/api/collaborations/{result['context_id']}/transcript",
                timeout=10,
            )
            transcript_response.raise_for_status()
            result["transcript"] = transcript_response.json()
            self.completed.emit(result)
        except (KeyError, ValueError, requests.RequestException) as exc:
            self.failed.emit(str(exc))

    def confirm_task(self, task_id: str, confirmed: bool) -> None:
        threading.Thread(target=self._confirm_task, args=(task_id, confirmed), daemon=True).start()

    def load_transcript(self, context_id: str) -> None:
        threading.Thread(target=self._load_transcript, args=(context_id,), daemon=True).start()

    def _load_transcript(self, context_id: str) -> None:
        try:
            response = requests.get(
                f"{self.base_url}/api/collaborations/{context_id}/transcript", timeout=10
            )
            response.raise_for_status()
            self.transcript_loaded.emit(response.json())
        except (KeyError, ValueError, requests.RequestException) as exc:
            self.failed.emit(str(exc))

    def _confirm_task(self, task_id: str, confirmed: bool) -> None:
        try:
            response = requests.post(
                f"{self.base_url}/api/collaboration-tasks/{task_id}/confirmation",
                json={"confirmed": confirmed},
                timeout=10,
            )
            response.raise_for_status()
            self.confirmation_completed.emit(response.json())
        except (KeyError, ValueError, requests.RequestException) as exc:
            self.failed.emit(str(exc))


def is_local_agreement(content: str) -> bool:
    normalized = content.strip().casefold()
    return normalized in {"\u6211\u540c\u610f", "\u540c\u610f", "\u53ef\u4ee5", "\u597d", "yes", "agree"}


class ImeTextEdit(QTextEdit):
    """A growing multiline chat input that remains safe for Windows IMEs."""

    submit_requested = Signal()
    _MINIMUM_HEIGHT = 42
    _MAXIMUM_HEIGHT = 120

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_composing = False
        self._ime_cursor_visible = False
        self._ime_cursor_timer = QTimer(self)
        self._ime_cursor_timer.setInterval(500)
        self._ime_cursor_timer.timeout.connect(self._toggle_ime_cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptRichText(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.textChanged.connect(self._adjust_height)
        self._adjust_height()

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        super().inputMethodEvent(self._soft_composition_event(event))
        self._is_composing = bool(event.preeditString())
        self._sync_ime_cursor()

    def focusInEvent(self, event: object) -> None:
        super().focusInEvent(event)
        self._sync_ime_cursor()

    def focusOutEvent(self, event: object) -> None:
        super().focusOutEvent(event)
        self._sync_ime_cursor()

    def paintEvent(self, event: object) -> None:
        super().paintEvent(event)
        if not (self._is_composing and self._ime_cursor_visible and self.hasFocus()):
            return
        cursor = self.cursorRect()
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        cursor_x = cursor.left() + cursor.width() // 2
        painter.drawLine(cursor_x, cursor.top() + 1, cursor_x, cursor.bottom() - 1)

    def _sync_ime_cursor(self) -> None:
        should_show = self._is_composing and self.hasFocus()
        self._ime_cursor_visible = should_show
        if should_show:
            self._ime_cursor_timer.start()
        else:
            self._ime_cursor_timer.stop()
        self.update()

    def _toggle_ime_cursor(self) -> None:
        self._ime_cursor_visible = not self._ime_cursor_visible
        self.update()

    def _adjust_height(self) -> None:
        margins = self.contentsMargins()
        document = self.document()
        document.setTextWidth(self.viewport().width())
        content_height = ceil(document.documentLayout().documentSize().height())
        frame_and_margins = self.frameWidth() * 2 + margins.top() + margins.bottom()
        self.setFixedHeight(min(self._MAXIMUM_HEIGHT, max(self._MINIMUM_HEIGHT, content_height + frame_and_margins)))

    @staticmethod
    def _soft_composition_event(event: QInputMethodEvent) -> QInputMethodEvent:
        """Replace inverse IME highlighting with a cursor-friendly underline."""
        attributes: list[QInputMethodEvent.Attribute] = []
        for attribute in event.attributes():
            if attribute.type == QInputMethodEvent.AttributeType.Selection:
                continue
            if attribute.type == QInputMethodEvent.AttributeType.TextFormat:
                text_format = QTextCharFormat()
                text_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                attributes.append(
                    QInputMethodEvent.Attribute(
                        QInputMethodEvent.AttributeType.TextFormat,
                        attribute.start,
                        attribute.length,
                        text_format,
                    )
                )
                continue
            attributes.append(attribute)
        plain_event = QInputMethodEvent(event.preeditString(), attributes)
        plain_event.setCommitString(
            event.commitString(),
            event.replacementStart(),
            event.replacementLength(),
        )
        return plain_event

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._is_composing and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Enter confirms a 注音 candidate. Do not send while composing.
            QGuiApplication.inputMethod().commit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit_requested.emit()
                event.accept()
            return
        # Backspace/Delete remain Qt/Windows-IME owned.
        super().keyPressEvent(event)


class ChatPanel(QFrame):
    """A small, independently closable conversation window anchored beside Momo."""

    thinking_changed = Signal(bool)
    _ANCHOR_GAP = 14

    def __init__(
        self, base_url: str, parent: QWidget | None = None, display_name: str = "Momo"
    ) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.display_name = display_name
        self._last_message = ""
        self._has_answer_text = False
        self._thinking_frame = 0
        self._thinking_status = "正在準備回覆"
        self._thinking_frames = ("◜", "◠", "◝", "◞", "◡", "◟")
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(150)
        self._thinking_timer.timeout.connect(self._advance_thinking_indicator)
        self._client = ConversationClient(base_url)
        self._collaboration_client = CollaborationClient(base_url)
        self._build_ui()
        self._turn_origin = "user"
        self._client.turn_started.connect(self._turn_started)
        self._client.answer_chunk.connect(self._append_answer)
        self._client.status_changed.connect(self.show_agent_status)
        self._client.a2a_transcript_ready.connect(self._a2a_transcript_ready)
        self._client.completed.connect(self._completed)
        self._client.failed.connect(self._failed)
        self._collaboration_client.completed.connect(self._collaboration_completed)
        self._collaboration_client.failed.connect(self._collaboration_failed)
        self._collaboration_client.confirmation_completed.connect(self._confirmation_completed)
        self._collaboration_client.transcript_loaded.connect(self._raw_transcript_loaded)
        self._pending_confirmation_task_id: str | None = None

    def start_conversation(self) -> None:
        self._client.start()

    def closeEvent(self, event: object) -> None:
        self._client.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.setWindowTitle(f"和 {self.display_name} 聊天")
        self.setMinimumSize(340, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.collaboration_progress = QLabel()
        self.collaboration_progress.setObjectName("collaborationProgress")
        self.collaboration_progress.hide()
        self.peer_transcript = QTextEdit()
        self.peer_transcript.setObjectName("peerTranscript")
        self.peer_transcript.setReadOnly(True)
        self.peer_transcript.setMaximumHeight(220)
        self.peer_transcript.hide()
        self.peer_transcript_toggle = QPushButton("A2A 原始討論")
        self.peer_transcript_toggle.clicked.connect(self.toggle_peer_transcript)
        self.peer_transcript_toggle.hide()
        self.peer_transcript_close = QPushButton("關閉 A2A 討論")
        self.peer_transcript_close.clicked.connect(self.close_peer_transcript)
        self.peer_transcript_close.hide()
        self.a2a_controls = QWidget()
        a2a_controls = QHBoxLayout(self.a2a_controls)
        a2a_controls.setContentsMargins(0, 0, 0, 0)
        a2a_controls.addWidget(self.peer_transcript_toggle)
        a2a_controls.addWidget(self.peer_transcript_close)
        a2a_controls.addStretch()
        self.a2a_controls.hide()
        self.thinking_indicator = QLabel()
        self.thinking_indicator.setObjectName("thinkingIndicator")
        self.thinking_indicator.hide()
        self.transcript.setPlaceholderText(f"和 {self.display_name} 打個招呼吧！")
        self.input = ImeTextEdit()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("輸入訊息…")
        self.input.submit_requested.connect(self.send_message)
        self.send_button = QPushButton("送出")
        self.send_button.clicked.connect(self.send_message)
        self.retry_button = QPushButton("重試")
        self.retry_button.clicked.connect(self.retry)
        self.retry_button.hide()
        self.collaboration_button = QPushButton("Discuss")
        self.collaboration_button.clicked.connect(self.start_collaboration)
        self.collaboration_button.hide()
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
        layout.addWidget(self.collaboration_progress)
        layout.addWidget(self.a2a_controls)
        layout.addWidget(self.peer_transcript)
        layout.addLayout(controls)
        self.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 245); border: 2px solid #c9b6ff; border-radius: 16px; }"
            "QTextEdit { border: 1px solid #dfcdf7; border-radius: 8px; padding: 7px; }"
            "QTextEdit#chatInput { selection-background-color: #e6dcff; selection-color: #3d2866; }"
            "#thinkingIndicator { color: #6d4bb8; font-weight: 600; padding: 2px 4px; }"
            "#collaborationProgress { color: #35688c; font-weight: 600; padding: 2px 4px; }"
            "QPushButton { background: #f5eaff; border: 0; border-radius: 8px; padding: 7px 10px; color: #553b8d; }"
        )

    def show_collaboration_progress(self, text: str) -> None:
        """Show A2A status without adding background work to ordinary chat."""
        self.collaboration_progress.setText(text)
        self.collaboration_progress.show()

    def show_peer_transcript(self, messages: list[tuple[str, str]]) -> None:
        """Expose only actual A2A messages in a distinct read-only panel."""
        self.peer_transcript.setPlainText("\n\n".join(f"{speaker}: {text}" for speaker, text in messages))
        self.a2a_controls.show()
        self.peer_transcript_toggle.show()
        self.peer_transcript_close.show()
        self.peer_transcript.show()

    def load_peer_transcript(self, context_id: str) -> None:
        """Load a locally retained A2A transcript after an admin notification."""
        self._collaboration_client.load_transcript(context_id)

    def toggle_peer_transcript(self) -> None:
        self.peer_transcript.setVisible(not self.peer_transcript.isVisible())

    def close_peer_transcript(self) -> None:
        """Close the local A2A panel without deleting its retained transcript."""
        self.peer_transcript.clear()
        self.peer_transcript.hide()
        self.a2a_controls.hide()
        self.peer_transcript_toggle.hide()
        self.peer_transcript_close.hide()

    def _a2a_transcript_ready(self, context_id: str, summary: str) -> None:
        """Show the outbound A2A exchange outside the ordinary admin reply."""
        self.show_collaboration_progress(summary)
        if context_id:
            self.load_peer_transcript(context_id)

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
        content = self.input.toPlainText().strip()
        if not content:
            return
        if self._pending_confirmation_task_id and is_local_agreement(content):
            self.input.clear()
            self.transcript.append(f"You: {content}")
            self.show_collaboration_progress("Local confirmation recorded; waiting for the other admin.")
            self._collaboration_client.confirm_task(self._pending_confirmation_task_id, True)
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

    def start_collaboration(self, content: str | None = None) -> None:
        content = content or self.input.toPlainText().strip()
        contact_name = os.getenv("LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT", "").strip()
        if not content or not contact_name:
            self.show_collaboration_progress("Configure LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT to start a discussion.")
            return
        self.input.clear()
        self.transcript.append(f"You: {content}")
        self.show_collaboration_progress("Discussing with peer…")
        self._collaboration_client.start(contact_name, content)

    def _collaboration_completed(self, result: dict) -> None:
        summary = str(result.get("summary", "Discussion complete. Review the local admin summary."))
        self.show_collaboration_progress("Discussion complete.")
        self.transcript.append(f"Momo: {summary}")
        transcript = result.get("transcript", [])
        if isinstance(transcript, list):
            self._raw_transcript_loaded(transcript)
        task_id = result.get("task_id")
        if isinstance(task_id, str) and task_id:
            self._pending_confirmation_task_id = task_id

    def _collaboration_failed(self, detail: str) -> None:
        self.show_collaboration_progress(f"Discussion failed: {detail}")

    def _raw_transcript_loaded(self, transcript: list) -> None:
        messages = [
            (str(item.get("speaker", "Communicator")), str(item.get("text", "")))
            for item in transcript
            if isinstance(item, dict) and item.get("text")
        ]
        if messages:
            self.show_peer_transcript(messages)

    def confirm_local_proposal(self) -> None:
        if self._pending_confirmation_task_id is None:
            return
        self.confirmation_button.setEnabled(False)
        self.show_collaboration_progress("Local confirmation recorded; waiting for the other admin.")
        self._collaboration_client.confirm_task(self._pending_confirmation_task_id, True)

    def _confirmation_completed(self, task: dict) -> None:
        if task.get("status", {}).get("state") == "TASK_STATE_WORKING":
            self.show_collaboration_progress("Local confirmation recorded; waiting for the other admin.")
        else:
            self.show_collaboration_progress("Local confirmation could not be recorded.")

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
        self._thinking_status = "正在準備回覆"
        self._update_thinking_indicator()
        self.thinking_indicator.show()
        self._thinking_timer.start()

    def _stop_thinking_indicator(self) -> None:
        self._thinking_timer.stop()
        self.thinking_indicator.hide()

    def show_agent_status(self, status: str) -> None:
        """Update the visible, safe summary of the Agent's latest activity."""
        if not status:
            return
        self._thinking_status = status
        self._update_thinking_indicator()

    def _advance_thinking_indicator(self) -> None:
        self._thinking_frame = (self._thinking_frame + 1) % len(self._thinking_frames)
        self._update_thinking_indicator()

    def _update_thinking_indicator(self) -> None:
        frame = self._thinking_frames[self._thinking_frame]
        self.thinking_indicator.setText(f"Momo 正在思考中 {frame} … {self._thinking_status}")
