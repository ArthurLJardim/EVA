from __future__ import annotations

from datetime import datetime
from html import escape


def _row(cells: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in cells) + "</tr>"


def render_dashboard(settings, storage) -> None:
    settings.dashboard_output_path.parent.mkdir(parents=True, exist_ok=True)
    items = storage.upcoming_items(60)
    news = storage.recent_news(30)
    changes = storage.recent_changes(20)
    materials = storage.list_materials()
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    item_rows = "\n".join(
        _row(
            [
                datetime.fromisoformat(row["due_at"]).strftime("%d/%m/%Y %H:%M"),
                row["priority"],
                row["kind"],
                row["title"],
                row["course"] or "",
            ]
        )
        for row in items
    ) or '<tr><td colspan="5">Nenhum prazo encontrado.</td></tr>'

    news_rows = "\n".join(
        _row(
            [
                datetime.fromisoformat(row["published_at"]).strftime("%d/%m/%Y %H:%M"),
                row["priority"],
                row["title"],
                row["source"],
            ]
        )
        for row in news
    ) or '<tr><td colspan="4">Nenhuma noticia recente.</td></tr>'

    change_rows = "\n".join(
        _row([row["created_at"], row["title"], row["field_name"], row["old_value"] or "", row["new_value"] or ""])
        for row in changes
    ) or '<tr><td colspan="5">Nenhuma mudanca registrada.</td></tr>'

    material_rows = "\n".join(
        _row([row["due_at"] or "", row["exam_title"] or "", row["filename"], row["saved_path"]])
        for row in materials
    ) or '<tr><td colspan="4">Nenhum material de prova arquivado.</td></tr>'

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bot Faculdade</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f4f7f6; color: #17211f; }}
    header {{ background: #165c4a; color: white; padding: 24px 32px; }}
    main {{ padding: 24px 32px; display: grid; gap: 24px; }}
    section {{ background: white; border: 1px solid #d9e2df; border-radius: 8px; overflow: hidden; }}
    h1, h2 {{ margin: 0; }}
    h2 {{ padding: 16px; font-size: 18px; border-bottom: 1px solid #d9e2df; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #edf1ef; text-align: left; vertical-align: top; }}
    th {{ background: #eef5f2; font-weight: 700; }}
    .meta {{ margin-top: 8px; opacity: .82; }}
  </style>
</head>
<body>
  <header>
    <h1>Bot Faculdade</h1>
    <div class="meta">Atualizado em {escape(generated_at)}</div>
  </header>
  <main>
    <section>
      <h2>Proximos prazos</h2>
      <table><thead><tr><th>Data</th><th>Prioridade</th><th>Tipo</th><th>Titulo</th><th>Disciplina</th></tr></thead><tbody>{item_rows}</tbody></table>
    </section>
    <section>
      <h2>Noticias recentes</h2>
      <table><thead><tr><th>Data</th><th>Prioridade</th><th>Titulo</th><th>Origem</th></tr></thead><tbody>{news_rows}</tbody></table>
    </section>
    <section>
      <h2>Mudancas detectadas</h2>
      <table><thead><tr><th>Data</th><th>Item</th><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead><tbody>{change_rows}</tbody></table>
    </section>
    <section>
      <h2>Materiais de prova</h2>
      <table><thead><tr><th>Data da prova</th><th>Prova</th><th>Arquivo</th><th>Caminho</th></tr></thead><tbody>{material_rows}</tbody></table>
    </section>
  </main>
</body>
</html>
"""
    settings.dashboard_output_path.write_text(html, encoding="utf-8")
