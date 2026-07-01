from __future__ import annotations


HIGH_WORDS = (
    "prova",
    "prazo final",
    "edital",
    "matricula",
    "matrícula",
    "cancelamento",
    "cancelado",
    "adiado",
    "urgente",
)

MEDIUM_WORDS = (
    "atividade",
    "tarefa",
    "palestra",
    "evento",
    "monitoria",
    "bolsa",
    "estagio",
    "estágio",
    "oportunidade",
)


def classify_priority(text: str, kind: str = "") -> str:
    low = f"{kind}\n{text}".lower()
    if any(word in low for word in HIGH_WORDS):
        return "alta"
    if any(word in low for word in MEDIUM_WORDS):
        return "media"
    return "baixa"


def is_urgent(text: str, keywords: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in keywords)
