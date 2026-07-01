from bot_faculdade.news import clean_title, is_relevant_news


def test_relevant_news_needs_news_shape_and_keyword():
    keywords = ("curso", "estagio", "edital")
    assert is_relevant_news("Comunicado importante sobre edital de monitoria", keywords)
    assert not is_relevant_news("Entrega de atividade com prazo final", keywords)


def test_clean_title_prefers_news_line():
    text = "Menu\nComunicado sobre oportunidades de estagio\nTexto completo"
    assert clean_title(text) == "Comunicado sobre oportunidades de estagio"
