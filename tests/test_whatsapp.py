import json
from types import SimpleNamespace

from bot_faculdade import channels


def _settings(**overrides):
    base = dict(
        whatsapp_api_token="token-falso",
        whatsapp_phone_number_id="123",
        whatsapp_to="+55 (64) 99999-9999",
        whatsapp_template_name="aviso_bot",
        whatsapp_template_language="pt_BR",
        whatsapp_template_params=("EVA (faculdade)", "{mensagem}"),
        whatsapp_api_version="v21.0",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_payload_usa_template_com_numero_limpo_e_mensagem_numa_linha():
    payload = channels.build_whatsapp_payload(_settings(), "Prova 2\n\nem 3 dias!  ")
    assert payload["to"] == "5564999999999"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "aviso_bot"
    assert payload["template"]["language"] == {"code": "pt_BR"}
    parameters = payload["template"]["components"][0]["parameters"]
    assert [p["text"] for p in parameters] == ["EVA (faculdade)", "Prova 2 em 3 dias"]


def test_send_whatsapp_sem_configuracao_nao_chama_a_api(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("nao deveria chamar a API")

    monkeypatch.setattr(channels, "urlopen", fail)
    assert channels.send_whatsapp(_settings(whatsapp_template_name=""), "oi") is False
    assert channels.send_whatsapp(_settings(whatsapp_api_token=""), "oi") is False


def test_send_whatsapp_envia_para_a_url_e_headers_corretos(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(channels, "urlopen", fake_urlopen)
    assert channels.send_whatsapp(_settings(), "Prova amanha") is True
    assert captured["url"] == "https://graph.facebook.com/v21.0/123/messages"
    assert captured["auth"] == "Bearer token-falso"
    assert captured["body"]["template"]["name"] == "aviso_bot"


def test_send_all_so_usa_whatsapp_quando_recebe_texto(monkeypatch):
    sent = []
    monkeypatch.setattr(channels, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(channels, "send_telegram", lambda *a, **k: False)
    monkeypatch.setattr(channels, "send_whatsapp", lambda settings, text: sent.append(text) or True)

    channels.send_all(_settings(), "assunto", "corpo")
    assert sent == []
    channels.send_all(_settings(), "assunto", "corpo", "alerta importante")
    assert sent == ["alerta importante"]


def test_lembretes_vao_ao_whatsapp_so_se_alta_e_so_o_mais_proximo(monkeypatch):
    from bot_faculdade import notifier

    def row(uid, priority):
        return {
            "uid": uid,
            "title": f"Item {uid}",
            "due_at": "2026-11-20T23:59:00-03:00",
            "priority": priority,
            "kind": "prova",
            "course": "CALCULO",
            "source": "sigaa",
            "url": "",
            "description": "",
        }

    entries = [
        {"row": row("a", "alta"), "reminder_days": 7},
        {"row": row("a", "alta"), "reminder_days": 3},
        {"row": row("b", "media"), "reminder_days": 3},
    ]
    storage = SimpleNamespace(
        pending_notification_items=lambda days: entries,
        mark_notified=lambda uid, days: None,
    )
    calls = []
    monkeypatch.setattr(
        notifier, "send_all", lambda settings, subject, body, whatsapp_text=None: calls.append(whatsapp_text) or True
    )

    assert notifier.send_pending_notifications(SimpleNamespace(reminder_days=(7, 3)), storage) == 3
    assert calls[0] is None
    assert calls[1] is not None and "Item a" in calls[1] and "20/11/2026 23:59" in calls[1]
    assert calls[2] is None
