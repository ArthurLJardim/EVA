from __future__ import annotations

import argparse
import http.server
import socketserver

from .calendar_google import authorize_google_calendar
from .calendar_sync import sync_calendars
from .classroom import authorize_classroom, fetch_classroom_data
from .config import load_settings
from .dashboard import render_dashboard
from .email_reader import fetch_email_data
from .grades import apply_boletim_results, load_grade_configs
from .ics_exporter import export_ics
from .materials import archive_exam_materials
from .notifier import (
    send_change_notifications,
    send_daily_summary,
    send_grade_followups,
    send_grade_requests,
    send_link_questions,
    send_materials_archived_notification,
    send_pending_news_notifications,
    send_pending_notifications,
    send_urgent_notifications,
    send_weekly_report,
    process_grade_replies,
    process_link_replies,
)
from .sigaa import fetch_boletim_data, fetch_sigaa_data
from .storage import Storage


def _safe_fetch(label, fetch_fn):
    try:
        return fetch_fn()
    except Exception as exc:
        print(f"{label}: falhou ({exc}). Pulando esta fonte nesta execucao.", flush=True)
        return [], []


def _safe_call(label, fetch_fn, default):
    try:
        return fetch_fn()
    except Exception as exc:
        print(f"{label}: falhou ({exc}). Pulando esta etapa nesta execucao.", flush=True)
        return default


def sync(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)

    items = []
    news = []
    source_stable_keys = {}

    def add_source_items(found_items):
        items.extend(found_items)
        for item in found_items:
            source_stable_keys.setdefault(item.source, set()).add(item.stable_key)

    if not args.skip_email:
        print("Lendo e-mail academico...", flush=True)
        email_items, email_news = _safe_fetch("E-mail academico", lambda: fetch_email_data(settings))
        add_source_items(email_items)
        news.extend(email_news)
        print(f"E-mail concluido: {len(email_items)} itens, {len(email_news)} noticias.", flush=True)
    if not args.skip_sigaa:
        print("Lendo SIGAA...", flush=True)
        sigaa_items, sigaa_news = _safe_fetch(
            "SIGAA", lambda: fetch_sigaa_data(settings, debug_browser=args.debug_browser)
        )
        add_source_items(sigaa_items)
        news.extend(sigaa_news)
        print(f"SIGAA concluido: {len(sigaa_items)} itens, {len(sigaa_news)} noticias.", flush=True)
    if not args.skip_classroom:
        print("Lendo Google Classroom...", flush=True)
        classroom_items, classroom_news = _safe_fetch("Google Classroom", lambda: fetch_classroom_data(settings))
        add_source_items(classroom_items)
        news.extend(classroom_news)
        print(f"Classroom concluido: {len(classroom_items)} itens, {len(classroom_news)} noticias.", flush=True)

    print("Salvando itens e gerando arquivos locais...", flush=True)
    item_result = storage.upsert_items(items)
    news_result = storage.upsert_news(news)
    removed_rows = storage.mark_missing_items_removed(source_stable_keys)
    rows = storage.list_items()
    export_ics(settings, rows)
    render_dashboard(settings, storage)
    print("Sincronizando calendario...", flush=True)
    synced = _safe_call(
        "Sincronizacao de calendario",
        lambda: sync_calendars(settings, rows, storage, removed_rows),
        {"outlook": 0, "google": 0, "outlook_deleted": 0, "google_deleted": 0},
    )
    print("Enviando notificacoes...", flush=True)
    notified = send_pending_notifications(settings, storage) if args.notify else 0
    news_notified = send_pending_news_notifications(settings, storage) if args.notify else 0
    changes_notified = send_change_notifications(settings, item_result["changed"]) if args.notify else 0
    urgent_notified = (
        send_urgent_notifications(settings, item_result["new_items"], news_result["new_news"])
        if args.notify
        else 0
    )
    archived_materials = archive_exam_materials(settings, storage) if not args.skip_email else []
    materials_notified = (
        1 if args.notify and send_materials_archived_notification(settings, archived_materials) else 0
    )

    grades_answered = 0
    grade_requests_sent = 0
    grade_followups_sent = 0
    links_answered = 0
    link_questions_sent = 0
    if not args.skip_grades:
        print("Verificando boletim (notas e faltas) no SIGAA...", flush=True)
        boletim_results = _safe_call("Boletim SIGAA", lambda: fetch_boletim_data(settings), [])
        configs = load_grade_configs(settings.grade_formulas_path)
        apply_boletim_results(storage, configs, boletim_results)
        links_answered = process_link_replies(settings, storage)
        grades_answered = process_grade_replies(settings, storage)
        if args.notify:
            link_questions_sent = send_link_questions(settings, storage, item_result["new_items"])
            grade_requests_sent = send_grade_requests(settings, storage)
            grade_followups_sent = send_grade_followups(settings, storage)

    print(f"Itens encontrados nesta execucao: {len(items)}")
    print(f"Itens novos: {item_result['new']}")
    print(f"Itens alterados: {len(item_result['changed'])}")
    print(f"Itens removidos das fontes: {len(removed_rows)}")
    print(f"Noticias pertinentes encontradas nesta execucao: {len(news)}")
    print(f"Noticias novas: {news_result['new']}")
    print(f"Eventos enviados ao Outlook Calendar: {synced['outlook']}")
    print(f"Eventos enviados ao Google Calendar: {synced['google']}")
    print(f"Eventos removidos do Outlook Calendar: {synced['outlook_deleted']}")
    print(f"Eventos removidos do Google Calendar: {synced['google_deleted']}")
    print(f"Arquivo ICS atualizado: {settings.ics_output_path}")
    print(f"Dashboard atualizado: {settings.dashboard_output_path}")
    print(f"Avisos enviados: {notified}")
    print(f"Avisos de noticias enviados: {news_notified}")
    print(f"Avisos de mudancas enviados: {changes_notified}")
    print(f"Avisos urgentes enviados: {urgent_notified}")
    print(f"Materiais de prova arquivados: {len(archived_materials)}")
    print(f"Avisos de materiais enviados: {materials_notified}")
    print(f"Respostas de notas processadas: {grades_answered}")
    print(f"Pedidos de nota enviados: {grade_requests_sent}")
    print(f"Lembretes de nota enviados: {grade_followups_sent}")
    print(f"Respostas de vinculo processadas: {links_answered}")
    print(f"Perguntas de vinculo enviadas: {link_questions_sent}")


def list_items(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    rows = storage.list_items()
    if not rows:
        print("Nenhum item salvo ainda.")
        return
    for row in rows:
        print(f"{row['due_at']} | {row['priority']} | {row['kind']} | {row['title']} | {row['source']}")


def notify(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    sent = send_pending_notifications(settings, storage)
    news_sent = send_pending_news_notifications(settings, storage)
    print(f"Avisos enviados: {sent}")
    print(f"Avisos de noticias enviados: {news_sent}")


def list_news(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    rows = storage.list_news()
    if not rows:
        print("Nenhuma noticia salva ainda.")
        return
    for row in rows:
        print(f"{row['published_at']} | {row['priority']} | {row['title']} | {row['source']}")


def notify_news(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    sent = send_pending_news_notifications(settings, storage)
    print(f"Avisos de noticias enviados: {sent}")


def archive_materials(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    archived = archive_exam_materials(settings, storage)
    notified = send_materials_archived_notification(settings, archived) if args.notify else False
    print(f"Materiais de prova arquivados: {len(archived)}")
    print(f"Aviso enviado: {'sim' if notified else 'nao'}")


def list_materials(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    rows = storage.list_materials()
    if not rows:
        print("Nenhum material de prova arquivado ainda.")
        return
    for row in rows:
        print(f"{row['due_at']} | {row['exam_title']} | {row['filename']} | {row['saved_path']}")


def classroom_auth(args) -> None:
    settings = load_settings()
    authorize_classroom(settings)


def calendar_auth(args) -> None:
    settings = load_settings()
    authorize_google_calendar(settings)


def summary(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    sent = send_daily_summary(settings, storage)
    print(f"Resumo diario enviado: {'sim' if sent else 'nao'}")


def whatsapp_test(args) -> None:
    from .channels import send_whatsapp

    settings = load_settings()
    missing = [
        name
        for name, value in (
            ("WHATSAPP_API_TOKEN", settings.whatsapp_api_token),
            ("WHATSAPP_PHONE_NUMBER_ID", settings.whatsapp_phone_number_id),
            ("WHATSAPP_TO", settings.whatsapp_to),
            ("WHATSAPP_TEMPLATE_NAME", settings.whatsapp_template_name),
        )
        if not value
    ]
    if missing:
        print(f"WhatsApp nao configurado. Faltando no .env: {', '.join(missing)}")
        return
    ok = send_whatsapp(settings, "Teste do EVA: se voce recebeu esta mensagem, o WhatsApp esta funcionando")
    print(f"Mensagem aceita pela API da Meta: {'sim' if ok else 'nao (veja o erro acima)'}")
    if ok:
        print("A API aceitar nao garante entrega: confira se a mensagem chegou no seu WhatsApp.")


def weekly_report(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    sent = send_weekly_report(settings, storage)
    print(f"Resumo semanal enviado: {'sim' if sent else 'nao'}")


def dashboard(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    render_dashboard(settings, storage)
    print(f"Dashboard atualizado: {settings.dashboard_output_path}")


def serve_dashboard(args) -> None:
    settings = load_settings()
    storage = Storage(settings.database_path)
    render_dashboard(settings, storage)
    directory = str(settings.dashboard_output_path.parent)
    handler = lambda *handler_args, **handler_kwargs: http.server.SimpleHTTPRequestHandler(
        *handler_args,
        directory=directory,
        **handler_kwargs,
    )
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Dashboard em http://127.0.0.1:{args.port}/{settings.dashboard_output_path.name}")
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bot para SIGAA, e-mail academico e agenda.")
    sub = parser.add_subparsers(dest="command", required=True)

    sync_parser = sub.add_parser("sync", help="Busca itens, atualiza calendario e exporta ICS.")
    sync_parser.add_argument("--skip-email", action="store_true")
    sync_parser.add_argument("--skip-sigaa", action="store_true")
    sync_parser.add_argument("--skip-classroom", action="store_true")
    sync_parser.add_argument("--skip-grades", action="store_true")
    sync_parser.add_argument("--only-sigaa", action="store_true")
    sync_parser.add_argument("--only-classroom", action="store_true")
    sync_parser.add_argument("--debug-browser", action="store_true")
    sync_parser.add_argument("--notify", action="store_true")
    sync_parser.set_defaults(func=sync)

    list_parser = sub.add_parser("list", help="Lista itens salvos.")
    list_parser.set_defaults(func=list_items)

    notify_parser = sub.add_parser("notify", help="Envia avisos pendentes.")
    notify_parser.set_defaults(func=notify)

    list_news_parser = sub.add_parser("list-news", help="Lista noticias pertinentes salvas.")
    list_news_parser.set_defaults(func=list_news)

    notify_news_parser = sub.add_parser("notify-news", help="Envia avisos pendentes de noticias.")
    notify_news_parser.set_defaults(func=notify_news)

    archive_materials_parser = sub.add_parser("archive-materials", help="Arquiva anexos do e-mail relacionados a provas.")
    archive_materials_parser.add_argument("--notify", action="store_true")
    archive_materials_parser.set_defaults(func=archive_materials)

    list_materials_parser = sub.add_parser("list-materials", help="Lista materiais de prova arquivados.")
    list_materials_parser.set_defaults(func=list_materials)

    classroom_auth_parser = sub.add_parser(
        "classroom-auth",
        help="Autoriza o Google Classroom uma vez (abre o navegador; rode manualmente antes de agendar o sync).",
    )
    classroom_auth_parser.set_defaults(func=classroom_auth)

    calendar_auth_parser = sub.add_parser(
        "calendar-auth",
        help="Autoriza o Google Calendar uma vez (abre o navegador; rode manualmente antes de agendar o sync).",
    )
    calendar_auth_parser.set_defaults(func=calendar_auth)

    summary_parser = sub.add_parser("summary", help="Envia um resumo diario por e-mail/Telegram.")
    summary_parser.set_defaults(func=summary)

    weekly_report_parser = sub.add_parser("weekly-report", help="Envia o resumo semanal de faltas e medias.")
    weekly_report_parser.set_defaults(func=weekly_report)

    whatsapp_test_parser = sub.add_parser("whatsapp-test", help="Envia uma mensagem de teste pelo WhatsApp.")
    whatsapp_test_parser.set_defaults(func=whatsapp_test)

    dashboard_parser = sub.add_parser("dashboard", help="Gera o dashboard HTML local.")
    dashboard_parser.set_defaults(func=dashboard)

    serve_dashboard_parser = sub.add_parser("serve-dashboard", help="Abre um servidor local para o dashboard.")
    serve_dashboard_parser.add_argument("--port", type=int, default=8765)
    serve_dashboard_parser.set_defaults(func=serve_dashboard)

    args = parser.parse_args()
    if getattr(args, "only_sigaa", False):
        args.skip_email = True
        args.skip_sigaa = False
        args.skip_classroom = True
    if getattr(args, "only_classroom", False):
        args.skip_email = True
        args.skip_sigaa = True
        args.skip_classroom = False
    args.func(args)
