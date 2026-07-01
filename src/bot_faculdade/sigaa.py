from __future__ import annotations

from datetime import datetime
import re

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .date_parser import parse_due_date
from .models import AcademicItem, AcademicNews
from .news import clean_title, is_relevant_news


def _build_item_from_text(text: str, settings, url: str) -> AcademicItem | None:
    due_at = parse_due_date(text, settings.timezone)
    if not due_at:
        return None
    low = text.lower()
    kind = "prova" if any(word in low for word in ["prova", "avaliacao", "avaliação", "exame"]) else "atividade"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = next((line for line in lines if 5 <= len(line) <= 100), "Item do SIGAA")
    course = ""
    for line in lines:
        if re.search(r"(disciplina|turma|componente)", line, re.I):
            course = re.sub(r"^(disciplina|turma|componente)\s*:?\s*", "", line, flags=re.I)
            break
    return AcademicItem(
        title=title,
        due_at=due_at,
        course=course,
        kind=kind,
        source="sigaa",
        url=url,
        description=text[:1500],
    )


def _items_from_avaliacao_portal(soup: BeautifulSoup, settings, url: str) -> list[AcademicItem]:
    panel = soup.select_one("#avaliacao-portal")
    if not panel:
        return []
    items = []
    for row in panel.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        date_text = cells[1].get_text(" ", strip=True)
        due_at = parse_due_date(date_text, settings.timezone)
        if not due_at:
            continue
        detail_cell = cells[2]
        link = detail_cell.find("a")
        title = link.get_text(strip=True) if link else detail_cell.get_text(" ", strip=True)
        if not title:
            continue
        label = detail_cell.find("strong")
        label_text = label.get_text(strip=True) if label else ""
        kind = "prova" if "avalia" in label_text.lower() else "atividade"
        course = next(iter(detail_cell.stripped_strings), "")
        items.append(
            AcademicItem(
                title=title,
                due_at=due_at,
                course=course,
                kind=kind,
                source="sigaa",
                url=url,
                description=f"{course}\n{label_text} {title}".strip(),
            )
        )
    return items


def _generic_items_from_html(html: str, settings, url: str) -> list[AcademicItem]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    selectors = [
        "tr",
        ".atividade",
        ".avaliacao",
        ".prova",
        ".noticia",
        ".listagem tr",
        ".linhaPar",
        ".linhaImpar",
    ]
    for selector in selectors:
        blocks.extend(tag.get_text("\n", strip=True) for tag in soup.select(selector))
    if not blocks:
        blocks = [soup.get_text("\n", strip=True)]

    seen: set[str] = set()
    items: list[AcademicItem] = []
    for block in blocks:
        compact = "\n".join(line for line in block.splitlines() if line.strip())
        if len(compact) < 20 or compact in seen:
            continue
        seen.add(compact)
        if not re.search(r"(atividade|tarefa|prova|avaliacao|avaliação|data|prazo|entrega)", compact, re.I):
            continue
        item = _build_item_from_text(compact, settings, url)
        if item:
            items.append(item)
    return items


def _news_from_html(html: str, settings, url: str) -> list[AcademicNews]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    selectors = [
        ".noticia",
        ".notícias",
        ".noticias",
        ".comunicado",
        ".aviso",
        ".linhaPar",
        ".linhaImpar",
        "tr",
        "article",
        "section",
    ]
    for selector in selectors:
        blocks.extend(tag.get_text("\n", strip=True) for tag in soup.select(selector))
    if not blocks:
        blocks = [soup.get_text("\n", strip=True)]

    seen: set[str] = set()
    news: list[AcademicNews] = []
    for block in blocks:
        compact = "\n".join(line for line in block.splitlines() if line.strip())
        if len(compact) < 25 or compact in seen:
            continue
        seen.add(compact)
        if not is_relevant_news(compact, settings.news_keywords):
            continue
        news.append(
            AcademicNews(
                title=clean_title(compact, fallback="Noticia do SIGAA"),
                published_at=datetime.now().astimezone(),
                source="sigaa",
                url=url,
                description=compact[:1500],
            )
        )
    return news


def fetch_sigaa_data(settings, debug_browser: bool = False) -> tuple[list[AcademicItem], list[AcademicNews]]:
    if not settings.sigaa_url or not settings.sigaa_username or not settings.sigaa_password:
        return [], []

    with sync_playwright() as p:
        manual_login = settings.sigaa_manual_login or debug_browser
        browser = p.chromium.launch(headless=settings.sigaa_headless and not manual_login)
        page = browser.new_page()
        page.goto(settings.sigaa_url, wait_until="domcontentloaded")

        if manual_login:
            print("SIGAA: faca o login manualmente na janela do navegador.")
            input("Depois que a pagina inicial do SIGAA abrir, pressione Enter aqui para continuar...")
            page.wait_for_load_state("networkidle", timeout=20000)
        else:
            login_selectors = [
                'input[name="user.login"]',
                'input[id="username"]',
                'input[name="username"]',
                'input[name="login"]',
                'input[type="text"]',
            ]
            password_selectors = [
                'input[name="user.senha"]',
                'input[id="password"]',
                'input[name="password"]',
                'input[name="senha"]',
                'input[type="password"]',
            ]
            for selector in login_selectors:
                if page.locator(selector).count():
                    page.fill(selector, settings.sigaa_username)
                    break
            for selector in password_selectors:
                if page.locator(selector).count():
                    page.fill(selector, settings.sigaa_password)
                    break

            submit = page.locator(
                'input[type="submit"], button[type="submit"], input[value*="Entrar"], button:has-text("Entrar"), a:has-text("Entrar")'
            )
            if submit.count():
                submit.first.click()
                page.wait_for_load_state("networkidle", timeout=20000)
            else:
                page.keyboard.press("Enter")
                page.wait_for_load_state("networkidle", timeout=20000)

        base = settings.sigaa_url.rstrip("/")
        app_root = base if base.endswith("/sigaa") else f"{base}/sigaa"
        urls_to_try = [
            page.url,
            f"{app_root}/portais/discente/discente.jsf",
            f"{app_root}/ava/index.jsf",
        ]
        html_pages: list[tuple[str, str]] = []
        for url in dict.fromkeys(urls_to_try):
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                html_pages.append((page.content(), page.url))
            except Exception:
                continue

        portal_items: list[AcademicItem] = []
        generic_items: list[AcademicItem] = []
        news: list[AcademicNews] = []
        for html, url in html_pages:
            soup = BeautifulSoup(html, "html.parser")
            portal_items.extend(_items_from_avaliacao_portal(soup, settings, url))
            generic_items.extend(_generic_items_from_html(html, settings, url))
            news.extend(_news_from_html(html, settings, url))

        browser.close()
        items = portal_items if portal_items else generic_items
        deduped = {item.uid: item for item in items}
        deduped_news = {item.uid: item for item in news}
        return list(deduped.values()), list(deduped_news.values())


def fetch_sigaa_items(settings, debug_browser: bool = False) -> list[AcademicItem]:
    items, _ = fetch_sigaa_data(settings, debug_browser=debug_browser)
    return items
