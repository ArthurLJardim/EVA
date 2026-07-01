from bot_faculdade.classroom import _due_at, _kind


def test_classroom_due_at_uses_end_of_day_without_time():
    work = {"dueDate": {"year": 2026, "month": 6, "day": 10}}
    result = _due_at(work, "America/Sao_Paulo")
    assert result is not None
    assert result.hour == 23
    assert result.minute == 59


def test_classroom_kind_detects_exam_words():
    assert _kind("Quiz avaliativo", "ASSIGNMENT") == "prova"
