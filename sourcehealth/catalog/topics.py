"""Deterministic public metadata topic classifier v1 (catalog-topic-v1)."""

import re
from typing import Final

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
    ),
    "web": (
        "web", "frontend", "backend", "site", "website", "api", "rest-api",
        "react", "vue", "angular", "svelte", "nextjs", "nuxt", "django",
        "fastapi", "flask", "express", "nestjs", "spring", "aspnet", "html",
        "css", "tailwind", "graphql", "rest",
    ),
    "ml_data": (
        "ml", "ai", "neural", "model", "dataset", "data", "analytics",
        "nlp", "cv", "machine-learning", "deep-learning", "llm", "gpt",
        "pytorch", "tensorflow", "pandas", "numpy", "scikit", "keras",
    ),
    "games": (
        "game", "unity", "unreal", "pygame", "gamedev", "godot", "gaming",
        "arcade", "rpg", "shooter",
    ),
    "education": (
        "edu", "course", "tutorial", "student", "school", "learning",
        "lecture", "homework", "practice", "study", "university", "task",
        "assignment", "workshop", "lesson",
    ),
    "mobile": (
        "android", "ios", "mobile", "flutter", "react-native", "swift",
        "swiftui", "kotlin-multiplatform", "kmp", "apk", "ipa",
    ),
    "devops": (
        "devops", "infra", "infrastructure", "docker", "dockerfile",
        "kubernetes", "k8s", "terraform", "ansible", "ci", "cicd",
        "pipeline", "deployment", "helm", "prometheus", "grafana",
    ),
    "security": (
        "security", "infosec", "pentest", "scanner", "sast", "vuln",
        "vulnerability", "ctf", "cve", "exploit", "audit", "crypto",
        "malware", "firewall", "appsec",
    ),
    "tools": (
        "tool", "tools", "cli", "utility", "utilities", "generator",
        "automation", "scraper", "parser", "converter", "helper",
        "linter", "formatter", "scripts",
    ),
    "libraries": (
        "library", "lib", "sdk", "framework", "package", "client-library",
        "module", "wrapper", "plugin", "extension",
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
        if lang_lower in {"swift"} and "mobile" not in matched:
            matched.append("mobile")
        elif lang_lower in {"html", "css"} and "web" not in matched:
            matched.append("web")

    if not matched:
        return ["other"]

    # Return sorted unique topics (capped at 5)
    return sorted(set(matched))[:5]
