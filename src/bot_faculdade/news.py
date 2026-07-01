from __future__ import annotations

import re


NEWS_WORDS = (
    "noticia",
    "notícia",
    "comunicado",
    "aviso",
    "informativo",
    "novidade",
    "oportunidade",
)


def is_relevant_news(text: str, keywords: tuple[str, ...]) -> bool:
    low = text.lower()
    has_news_shape = any(word in low for word in NEWS_WORDS)
    has_keyword = any(keyword in low for keyword in keywords)
    return has_news_shape and has_keyword


def clean_title(text: str, fallback: str = "Noticia academica") -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if 8 <= len(line) <= 140]
    if not lines:
        return fallback
    for line in lines:
        if any(word in line.lower() for word in NEWS_WORDS):
            return line
    return lines[0]
