from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .channels import send_all
from .email_reader import fetch_grade_replies, fetch_link_replies
from .grades import compute_course_average, load_grade_configs, missing_components
from .priority import classify_priority


def _short(value: str, limit: int = 60) -> str:
    value = " ".join((value or "-").split())
    return value if len(value) <= limit else value[: limit - 3] + "..."


def send_pending_notifications(settings, storage) -> int:
    rows = storage.pending_notification_items(settings.reminder_days)
    if not rows:
        return 0

    # No WhatsApp vai um aviso por item a cada rodada (o mais proximo do prazo),
    # mesmo que mais de um marco (7, 3, 1 dias) esteja pendente ao mesmo tempo.
    tightest: dict[str, int] = {}
    for entry in rows:
        uid = entry["row"]["uid"]
        tightest[uid] = min(entry["reminder_days"], tightest.get(uid, entry["reminder_days"]))

    sent = 0
    for entry in rows:
        row = entry["row"]
        reminder_days = entry["reminder_days"]
        due_at = datetime.fromisoformat(row["due_at"])
        label = "hoje" if reminder_days == 0 else f"em ate {reminder_days} dias"
        subject = f"Faculdade: prazo {label} - {row['title']}"
        whatsapp_text = None
        if row["priority"] == "alta" and reminder_days == tightest[row["uid"]]:
            whatsapp_text = (
                f"Prazo {label}: {row['title']} ({_short(row['course'] or '-', 40)}) "
                f"- {due_at.strftime('%d/%m/%Y %H:%M')}"
            )
        body = "\n".join(
            [
                f"Item: {row['title']}",
                f"Prioridade: {row['priority']}",
                f"Tipo: {row['kind']}",
                f"Prazo: {due_at.strftime('%d/%m/%Y %H:%M')}",
                f"Disciplina: {row['course'] or '-'}",
                f"Origem: {row['source']}",
                f"Link: {row['url'] or '-'}",
                "",
                row["description"] or "",
            ]
        )
        if send_all(settings, subject, body, whatsapp_text):
            storage.mark_notified(row["uid"], reminder_days)
            sent += 1
    return sent


_CHANGE_FIELD_LABELS = {
    "title": "Titulo",
    "due_at": "Prazo",
    "course": "Disciplina",
    "kind": "Tipo",
    "description": "Descricao",
}


def _format_change_value(field_name: str, value: str) -> str:
    if field_name == "due_at" and value:
        try:
            return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value
    return value or "-"


def send_change_notifications(settings, changes: list[dict]) -> int:
    sent = 0
    for change in changes:
        item = change["item"]
        lines = [
            f"Item: {item.title}",
            f"Tipo: {item.kind}",
            f"Novo prazo: {item.due_at.strftime('%d/%m/%Y %H:%M')}",
            "",
            "Mudancas detectadas:",
        ]
        summary = []
        for field_name, old_value, new_value in change["changes"]:
            label = _CHANGE_FIELD_LABELS.get(field_name, field_name)
            old_shown = _format_change_value(field_name, old_value)
            new_shown = _format_change_value(field_name, new_value)
            lines.append(f"- {label}: {old_shown} -> {new_shown}")
            summary.append(f"{label} {_short(old_shown)} -> {_short(new_shown)}")
        important = classify_priority(f"{item.title}\n{item.description}\n{item.course}", item.kind) == "alta"
        whatsapp_text = f"Item alterado: {item.title}. {'; '.join(summary)}" if important else None
        if send_all(
            settings,
            f"Faculdade: item alterado - {item.title}",
            "\n".join(lines),
            whatsapp_text,
        ):
            sent += 1
    return sent


def send_urgent_notifications(settings, new_items, new_news) -> int:
    from .priority import is_urgent

    sent = 0
    for item in new_items:
        text = f"{item.title}\n{item.description}\n{item.kind}"
        if not is_urgent(text, settings.urgent_keywords):
            continue
        if send_all(
            settings,
            f"Faculdade: urgente - {item.title}",
            "\n".join(
                [
                    f"Item: {item.title}",
                    f"Tipo: {item.kind}",
                    f"Prazo: {item.due_at.strftime('%d/%m/%Y %H:%M')}",
                    f"Link: {item.url or '-'}",
                    "",
                    item.description or "",
                ]
            ),
            f"URGENTE: {item.title} - prazo {item.due_at.strftime('%d/%m/%Y %H:%M')}",
        ):
            sent += 1
    for item in new_news:
        text = f"{item.title}\n{item.description}"
        if not is_urgent(text, settings.urgent_keywords):
            continue
        if send_all(
            settings,
            f"Faculdade: noticia urgente - {item.title}",
            "\n".join(
                [
                    f"Noticia: {item.title}",
                    f"Origem: {item.source}",
                    f"Link: {item.url or '-'}",
                    "",
                    item.description or "",
                ]
            ),
            f"URGENTE: {item.title}",
        ):
            sent += 1
    return sent


def send_pending_news_notifications(settings, storage) -> int:
    rows = storage.pending_news_notifications()
    if not rows:
        return 0

    sent = 0
    for row in rows:
        published_at = datetime.fromisoformat(row["published_at"])
        subject = f"Faculdade: noticia pertinente - {row['title']}"
        body = "\n".join(
            [
                f"Noticia: {row['title']}",
                f"Prioridade: {row['priority']}",
                f"Publicacao/encontrada em: {published_at.strftime('%d/%m/%Y %H:%M')}",
                f"Origem: {row['source']}",
                f"Remetente: {row['sender'] or '-'}",
                f"Link: {row['url'] or '-'}",
                "",
                row["description"] or "",
            ]
        )
        if send_all(settings, subject, body):
            storage.mark_news_notified(row["uid"])
            sent += 1
    return sent


def send_daily_summary(settings, storage) -> bool:
    items = storage.upcoming_items(settings.summary_days_ahead)
    news = storage.recent_news(settings.summary_days_ahead)
    changes = storage.recent_changes(10)
    lines = [f"Resumo academico dos proximos {settings.summary_days_ahead} dias", ""]
    lines.append("Prazos e provas:")
    if items:
        for row in items:
            due_at = datetime.fromisoformat(row["due_at"])
            lines.append(f"- {due_at.strftime('%d/%m %H:%M')} | {row['priority']} | {row['kind']} | {row['title']}")
    else:
        lines.append("- Nenhum prazo encontrado.")
    lines.extend(["", "Noticias recentes:"])
    if news:
        for row in news[:10]:
            published_at = datetime.fromisoformat(row["published_at"])
            lines.append(f"- {published_at.strftime('%d/%m')} | {row['priority']} | {row['title']}")
    else:
        lines.append("- Nenhuma noticia recente.")
    lines.extend(["", "Mudancas recentes:"])
    if changes:
        for row in changes:
            lines.append(f"- {row['title']}: {row['field_name']} mudou")
    else:
        lines.append("- Nenhuma mudanca registrada.")
    return send_all(settings, "Faculdade: resumo diario", "\n".join(lines))


def _component_reference_date(settings, storage, course: str, component) -> datetime | None:
    tz = ZoneInfo(settings.timezone)
    linked_due_at = storage.get_component_link_due_at(course, component.key)
    if linked_due_at:
        return datetime.fromisoformat(linked_due_at)
    if component.due_date:
        year, month, day = (int(part) for part in component.due_date.split("-"))
        return datetime(year, month, day, tzinfo=tz)
    if component.item_title_contains:
        due_at = storage.find_item_due_at(course, component.item_title_contains)
        if due_at:
            return datetime.fromisoformat(due_at)
    return None


def _grade_request_body(config, course: str, keys: list[str]) -> str:
    lines = [
        f"Preciso de informacoes para calcular sua media em {course}.",
        "",
        'Responda este e-mail preenchendo os valores abaixo, mantendo o formato "chave: valor" (uma linha por valor):',
        "",
    ]
    for key in keys:
        component = config.component(key)
        label = component.label if component else key
        lines.append(f"{key}: ___    ({label})")
    lines.extend(["", "Pode usar ponto ou virgula decimal (ex: 8.5 ou 8,5)."])
    return "\n".join(lines)


def send_grade_requests(settings, storage) -> int:
    configs = load_grade_configs(settings.grade_formulas_path)
    now = datetime.now().astimezone()
    sent = 0
    for course, config in configs.items():
        values = storage.get_grade_values(course)
        due_keys = []
        for component in missing_components(config, values):
            reference = _component_reference_date(settings, storage, course, component)
            if reference is None:
                continue
            if now < reference + timedelta(days=settings.grade_request_days_after):
                continue
            due_keys.append(component.key)
        if not due_keys:
            continue
        if storage.open_grade_request_for_keys(course, due_keys):
            continue
        request_id = storage.create_grade_request(course, due_keys)
        subject = f"Faculdade: preciso da sua nota - {course} [nota#{request_id}]"
        body = _grade_request_body(config, course, due_keys)
        if send_all(settings, subject, body):
            sent += 1
    return sent


def send_grade_followups(settings, storage) -> int:
    configs = load_grade_configs(settings.grade_formulas_path)
    sent = 0
    for row in storage.pending_grade_followups(settings.grade_followup_days_after):
        config = configs.get(row["course"])
        if not config:
            continue
        keys = row["component_keys"].split(",")
        subject = f"Faculdade: (lembrete) preciso da sua nota - {row['course']} [nota#{row['id']}]"
        body = _grade_request_body(config, row["course"], keys)
        if send_all(settings, subject, body):
            storage.mark_grade_request_followed_up(row["id"])
            sent += 1
    return sent


def process_grade_replies(settings, storage) -> int:
    open_requests = storage.open_grade_requests()
    if not open_requests:
        return 0
    by_id = {row["id"]: row for row in open_requests}
    replies = fetch_grade_replies(settings, list(by_id.keys()))
    processed = 0
    for request_id, values in replies.items():
        row = by_id.get(request_id)
        if not row:
            continue
        for key, value in values.items():
            storage.set_grade_component(row["course"], key, value, "email")
        storage.mark_grade_request_answered(request_id)
        processed += 1
    return processed


def _unresolved_components(settings, storage, config) -> list:
    unresolved = []
    for component in config.all_components():
        if component.due_date or component.item_title_contains:
            continue
        if storage.get_component_link_due_at(config.course, component.key):
            continue
        unresolved.append(component)
    return unresolved


def send_link_questions(settings, storage, new_items) -> int:
    configs = load_grade_configs(settings.grade_formulas_path)
    sent = 0
    for item in new_items:
        config = configs.get(item.course)
        if not config:
            continue
        unresolved = _unresolved_components(settings, storage, config)
        if not unresolved:
            continue
        if storage.open_link_question_for_item(item.course, item.uid):
            continue
        question_id = storage.create_link_question(item.course, item.uid, item.title)
        options = ", ".join(component.key for component in unresolved)
        subject = f"Faculdade: a que nota corresponde? - {item.course} [vinculo#{question_id}]"
        body = "\n".join(
            [
                f"Apareceu uma atividade nova em {item.course}:",
                "",
                f"Titulo: {item.title}",
                f"Prazo: {item.due_at.strftime('%d/%m/%Y %H:%M')}",
                "",
                "A qual componente da formula de notas ela corresponde? Responda so com uma destas chaves:",
                f"{options}, ou nenhum se nao for nenhuma delas.",
                "",
                "resposta: ___",
            ]
        )
        if send_all(settings, subject, body):
            sent += 1
    return sent


def process_link_replies(settings, storage) -> int:
    open_questions = storage.open_link_questions()
    if not open_questions:
        return 0
    by_id = {row["id"]: row for row in open_questions}
    replies = fetch_link_replies(settings, list(by_id.keys()))
    processed = 0
    for question_id, answer in replies.items():
        row = by_id.get(question_id)
        if not row:
            continue
        if answer != "nenhum":
            storage.create_component_link(row["course"], answer, row["item_uid"])
        storage.mark_link_question_answered(question_id)
        processed += 1
    return processed


def send_weekly_report(settings, storage) -> bool:
    configs = load_grade_configs(settings.grade_formulas_path)
    attendance = {
        row["course"]: row
        for row in storage.list_current_course_attendance(settings.current_semester_stale_days)
    }
    courses = sorted(attendance.keys())
    if not courses:
        return False

    lines = ["Resumo semanal - faltas e medias", ""]
    for course in courses:
        att = attendance.get(course)
        faltas = att["faltas"] if att else 0
        max_faltas = att["max_faltas"] if att else None
        lines.append(f"{course}:")
        if max_faltas is not None:
            restantes = max_faltas - faltas
            lines.append(f"  Faltas: {faltas} de {max_faltas} permitidas ({restantes} restantes)")
        else:
            lines.append(f"  Faltas: {faltas}")
        config = configs.get(course)
        if config:
            values = storage.get_grade_values(course)
            average = compute_course_average(config, values)
            for unit_name, value in average["units"].items():
                shown = f"{value:.2f}" if value is not None else "ainda nao disponivel"
                lines.append(f"  {unit_name}: {shown}")
            final = average["final_average"]
            shown_final = f"{final:.2f}" if final is not None else "ainda nao disponivel"
            lines.append(f"  Media atual: {shown_final}")
        else:
            lines.append("  Media: formula ainda nao configurada")
        lines.append("")

    return send_all(settings, "Faculdade: resumo semanal de faltas e medias", "\n".join(lines))


def send_materials_archived_notification(settings, archived: list[dict]) -> bool:
    if not archived:
        return False
    lines = ["Materiais de estudo arquivados para prova:", ""]
    for item in archived:
        lines.extend(
            [
                f"Prova: {item['exam_title']}",
                f"Arquivo: {item['filename']}",
                f"Caminho: {item['path']}",
                f"E-mail: {item['subject']}",
                f"Remetente: {item['sender']}",
                "",
            ]
        )
    return send_all(settings, "Faculdade: materiais de prova arquivados", "\n".join(lines))
