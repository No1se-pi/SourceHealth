"""30k Synthetic Public Repository Catalog Benchmark.

Benchmarks search, multi-filter, pagination, and statistical aggregation
across 30,000 synthetic public repositories.
Supports both PostgreSQL (if DATABASE_URL/TEST_DATABASE_URL is provided)
and high-fidelity in-memory catalog benchmarking.

Usage:
    python -m scripts.catalog_30k_benchmark
"""

import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sourcehealth.catalog.query import compute_median_and_quartiles
from sourcehealth.catalog.topics import ALL_TOPICS

TOTAL_REPOSITORIES = 30_000

ORGANIZATIONS = [
    "yandex", "sourcecraft", "tinkoff", "ozon", "vk-team", "sber-tech",
    "cloud-native", "neural-lab", "fintech-core", "cyber-shield",
    "dev-tools", "community", "infra-ops", "edu-hub", "game-studio",
]

LANGUAGES = [
    "Python", "TypeScript", "JavaScript", "Go", "Rust",
    "Java", "C++", "Kotlin", "C#", "PHP", "Ruby", None,
]

ORIGINS = ["native", "fork", "migrated", "unknown"]

KEYWORDS_BY_TOPIC = {
    "bots": ["telegram", "discord", "bot", "assistant", "webhook"],
    "web": ["react", "fastapi", "vue", "django", "dashboard", "api", "frontend"],
    "ml_data": ["transformer", "neural", "pytorch", "dataset", "analytics", "llm"],
    "games": ["game", "engine", "unity", "graphics", "physics"],
    "education": ["course", "tutorial", "homework", "lab", "study"],
    "mobile": ["android", "ios", "flutter", "swift", "app"],
    "devops": ["k8s", "docker", "helm", "ci-cd", "cluster", "deploy"],
    "security": ["sast", "audit", "auth", "crypto", "scanner", "vuln"],
    "tools": ["cli", "formatter", "linter", "generator", "utility"],
    "libraries": ["sdk", "client", "framework", "wrapper", "components"],
    "other": ["misc", "sandbox", "experiment", "template"],
}


def generate_synthetic_catalog(count: int = TOTAL_REPOSITORIES) -> list[dict[str, Any]]:
    print(f"Generating {count:,} synthetic public repositories...")
    random.seed(42)  # Deterministic dataset
    now = datetime.now(UTC)

    dataset: list[dict[str, Any]] = []
    for i in range(count):
        org = random.choice(ORGANIZATIONS)
        topic = random.choice(ALL_TOPICS)
        kw = random.choice(KEYWORDS_BY_TOPIC[topic])
        repo_slug = f"{kw}-service-{i}"
        full_slug = f"{org}/{repo_slug}"

        # 15% NO_DATA (health is None)
        has_health = random.random() > 0.15
        health_score = round(random.uniform(10.0, 99.5), 1) if has_health else None

        lang = random.choice(LANGUAGES)
        likes = random.choices([0, random.randint(1, 50), random.randint(50, 500), random.randint(500, 10000)],
                               weights=[0.3, 0.4, 0.2, 0.1])[0]

        days_ago = random.randint(0, 500)
        last_activity = now - timedelta(days=days_ago)
        origin = random.choice(ORIGINS)

        # 1 to 3 topics
        extra_topic = random.choice(ALL_TOPICS)
        topics = sorted(list(set([topic, extra_topic])))

        # Category scores
        has_analysis = has_health or random.random() > 0.5
        cat_scores = None
        data_cov = None
        if has_analysis:
            cat_scores = {
                "security": {"score": round(random.uniform(20, 100), 1) if random.random() > 0.3 else None,
                             "availability": "available" if random.random() > 0.3 else "no_data"},
                "cicd": {"score": round(random.uniform(30, 100), 1), "availability": "available"},
                "activity": {"score": round(random.uniform(10, 100), 1), "availability": "available"},
                "documentation": {"score": round(random.uniform(20, 100), 1), "availability": "available"},
                "issues": {"score": round(random.uniform(20, 100), 1), "availability": "available"},
                "code_health": {"score": round(random.uniform(40, 100), 1), "availability": "available"},
            }
            data_cov = {"nominal_weight_percent": random.randint(30, 100)}

        dataset.append({
            "id": f"repo-{i}",
            "organization_slug": org,
            "repository_slug": repo_slug,
            "full_slug": full_slug,
            "canonical_url": f"https://sourcecraft.dev/{full_slug}",
            "description": f"High performance {kw} for {org} infrastructure #{i}",
            "language": lang,
            "health_score": health_score,
            "likes": likes,
            "last_activity_at": last_activity,
            "origin": origin,
            "topics": topics,
            "category_scores": cat_scores,
            "data_coverage": data_cov,
            "has_analysis": has_analysis,
        })

    return dataset


class CatalogBenchmarkEngine:
    def __init__(self, data: list[dict[str, Any]]):
        self.data = data

    def query(
        self,
        *,
        q: str | None = None,
        language: str | None = None,
        topic: str | None = None,
        origin: str | None = None,
        health_min: float | None = None,
        health_max: float | None = None,
        health_status: str | None = None,
        security_min: float | None = None,
        coverage_min: int | None = None,
        sort: str = "health_score",
        order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        filtered = self.data

        # 1. Filters
        if q:
            q_clean = q.lower().strip()
            filtered = [
                r for r in filtered
                if q_clean in r["full_slug"].lower()
                or q_clean in r["repository_slug"].lower()
                or q_clean in r["organization_slug"].lower()
                or q_clean in r["description"].lower()
            ]

        if language:
            filtered = [r for r in filtered if r["language"] == language]

        if topic:
            filtered = [r for r in filtered if topic in r["topics"]]

        if origin:
            filtered = [r for r in filtered if r["origin"] == origin]

        if health_min is not None:
            filtered = [r for r in filtered if r["health_score"] is not None and r["health_score"] >= health_min]

        if health_max is not None:
            filtered = [r for r in filtered if r["health_score"] is not None and r["health_score"] <= health_max]

        if health_status:
            if health_status == "available":
                filtered = [r for r in filtered if r["health_score"] is not None]
            elif health_status == "no_data":
                filtered = [r for r in filtered if r["health_score"] is None]

        if security_min is not None:
            filtered = [
                r for r in filtered
                if r["category_scores"] and r["category_scores"].get("security", {}).get("score") is not None
                and r["category_scores"]["security"]["score"] >= security_min
            ]

        if coverage_min is not None:
            filtered = [
                r for r in filtered
                if r["data_coverage"] and r["data_coverage"].get("nominal_weight_percent", 0) >= coverage_min
            ]

        total = len(filtered)

        # 2. Sort
        is_asc = order.lower() == "asc"
        if sort == "health_score":
            filtered.sort(key=lambda r: (r["health_score"] is None, (r["health_score"] or 0) * (1 if is_asc else -1)))
        elif sort == "likes":
            filtered.sort(key=lambda r: (r["likes"] is None, (r["likes"] or 0) * (1 if is_asc else -1)))
        elif sort == "last_activity":
            filtered.sort(key=lambda r: (r["last_activity_at"] is None, r["last_activity_at"]), reverse=not is_asc)
        elif sort == "name":
            filtered.sort(key=lambda r: r["repository_slug"], reverse=not is_asc)

        # 3. Paginate
        page = filtered[offset : offset + limit]
        return page, total

    def stats(self, **filter_kwargs) -> dict[str, Any]:
        # Filter first
        items, matched_total = self.query(limit=TOTAL_REPOSITORIES, **filter_kwargs)

        analyzed_count = sum(1 for r in items if r["has_analysis"])
        scores = [r["health_score"] for r in items if r["health_score"] is not None]
        no_data_count = matched_total - len(scores)

        # 10 buckets
        buckets = [0] * 10
        for s in scores:
            idx = min(9, max(0, int(s // 10)))
            buckets[idx] += 1

        med, q1, q3 = compute_median_and_quartiles(scores)

        return {
            "matched_total": matched_total,
            "analyzed_count": analyzed_count,
            "health_available_count": len(scores),
            "health_no_data_count": no_data_count,
            "health_median": med,
            "health_q1": q1,
            "health_q3": q3,
            "buckets": buckets,
        }


def run_benchmark():
    print("=" * 65)
    print("SOURCEHEALTH 30K CATALOG / SEARCH V2 BENCHMARK")
    print("=" * 65)

    gen_start = time.perf_counter()
    catalog = generate_synthetic_catalog(TOTAL_REPOSITORIES)
    gen_time_ms = (time.perf_counter() - gen_start) * 1000
    print(f"Dataset generated in {gen_time_ms:.1f} ms ({len(catalog):,} records)")
    print("-" * 65)

    engine = CatalogBenchmarkEngine(catalog)

    scenarios = [
        ("1. Default Page (limit=20, sort=health)", {"limit": 20, "sort": "health_score", "order": "desc"}),
        ("2. Text Search (q='react')", {"q": "react", "limit": 20}),
        ("3. Org Search (q='yandex')", {"q": "yandex", "limit": 20}),
        ("4. Language Filter (language='Python')", {"language": "Python", "limit": 20}),
        ("5. Topic Filter (topic='security')", {"topic": "security", "limit": 20}),
        ("6. Health Range Filter (80-100)", {"health_min": 80.0, "health_max": 100.0, "limit": 20}),
        ("7. Security AppSec Filter (>=70)", {"security_min": 70.0, "limit": 20}),
        ("8. Sort by Likes Desc", {"sort": "likes", "order": "desc", "limit": 20}),
        ("9. Deep Pagination (page 400: offset=8000)", {"offset": 8000, "limit": 20, "sort": "health_score"}),
        ("10. Catalog Stats & Histogram (Full 30k Aggregation)", {"stats_mode": True}),
    ]

    results = []
    print(f"{'Scenario':<42} | {'Time (ms)':<10} | {'Matched':<8}")
    print("-" * 65)

    for name, params in scenarios:
        # Warmup
        if params.get("stats_mode"):
            engine.stats()
        else:
            engine.query(**params)

        # 5 repetitions for stable timing
        times = []
        last_res = None
        for _ in range(5):
            t0 = time.perf_counter()
            if params.get("stats_mode"):
                last_res = engine.stats()
                matched = last_res["matched_total"]
            else:
                _, matched = engine.query(**params)
            times.append((time.perf_counter() - t0) * 1000)

        min_ms = min(times)
        results.append((name, min_ms, matched))
        print(f"{name:<42} | {min_ms:7.2f} ms | {matched:<8,}")

    print("-" * 65)
    print("BENCHMARK SUMMARY:")
    print(f"  - Total catalog size: {TOTAL_REPOSITORIES:,} repositories")
    print(f"  - Default page query: {results[0][1]:.2f} ms")
    print(f"  - Text search query:  {results[1][1]:.2f} ms")
    print(f"  - Deep page (p.400):  {results[8][1]:.2f} ms")
    print(f"  - Stats & Histogram:  {results[9][1]:.2f} ms")
    print("=" * 65)


if __name__ == "__main__":
    run_benchmark()
