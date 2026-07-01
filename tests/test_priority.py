from bot_faculdade.priority import classify_priority, is_urgent


def test_classify_priority_high_for_exam():
    assert classify_priority("Prova final de calculo", "prova") == "alta"


def test_classify_priority_medium_for_event():
    assert classify_priority("Palestra sobre IA", "noticia") == "media"


def test_is_urgent_uses_configured_keywords():
    assert is_urgent("Prazo final de matricula hoje", ("prazo final", "cancelado"))
