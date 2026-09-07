"""Regression tests for keeping Momo's chat panel anchored to the avatar."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QInputMethodEvent, QKeyEvent, QTextCharFormat
from PySide6.QtWidgets import QApplication, QWidget

import p2026_little_avator.desktop as desktop
from p2026_little_avator.chat import ChatPanel, ImeTextEdit
from p2026_little_avator.desktop import AvatarWindow, NegotiationResultDialog


def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_chat_panel_prefers_space_above_the_avatar() -> None:
    app = application()
    panel = ChatPanel("http://127.0.0.1:8765")
    screen = app.primaryScreen().availableGeometry()
    anchor = QWidget()
    anchor.resize(160, 220)
    anchor.move(screen.center().x() - anchor.width() // 2, screen.top() + panel.minimumHeight() + 20)
    anchor.show()
    app.processEvents()

    panel.show_near(anchor)
    app.processEvents()

    anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
    assert panel.geometry().bottom() < anchor_top_left.y()
    assert abs(panel.geometry().center().x() - anchor.geometry().center().x()) <= 1

    panel.close()
    anchor.close()


def test_chat_panel_uses_the_configured_avatar_display_name() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765", display_name="Momo A（邀約者）")

    assert "Momo A（邀約者）" in panel.windowTitle()
    panel.close()


def test_visible_chat_panel_repositions_when_anchor_moves() -> None:
    app = application()
    panel = ChatPanel("http://127.0.0.1:8765")
    screen = app.primaryScreen().availableGeometry()
    anchor = QWidget()
    anchor.resize(160, 220)
    anchor.move(screen.center().x() - anchor.width() // 2, screen.top() + panel.minimumHeight() + 20)
    anchor.show()
    panel.show_near(anchor)
    app.processEvents()
    original_position = panel.pos()

    anchor.move(anchor.pos() + QPoint(35, 18))
    panel.follow_anchor(anchor)

    assert panel.pos() == original_position + QPoint(35, 18)

    panel.close()
    anchor.close()


def test_avatar_drag_asks_visible_chat_panel_to_follow() -> None:
    class PanelStub:
        def __init__(self) -> None:
            self.anchor: object | None = None

        def follow_anchor(self, anchor: object) -> None:
            self.anchor = anchor

    class WindowStub:
        def __init__(self) -> None:
            self._position = QPoint(10, 20)
            self.avatar = object()
            self.chat_panel = PanelStub()

        def pos(self) -> QPoint:
            return self._position

        def move(self, position: QPoint) -> None:
            self._position = position

    window = WindowStub()

    AvatarWindow._drag_by(window, QPoint(35, 18))

    assert window.pos() == QPoint(45, 38)
    assert window.chat_panel.anchor is window.avatar


def test_chat_panel_shows_a_moving_thinking_indicator_until_the_first_answer() -> None:
    app = application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel._client.send = lambda _: None
    panel.show()
    app.processEvents()

    panel.input.setPlainText("test message")
    panel.send_message()

    assert panel.thinking_indicator.isVisible()
    assert panel._thinking_timer.isActive()
    assert "Momo：" not in panel.transcript.toPlainText()
    first_frame = panel.thinking_indicator.text()
    panel._advance_thinking_indicator()
    assert panel.thinking_indicator.text() != first_frame

    panel.show_agent_status("正在使用已授權工具")
    assert "Momo 正在思考中" in panel.thinking_indicator.text()
    assert "正在使用已授權工具" in panel.thinking_indicator.text()

    panel._append_answer("first answer")

    assert not panel.thinking_indicator.isVisible()
    assert not panel._thinking_timer.isActive()
    assert "Momo：" in panel.transcript.toPlainText()
    assert "first answer" in panel.transcript.toPlainText()

    panel._completed()
    assert panel.input.isEnabled()
    assert panel.input.hasFocus()
    panel.close()


def test_collaboration_completion_keeps_raw_transcript_out_of_ordinary_chat() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel.show()

    panel._a2a_transcript_ready("context-1", "A private summary")

    assert not panel.collaboration_progress.isHidden()
    assert panel.collaboration_progress.text() == "協商已完成，請查看協商結果視窗。"
    assert "A private summary" not in panel.transcript.toPlainText()
    assert not hasattr(panel, "peer_transcript")
    panel.close()


def test_terminal_report_only_finishes_the_matching_background_delegation() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel._set_busy(True)
    panel._delegation_started("context-current")

    panel.append_admin_report("另一筆協商完成。", "context-other")
    assert not panel.input.isEnabled()
    assert panel._thinking_timer.isActive()

    panel.append_admin_report("這一筆協商完成。", "context-current")
    assert panel.input.isEnabled()
    assert not panel._thinking_timer.isActive()
    assert panel._active_delegation_context_id is None
    panel.close()


def test_terminal_report_clears_a_stale_indicator_after_the_initial_delegation_reply() -> None:
    """A dropped delegation-started event must not leave an already-answered turn busy."""
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel._set_busy(True)
    panel._append_answer("我已開始協商，完成後會回覆你。")
    panel._start_thinking_indicator()

    panel.append_admin_report("協商已完成，請確認暫定結果。", "context-finished")

    assert panel.input.isEnabled()
    assert not panel.thinking_indicator.isVisible()
    assert not panel._thinking_timer.isActive()
    panel.close()


def test_new_user_turn_cannot_be_finished_by_an_older_background_delegation() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel._delegation_started("context-old")
    panel._set_busy(True)

    panel._turn_started("user")
    panel.append_admin_report("舊協商完成。", "context-old")

    assert panel._active_delegation_context_id is None
    assert not panel.input.isEnabled()
    assert panel._thinking_timer.isActive()
    panel.close()


def test_legacy_collaboration_entry_sends_intent_to_momo_without_a_default_peer(monkeypatch) -> None:
    application()
    monkeypatch.delenv("LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT", raising=False)
    panel = ChatPanel("http://127.0.0.1:8765")
    sent: list[str] = []
    monkeypatch.setattr(panel._client, "send", sent.append)
    panel.input.setPlainText("Discuss this")

    panel.start_collaboration()

    assert sent == ["Discuss this"]
    assert "Discuss this" in panel.transcript.toPlainText()
    panel.close()


def test_dinner_invitation_typed_to_admin_is_delegated_without_polluting_regular_chat(
    monkeypatch,
) -> None:
    application()
    monkeypatch.setenv("LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT", "XXX")
    panel = ChatPanel("http://127.0.0.1:8765")
    delegated: list[tuple[str, str]] = []
    monkeypatch.setattr(
        panel._collaboration_client,
        "start",
        lambda contact, request: delegated.append((contact, request)),
    )
    regular_messages: list[str] = []
    monkeypatch.setattr(panel._client, "send", regular_messages.append)
    panel.input.setPlainText("幫我跟 XXX 說，我想約她吃晚餐，問她有沒有空和想吃什麼？")

    panel.send_message()

    assert delegated == []
    assert regular_messages
    assert "幫我跟 XXX 說" in panel.transcript.toPlainText()
    assert "agent-b-communicator" not in panel.transcript.toPlainText()
    panel.close()


def test_normal_chat_does_not_expose_communicator_transcript_after_completion() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")

    panel._collaboration_completed({"peer_agent_id": "agent-b", "reply": "internal peer reply"})

    assert "internal peer reply" not in panel.transcript.toPlainText()
    assert panel.transcript.toPlainText() == ""
    assert panel.collaboration_progress.text() == "協商已完成，請查看協商結果視窗。"
    panel.close()


def test_negotiation_result_dialog_shows_conclusion_and_only_a_close_button() -> None:
    application()
    dialog = NegotiationResultDialog("http://127.0.0.1:8765")
    dialog._load_transcript = lambda _: None

    dialog.show_result("雙方暫定週三晚上七點。", "context-1")
    dialog._show_transcript(
        "context-1",
        [
            {"speaker": "小王的 communicator", "text": "請問週三晚上可以嗎？"},
            {"speaker": "小美的 communicator", "text": "可以，週三晚上七點。"},
        ],
    )

    assert dialog.summary.text() == "雙方暫定週三晚上七點。"
    assert "小王的 communicator" in dialog.transcript.toPlainText()
    assert "小美的 communicator" in dialog.transcript.toPlainText()
    assert [button.text() for button in dialog.findChildren(desktop.QPushButton)] == ["關閉"]
    dialog.close()


def test_negotiation_result_dialog_uses_secretary_names_from_transcript_envelope() -> None:
    application()
    dialog = NegotiationResultDialog("http://127.0.0.1:8765")
    dialog._context_id = "context-identity"

    dialog._show_transcript(
        "context-identity",
        {
            "local_communicator_name": "小王的秘書",
            "peer_communicator_name": "小美的秘書",
            "entries": [
                {"role": "local", "speaker": "小王的秘書", "text": "您好。"},
                {"role": "peer", "speaker": "小美的秘書", "text": "您好。"},
            ],
        },
    )

    transcript_title = dialog.findChild(desktop.QLabel, "negotiationTranscriptTitle")
    assert transcript_title.text() == "小王的秘書 與 小美的秘書 的對話紀錄"
    assert "小王的秘書: 您好。" in dialog.transcript.toPlainText()
    assert "小美的秘書: 您好。" in dialog.transcript.toPlainText()
    assert "agent-x-communicator" not in dialog.transcript.toPlainText()
    dialog.close()


def test_admin_notification_opens_a_result_window_and_adds_the_local_report_to_chat() -> None:
    class ResultDialogStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def show_result(self, summary: str, context_id: str) -> None:
            self.calls.append((summary, context_id))

    result_dialog = ResultDialogStub()
    reports: list[str] = []
    window = type("WindowStub", (), {})()
    window.negotiation_result_dialog = result_dialog
    window.chat_panel = type("ChatPanelStub", (), {"append_admin_report": lambda _, text, context_id: reports.append((text, context_id))})()
    window._state = type("StateStub", (), {"play": lambda _, state: state})()
    window._play_plan = lambda plan: setattr(window, "played_plan", plan)
    window.set_message = lambda *_: (_ for _ in ()).throw(AssertionError("bubble must not be updated"))

    AvatarWindow.handle_event(
        window,
        {"type": "admin_notification", "data": {"text": "協商已完成。", "context_id": "context-1"}},
    )

    assert result_dialog.calls == [("協商已完成。", "context-1")]
    assert reports == [("協商已完成。", "context-1")]
    assert window.played_plan == "happy"


def test_tentative_proposal_accepts_a_natural_language_local_confirmation(monkeypatch) -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel._collaboration_completed(
        {
                "summary": "XXX 的 communicator 已完成討論。",
            "task_id": "local-task",
        }
    )

    sent: list[str] = []
    monkeypatch.setattr(panel._client, "send", sent.append)
    panel.input.setPlainText("我同意")
    panel.send_message()

    assert panel.collaboration_button.isHidden()
    assert sent
    assert "local-task" not in panel.transcript.toPlainText()
    panel.close()


def test_chat_input_uses_gentle_selection_colours() -> None:
    panel = ChatPanel("http://127.0.0.1:8765")

    assert "QTextEdit#chatInput { selection-background-color: #e6dcff" in panel.styleSheet()
    assert "selection-color: #3d2866" in panel.styleSheet()

    panel.close()


def test_chat_input_does_not_send_while_an_ime_candidate_is_being_confirmed() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    sent: list[str] = []
    panel._client.send = sent.append
    panel.input.setPlainText("draft")
    panel.input._is_composing = True

    QApplication.sendEvent(
        panel.input,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
    )

    assert sent == []
    assert panel.input.isEnabled()
    panel.close()


def test_chat_input_softens_ime_selection_format_but_keeps_the_cursor() -> None:
    inverted_format = QTextCharFormat()
    event = QInputMethodEvent(
        "ㄓ",
        [
            QInputMethodEvent.Attribute(
                QInputMethodEvent.AttributeType.TextFormat,
                0,
                1,
                inverted_format,
            ),
            QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.Cursor, 1, 0),
            QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.Selection, 0, 1),
        ],
    )
    event.setCommitString("字", -1, 1)

    plain_event = ImeTextEdit._soft_composition_event(event)

    assert plain_event.preeditString() == "ㄓ"
    assert plain_event.commitString() == "字"
    assert plain_event.replacementStart() == -1
    assert plain_event.replacementLength() == 1
    assert [attribute.type for attribute in plain_event.attributes()] == [
        QInputMethodEvent.AttributeType.TextFormat,
        QInputMethodEvent.AttributeType.Cursor,
    ]
    assert plain_event.attributes()[0].value.underlineStyle() == QTextCharFormat.UnderlineStyle.SingleUnderline


def test_chat_input_draws_a_blinking_cursor_while_ime_text_is_composing() -> None:
    app = application()
    input_widget = ImeTextEdit()
    input_widget.show()
    input_widget.setFocus()
    app.processEvents()
    event = QInputMethodEvent(
        "ㄓ",
        [QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.Cursor, 1, 0)],
    )

    QApplication.sendEvent(input_widget, event)

    assert input_widget._ime_cursor_visible
    assert input_widget._ime_cursor_timer.isActive()
    assert input_widget.cursorRect().width() >= 1

    QApplication.sendEvent(input_widget, QInputMethodEvent("", []))

    assert not input_widget._ime_cursor_timer.isActive()
    input_widget.close()


def test_chat_input_keeps_normal_backspace_and_delete_for_committed_text() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    panel.input.setPlainText("中文")
    cursor = panel.input.textCursor()
    cursor.setPosition(1)
    panel.input.setTextCursor(cursor)

    QApplication.sendEvent(
        panel.input,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier),
    )
    assert panel.input.toPlainText() == "文"

    QApplication.sendEvent(
        panel.input,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier),
    )
    assert panel.input.toPlainText() == ""
    panel.close()


def test_chat_input_uses_shift_enter_for_a_new_line_and_enter_to_send() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")
    sent: list[str] = []
    panel._client.send = sent.append
    panel.input.setPlainText("first line")
    cursor = panel.input.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    panel.input.setTextCursor(cursor)

    QApplication.sendEvent(
        panel.input,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier),
    )

    assert panel.input.toPlainText() == "first line\n"
    assert sent == []

    QApplication.sendEvent(
        panel.input,
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
    )

    assert sent == ["first line"]
    panel.close()


def test_chat_input_grows_for_multiple_lines_then_returns_to_one_line() -> None:
    application()
    input_widget = ImeTextEdit()
    one_line_height = input_widget.height()

    input_widget.setPlainText("one\ntwo\nthree")

    assert input_widget.height() > one_line_height

    input_widget.clear()

    assert input_widget.height() == one_line_height
    input_widget.close()


def test_proactive_reminder_starts_a_separate_momo_transcript_turn() -> None:
    application()
    panel = ChatPanel("http://127.0.0.1:8765")

    panel._turn_started("reminder")
    panel._append_answer("該起來動一動囉")

    assert "Momo（提醒）" in panel.transcript.toPlainText()
    assert "該起來動一動囉" in panel.transcript.toPlainText()
    panel.close()


def test_avatar_right_click_menu_only_offers_close(monkeypatch) -> None:
    class MenuStub:
        actions: list[str] = []

        def __init__(self, _: object) -> None:
            self.actions = []
            MenuStub.actions = self.actions

        def addAction(self, text: str) -> str:
            self.actions.append(text)
            return text

        def exec(self, _: QPoint) -> None:
            return None

    monkeypatch.setattr(desktop, "QMenu", MenuStub)

    AvatarWindow._show_avatar_menu(object(), QPoint())

    assert MenuStub.actions == ["關閉 Momo"]
def test_replacing_a_gif_stops_and_releases_the_previous_movie(monkeypatch) -> None:
    class MovieStub:
        def __init__(self, *_: object) -> None:
            self.stopped = False
            self.deleted = False
            self.finished = type("SignalStub", (), {"connect": lambda *_: None})()
            self.frameChanged = type("SignalStub", (), {"connect": lambda *_: None})()

        def stop(self) -> None:
            self.stopped = True

        def deleteLater(self) -> None:
            self.deleted = True

        def setScaledSize(self, _: object) -> None:
            pass

        def start(self) -> None:
            pass

    class AvatarStub:
        def __init__(self) -> None:
            self.movies: list[object | None] = []

        def setMovie(self, movie: object | None) -> None:
            self.movies.append(movie)

    old_movie = MovieStub()
    window = type("WindowStub", (), {})()
    window._movie = old_movie
    window.avatar = AvatarStub()
    window._opacity_effect = type("OpacityStub", (), {"setOpacity": lambda *_: None})()
    window._assets = type("AssetsStub", (), {"path_for": lambda *_: __import__("pathlib").Path("idle.gif")})()
    window._animation_finished = lambda: None
    window._release_current_movie = lambda: AvatarWindow._release_current_movie(window)
    monkeypatch.setattr(desktop, "QMovie", MovieStub)

    AvatarWindow._play_plan(window, desktop.AnimationPlan("idle", loops=True))

    assert old_movie.stopped is True
    assert old_movie.deleted is True
    assert window.avatar.movies[0] is None


def test_one_shot_gif_finishes_at_its_last_frame_even_if_the_file_loops() -> None:
    class MovieStub:
        def __init__(self) -> None:
            self.stopped = False

        def frameCount(self) -> int:
            return 3

        def stop(self) -> None:
            self.stopped = True

    movie = MovieStub()
    window = type("WindowStub", (), {})()
    window._movie = movie
    window.finished = False
    window._animation_finished = lambda: setattr(window, "finished", True)

    AvatarWindow._one_shot_frame_changed(window, movie, 2)

    assert movie.stopped is True
    assert window.finished is True
