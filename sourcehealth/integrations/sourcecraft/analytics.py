"""Allowlisted факты Public REST API; определения сверены со Swagger 19.09.2026."""

import re
from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import quote

from sourcehealth.core.domain import DataAvailability as A

from .client import SourceCraftError
from .collectors import CollectedFacts


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise SourceCraftError("invalid_response")
    return value


def timestamp(value, *, required=False):
    if value is None and not required:
        return None
    try:
        date = datetime.fromisoformat(value)
        if date.tzinfo is None:
            raise ValueError
        return date.astimezone(UTC).isoformat()
    except (ValueError, TypeError, OverflowError):
        raise SourceCraftError("invalid_response") from None


def enum(value, allowed):
    if not isinstance(value, str) or value not in allowed:
        raise SourceCraftError("invalid_response")
    return value


class ListCollector:
    """Полный пустой список — AVAILABLE; неудачная pagination сохраняет наблюдённую часть."""

    params = None

    def __init__(self, client, *, max_items=2000):
        self.client, self.max_items = client, max_items

    def collect(self, repository):
        path = self.client.repository_path(repository.organization_slug, repository.repository_slug) + self.suffix
        return self.collect_path(path)

    def collect_path(self, path):
        items, seen = [], set()
        try:
            for raw in self.client.iter_items(path, self.key, params=self.params):
                item = self.normalize(raw)
                if item is None:
                    continue
                if item["id"] in seen:
                    continue
                if len(items) >= self.max_items:
                    raise SourceCraftError("item_limit")
                seen.add(item["id"])
                items.append(item)
            return CollectedFacts("sourcecraft", A.AVAILABLE, {"items": items, "complete": True})
        except (SourceCraftError, TypeError, KeyError, AttributeError) as exc:
            code = exc.code if isinstance(exc, SourceCraftError) else "invalid_response"
            return CollectedFacts("sourcecraft", A.PARTIAL if items else A.SOURCE_UNAVAILABLE,
                                  {"items": items, "complete": False}, error=code)


class IssuesCollector(ListCollector):
    name, suffix, key = "issues", "/issues", "issues"

    def __init__(self, client, *, max_items=2000, comment_budget=10):
        super().__init__(client, max_items=max_items)
        self.comment_budget = comment_budget

    def normalize(self, raw):
        if raw.get("visibility") == "private":
            return None
        if raw.get("visibility") != "public":
            raise SourceCraftError("invalid_response")
        status = enum(raw["status"]["status_type"], {"initial", "in_progress", "paused", "completed", "cancelled"})
        created = timestamp(raw.get("created_at"), required=True)
        updated = timestamp(raw.get("updated_at"), required=True)
        completed = timestamp(raw.get("completed_at"))
        if datetime.fromisoformat(updated) < datetime.fromisoformat(created) or (
                completed and datetime.fromisoformat(completed) < datetime.fromisoformat(created)):
            raise SourceCraftError("invalid_response")
        return {"id": identifier(raw["id"]), "slug": identifier(raw["slug"]), "status": status,
                "created_at": created, "updated_at": updated,
                "closed_at": completed, "first_external_response_at": None,
                "_author_id": raw.get("author", {}).get("id") if isinstance(raw.get("author"), dict) else None,
                "response_complete": False}

    def collect(self, repository):
        result = super().collect(repository)
        path = self.client.repository_path(repository.organization_slug, repository.repository_slug)
        # Author IDs are compared only in memory and removed before facts leave this collector.
        # Missing identities/history cannot prove either an external reply or an unanswered issue.
        for issue in result.facts["items"][:self.comment_budget]:
            try:
                author_id = identifier(issue["_author_id"])
                dates = []
                for index, raw in enumerate(self.client.iter_items(f"{path}/issues/{quote(issue['slug'], safe='')}/comments",
                                                                  "issue_comments")):
                    if index >= 2000:
                        raise SourceCraftError("item_limit")
                    comment_author = identifier(raw.get("author", {}).get("id"))
                    created_at = timestamp(raw.get("created_at"), required=True)
                    if comment_author != author_id:
                        dates.append(created_at)
                valid = [d for d in dates if datetime.fromisoformat(d) >= datetime.fromisoformat(issue["created_at"])]
                issue["first_external_response_at"] = min(valid, key=datetime.fromisoformat) if valid else None
                issue["response_complete"] = True
            except (SourceCraftError, AttributeError, TypeError):
                pass
        for issue in result.facts["items"]:
            issue.pop("_author_id", None)
        return replace(result, schema_version="2")


class CICollector(ListCollector):
    name, suffix, key = "cicd", "/cicd/runs", "runs"

    def normalize(self, raw):
        dates = raw["dates"]
        started, completed = timestamp(dates.get("started_at")), timestamp(dates.get("finished_at"))
        # SourceCraft uses Unix epoch for stages that have not happened yet.
        if started == "1970-01-01T00:00:00+00:00":
            started = None
        if completed == "1970-01-01T00:00:00+00:00":
            completed = None
        duration = (datetime.fromisoformat(completed) - datetime.fromisoformat(started)).total_seconds() if started and completed else None
        if duration is not None and duration < 0:
            raise SourceCraftError("invalid_response")
        # Official Run schema: public IDs are not assigned yet; slug is the run counter.
        return {"id": identifier(raw.get("id") or raw.get("slug")),
                "status": enum(raw["status"], {"created", "prepared", "processing", "success", "failed", "canceled",
                                               "timeout", "skipped", "awaiting_approval", "rejected"}),
                "created_at": timestamp(dates.get("created_at"), required=True), "started_at": started,
                "completed_at": completed, "duration_seconds": duration}


class PullRequestsCollector(ListCollector):
    name, suffix, key = "pull_requests", "/pulls", "pull_requests"

    def normalize(self, raw):
        return {"id": identifier(raw["id"]),
                "status": enum(raw["status"], {"draft", "open", "discarded", "merging", "merged"}),
                "created_at": timestamp(raw.get("created_at"), required=True),
                "updated_at": timestamp(raw.get("updated_at"), required=True)}


class ContributorsCollector(ListCollector):
    name, suffix, key = "contributors", "/contributors", "contributors"

    def normalize(self, raw):
        return {"id": identifier(raw["id"])}  # No names, emails, biography or arbitrary profile fields.


class ReleasesCollector(ListCollector):
    name, suffix, key = "releases", "/releases", "releases"

    def normalize(self, raw):
        status = enum(raw["status"], {"draft", "published", "discarded"})
        if status != "published":
            return None  # Draft release notes may be visible to a service PAT; never publish them.
        return {"id": identifier(raw["id"]), "released_at": timestamp(raw.get("released_at"), required=True)}


class CatalogCollector(ListCollector):
    """Ограниченная discovery; pagination не является снимком всего каталога."""
    key = "repositories"
    params = {"sort_by": "created_at"}

    def normalize(self, raw):
        from sourcehealth.core.domain import RepositoryRef

        if raw.get("visibility") != "public":
            return None
        try:
            ref = RepositoryRef.from_url(f"https://sourcecraft.dev/{raw['organization']['slug']}/{raw['slug']}")
        except (ValueError, KeyError, TypeError):
            raise SourceCraftError("invalid_response") from None
        return {"id": identifier(raw["id"]), "url": ref.canonical_url}

    def discover(self, organization=None):
        if organization is None:
            self.params = {"sort_by": "created_at"}
            return self.collect_path("/repos")
        identifier(organization)
        # Org-scoped operation has no sort_by parameter in the official contract.
        self.params = None
        return self.collect_path(f"/orgs/{quote(organization, safe='')}/repos")
