from p2026_little_avator.avatar_state import AvatarStateController


def test_one_shot_greeting_returns_to_looping_idle() -> None:
    controller = AvatarStateController()

    assert controller.play("greeting").state == "greeting"
    assert controller.play("greeting").loops is False
    assert controller.animation_finished().state == "idle"
    assert controller.current.loops is True


def test_drag_animation_returns_to_looping_idle_when_it_finishes() -> None:
    controller = AvatarStateController()

    plan = controller.drag_started()

    assert plan.state == "drag"
    assert plan.loops is False
    assert controller.animation_finished() == controller.current
    assert controller.current.state == "idle"
    assert controller.current.loops is True


def test_drag_keeps_only_latest_suggestion_until_drop_animation_finishes() -> None:
    controller = AvatarStateController()
    first = {"id": "first", "text": "先休息"}
    newest = {"id": "newest", "text": "喝水"}

    controller.drag_started()
    controller.receive_suggestion(first)
    controller.receive_suggestion(newest)
    assert controller.drag_released().state == "drop"

    assert controller.animation_finished().state == "happy"
    assert controller.visible_suggestion == newest
