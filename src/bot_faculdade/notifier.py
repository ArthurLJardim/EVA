from __future__ import annotations

from datetime import datetime

from .channels import send_all


def send_pending_notifications(settings, storage) -> int:
    rows = storage.pending_notification_items(settings.reminder_days)
    if not rows:
        return 0

    sent = 0
    for entry in rows:
        row = entry["row"]
        reminder_days = entry["reminder_days"]
        due_at = datetime.fromisoformat(row["due_at"])
        label = "hoje" if reminder_days == 0 else f"em ate {reminder_days} dias"
        subject = f"Faculdade: prazo {label} - {row['title']}"
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
        if send_all(settings, subject, body):
            storage.mark_notified(row["uid"], reminder_days)
            sent += 1
    return sent


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
        for field_name, old_value, new_value in change["changes"]:
            lines.append(f"- {field_name}: {old_value or '-'} -> {new_value or '-'}")
        if send_all(
            settings,
            f"Faculdade: item alterado - {item.title}",
            "\n".join(lines),
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
            )
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
