"""Regression tests for keeping Momo's chat panel anchored to the avatar."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

import p2026_little_avator.desktop as desktop
from p2026_little_avator.chat import ChatPanel
from p2026_little_avator.desktop import AvatarWindow


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

    panel.input.setText("test message")
    panel.send_message()

    assert panel.thinking_indicator.isVisible()
    assert panel._thinking_timer.isActive()
    assert "Momo：" not in panel.transcript.toPlainText()
    first_frame = panel.thinking_indicator.text()
    panel._advance_thinking_indicator()
    assert panel.thinking_indicator.text() != first_frame

    panel._append_answer("first answer")

    assert not panel.thinking_indicator.isVisible()
    assert not panel._thinking_timer.isActive()
    assert "Momo：" in panel.transcript.toPlainText()
    assert "first answer" in panel.transcript.toPlainText()

    panel._completed()
    assert panel.input.isEnabled()
    assert panel.input.hasFocus()
    panel.close()


def test_chat_input_uses_gentle_selection_colours() -> None:
    panel = ChatPanel("http://127.0.0.1:8765")

    assert "selection-background-color: #e6dcff" in panel.styleSheet()
    assert "selection-color: #3d2866" in panel.styleSheet()

    panel.close()


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
