"""Deterministic public metadata topic classifier v1 (catalog-topic-v1)."""

import re
from typing import Any, Final

TOPIC_CLASSIFIER_VERSION: Final[str] = "catalog-topic-v1"

ALL_TOPICS: Final[tuple[str, ...]] = (
    "bots",
    "web",
    "ml_data",
    "games",
    "education",
    "mobile",
    "devops",
    "security",
    "tools",
    "libraries",
    "other",
)

TOPIC_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "bots": (
        "bot", "telegram", "tgbot", "tg-bot", "discord-bot", "discordbot",
        "vk-bot", "vkbot", "chatbot", "chat-bot", "bot-framework",
        "бот", "боты", "телеграм", "дискорд", "чат-бот", "телеграм-бот",
    ),
    "web": (
        "web", "frontend", "backend", "site", "website", "api", "rest-api",
        "react", "vue", "angular", "svelte", "nextjs", "nuxt", "django",
        "fastapi", "flask", "express", "nestjs", "spring", "aspnet", "html",
        "css", "tailwind", "graphql", "rest",
        "веб", "сайт", "фронтенд", "бэкенд", "сервер", "интерфейс",
    ),
    "ml_data": (
        "ml", "ai", "neural", "model", "dataset", "data", "analytics",
        "nlp", "cv", "machine-learning", "deep-learning", "llm", "gpt",
        "pytorch", "tensorflow", "pandas", "numpy", "scikit", "keras",
        "машинное-обучение", "машинное", "нейросеть", "нейросети", "нейронная",
        "датасет", "датасеты", "аналитика", "классификатор", "распознавание",
    ),
    "games": (
        "game", "unity", "unreal", "pygame", "gamedev", "godot", "gaming",
        "arcade", "rpg", "shooter",
        "игра", "игры", "геймдев",
    ),
    "education": (
        "edu", "course", "tutorial", "student", "school", "learning",
        "lecture", "homework", "practice", "study", "university", "task",
        "assignment", "workshop", "lesson",
        "лабораторная", "лаба", "курсовая", "диплом", "учеба", "студент",
        "лекции", "домашнее", "задание", "практика",
    ),
    "mobile": (
        "android", "ios", "mobile", "flutter", "react-native", "swift",
        "swiftui", "kotlin-multiplatform", "kmp", "apk", "ipa",
        "мобильное", "мобильный", "андроид", "айос", "приложение",
    ),
    "devops": (
        "devops", "infra", "infrastructure", "docker", "dockerfile",
        "kubernetes", "k8s", "terraform", "ansible", "ci", "cicd",
        "pipeline", "deployment", "helm", "prometheus", "grafana",
        "деплой", "инфраструктура", "контейнер",
    ),
    "security": (
        "security", "infosec", "pentest", "scanner", "sast", "vuln",
        "vulnerability", "ctf", "cve", "exploit", "audit", "crypto",
        "malware", "firewall", "appsec",
        "безопасность", "уязвимости", "сканер", "взлом", "криптография",
    ),
    "tools": (
        "tool", "tools", "cli", "utility", "utilities", "generator",
        "automation", "scraper", "parser", "converter", "helper",
        "linter", "formatter", "scripts",
        "утилита", "утилиты", "генератор", "парсер", "скрапер", "автоматизация", "скрипт",
    ),
    "libraries": (
        "library", "lib", "sdk", "framework", "package", "client-library",
        "module", "wrapper", "plugin", "extension",
        "библиотека", "фреймворк", "пакет", "плагин",
    ),
}


def _tokenize(text: str) -> set[str]:
    """Extract lowercased word tokens and hyphenated compound tokens."""
    lowered = text.lower()
    # Split on whitespace and punctuation except hyphen and underscore
    parts = re.split(r"[^\w-]+", lowered)
    tokens: set[str] = set()
    for part in parts:
        if not part:
            continue
        tokens.add(part)
        # Also include sub-parts if hyphenated or underscored
        subparts = re.split(r"[-_]+", part)
        if len(subparts) > 1:
            for sp in subparts:
                if sp:
                    tokens.add(sp)
    return tokens


def classify_topics(
    repository_slug: str,
    description: str | None = None,
    project_slug: str | None = None,
    language: str | None = None,
) -> list[str]:
    """Classify a repository into one or more catalog topics deterministically."""
    combined_text = " ".join(
        part for part in (repository_slug, description or "", project_slug or "") if part
    )
    tokens = _tokenize(combined_text)

    matched: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in tokens:
                matched.append(topic)
                break
            # Also check if keyword is a clean substring of compound words
            if len(kw) >= 4 and any(kw in t for t in tokens):
                matched.append(topic)
                break

    # Secondary hints from language if no strong topic found or complementary
    if language:
        lang_lower = language.lower()
        if lang_lower in {"swift", "dart"} and "mobile" not in matched:
            matched.append("mobile")
        elif lang_lower in {"html", "css"} and "web" not in matched:
            matched.append("web")
        elif lang_lower in {"jupyter notebook"} and "ml_data" not in matched:
            matched.append("ml_data")

    if not matched:
        return ["other"]

    # Return sorted unique topics (capped at 5)
    return sorted(set(matched))[:5]


def reclassify_catalog_topics(
    sessions,
    *,
    batch_size: int = 500,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Deterministically backfill and update topics for catalog repositories."""
    from sqlalchemy import or_, select

    from sourcehealth.storage.models import Repository

    scanned = 0
    updated = 0

    with sessions.begin() as db:
        query = select(Repository).where(Repository.visibility == "public")
        if not force:
            query = query.where(
                or_(
                    Repository.topic_classifier_version != TOPIC_CLASSIFIER_VERSION,
                    Repository.topic_classifier_version.is_(None),
                    Repository.topics == [],
                )
            )
        query = query.order_by(Repository.id.asc())

        offset = 0
        while True:
            batch_query = query.offset(offset).limit(batch_size)
            batch = list(db.scalars(batch_query).all())
            if not batch:
                break

            for repo in batch:
                scanned += 1
                new_topics = classify_topics(
                    repo.repository_slug,
                    repo.description,
                    repo.project_slug,
                    repo.language,
                )
                if repo.topics != new_topics or repo.topic_classifier_version != TOPIC_CLASSIFIER_VERSION:
                    repo.topics = new_topics
                    repo.topic_classifier_version = TOPIC_CLASSIFIER_VERSION
                    updated += 1

            offset += len(batch)
            if limit and scanned >= limit:
                break

    return {
        "scanned": scanned,
        "updated": updated,
        "classifier_version": TOPIC_CLASSIFIER_VERSION,
    }
