"""Чистые платформенные метрики. Часы берутся только из AnalysisContext."""

from datetime import datetime, timedelta
from statistics import median

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.core.domain import Evidence


def date(value):
    return datetime.fromisoformat(value) if value else None


def observed(context, name):
    facts = context.sourcecraft_facts.get(name, {})
    availability = context.collection_statuses.get(name, A.NO_DATA)
    return facts.get("items", []), availability, availability == A.AVAILABLE and facts.get("complete") is True


def result(context, name, category, metrics, availability):
    evidence = []
    if availability in {A.AVAILABLE, A.PARTIAL, A.NOT_CONFIGURED}:
        evidence = [Evidence(id=f"{name}:observation", source="sourcecraft", type="platform_observation",
                             reference=context.repository.id, summary=f"Наблюдение {name}; окно 30 дней, полный охват указан отдельно.",
                             url=context.repository.canonical_url, timestamp=context.started_at.isoformat())]
    return AnalyzerResult(name, status="ok" if availability in {A.AVAILABLE, A.NOT_CONFIGURED} else "partial",
                          category=category, source="sourcecraft", metrics=metrics, availability=availability,
                          evidence=evidence, metadata={"window_days": 30, "reference_time": context.started_at.isoformat()})


class IssuesAnalyzer:
    name = "issues"

    def analyze(self, context):
        items, availability, complete = observed(context, self.name)
        cutoff = context.started_at - timedelta(days=30)
        opened = [i for i in items if i["status"] not in {"completed", "cancelled"}]
        closed = [i for i in items if i["status"] in {"completed", "cancelled"}]
        stale = [i for i in opened if date(i["updated_at"]) <= cutoff]
        responses = [(date(i["first_response_at"]) - date(i["created_at"])).total_seconds() / 3600
                     for i in items if i.get("first_response_at") and date(i["first_response_at"]) <= context.started_at]
        closing = [(date(i["closed_at"]) - date(i["created_at"])).total_seconds() / 3600
                   for i in closed if i.get("closed_at") and date(i["closed_at"]) <= context.started_at]
        response_complete = complete and all(i.get("response_complete") for i in items)
        metrics = {"observed_count": len(items), "complete": complete,
                   "open_count": len(opened) if complete else None, "closed_count": len(closed) if complete else None,
                   "stale_open_count": len(stale) if complete else None,
                   "stale_ratio": (len(stale) / len(opened) if opened else 0) if complete else None,
                   "median_first_response_hours": median(responses) if response_complete and responses else None,
                   "response_observed_count": len(responses), "response_complete": response_complete,
                   "median_close_hours": median(closing) if complete and closing and len(closing) == len(closed) else None,
                   "recent_created": sum(cutoff <= date(i["created_at"]) <= context.started_at for i in items) if complete else None,
                   "recent_closed": (sum(cutoff <= date(i["closed_at"]) <= context.started_at for i in closed)
                                     if complete and all(i.get("closed_at") for i in closed) else None)}
        return result(context, self.name, "issues", metrics, availability)


class CIAnalyzer:
    name = "cicd"

    def analyze(self, context):
        items, availability, complete = observed(context, self.name)
        success = [i for i in items if i["status"] == "success"]
        failed = [i for i in items if i["status"] in {"failed", "timeout", "rejected"}]
        terminal = success + failed
        durations = [i["duration_seconds"] for i in terminal if i.get("duration_seconds") is not None]
        configured = True if items else None
        # Only a complete snapshot + complete empty API history proves no native CI configuration.
        config = context.metadata.get("ci_configured")
        if complete and not items and config is False:
            configured, availability = False, A.NOT_CONFIGURED
        elif config is True:
            configured = True
        cutoff = context.started_at - timedelta(days=30)
        metrics = {"complete": complete, "configured": configured, "runs_observed": len(items),
                   "success_count": len(success) if complete else None,
                   "failure_count": len(failed) if complete else None,
                   "success_rate": len(success) / len(terminal) if complete and terminal else None,
                   "median_duration_seconds": median(durations) if complete and durations and len(durations) == len(terminal) else None,
                   "recent_failure_count": sum(cutoff <= date(i["created_at"]) <= context.started_at for i in failed) if complete else None,
                   "latest_status": max(items, key=lambda i: date(i["created_at"]))["status"] if complete and items else None}
        return result(context, self.name, "cicd", metrics, availability)


class PlatformActivityAnalyzer:
    name = "platform_activity"

    def analyze(self, context):
        pulls, pa, pc = observed(context, "pull_requests")
        contributors, ca, cc = observed(context, "contributors")
        releases, ra, rc = observed(context, "releases")
        availability = pa if pa == ca == ra else A.PARTIAL
        cutoff = context.started_at - timedelta(days=30)
        metrics = {"pr_count": len(pulls) if pc else None,
                   "merged_count": sum(i["status"] == "merged" for i in pulls) if pc else None,
                   "recent_pr_activity": sum(cutoff <= date(i["updated_at"]) <= context.started_at for i in pulls) if pc else None,
                   "contributors_count": len(contributors) if cc else None, "release_count": len(releases) if rc else None,
                   "last_release": max((i["released_at"] for i in releases), key=date, default=None) if rc else None,
                   "resource_availability": {"pull_requests": pa.value, "contributors": ca.value, "releases": ra.value}}
        return result(context, self.name, "activity", metrics, availability)
