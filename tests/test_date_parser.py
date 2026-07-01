from bot_faculdade.date_parser import parse_due_date


def test_parse_brazilian_date_with_time():
    result = parse_due_date("Entrega da atividade ate 15/06/2026 as 23:59", "America/Sao_Paulo")
    assert result is not None
    assert result.day == 15
    assert result.month == 6
    assert result.hour == 23
    assert result.minute == 59


def test_parse_brazilian_date_without_time_uses_end_of_day():
    result = parse_due_date("Prova em 20/07/2026", "America/Sao_Paulo")
    assert result is not None
    assert result.hour == 23
    assert result.minute == 59


def test_parse_brazilian_date_without_year_assumes_current_or_next_year():
    result = parse_due_date("Atividade com prazo em 10/10", "America/Sao_Paulo")
    assert result is not None
    assert result.day == 10
    assert result.month == 10
    assert result.hour == 23
    assert result.minute == 59


def test_parse_brazilian_date_with_h_time():
    result = parse_due_date("Entrega em 10/10/2026 23h59", "America/Sao_Paulo")
    assert result is not None
    assert result.day == 10
    assert result.month == 10
    assert result.year == 2026
    assert result.hour == 23
    assert result.minute == 59
