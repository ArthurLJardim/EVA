from bot_faculdade.materials import _matches_exam, _safe_name


def test_matches_exam_by_course_and_material_word():
    exam = {"title": "Prova 1", "course": "Inteligencia Artificial"}
    text = "Slides da aula de Inteligencia Artificial para revisao"
    assert _matches_exam(text, exam)


def test_safe_name_removes_path_characters():
    assert "\\" not in _safe_name("prova: aula/01?.pdf")
