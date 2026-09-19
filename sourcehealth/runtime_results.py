"""Legacy Docker JSON → публичные checks без raw errors и текста репозитория."""

import re
from dataclasses import fields
from datetime import UTC, datetime
from math import isfinite
from pathlib import PurePosixPath

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability, Evidence
from sourcehealth.git.activity import GitActivityMetrics

CLASSIFICATION = {"git_activity": ("activity", "git"), "sast": ("code_health", "sourcehealth_local")}
MVP_CLASSIFICATION = {**CLASSIFICATION, "documentation": ("documentation", "git_snapshot"),
                      "technical_debt": ("code_health", "git_snapshot")}
RUNTIME_ERRORS = frozenset({"docker_unavailable", "container_timeout", "docker_command_failed",
                            "invalid_or_missing_report", "invalid_report", "inconsistent_report"})
SAST_COUNTERS = ("files_scanned", "bytes_read", "entries_seen", "python_files_parsed",
                 "files_with_findings", "code_files_lexed")
SKIP_REASONS = frozenset({"file_limit", "total_bytes_limit", "timeout", "long_line", "finding_limit",
                          "binary", "encoding", "read_error", "entry_limit", "excluded", "link",
                          "depth_limit", "special_file", "hardlink", "file_changed_or_limit",
                          "lexical_error", "python_syntax_error", "python_ast_limit", "file_size_limit"})


def unavailable(name: str, code: str) -> AnalyzerResult:
    category, source = MVP_CLASSIFICATION[name]
    return AnalyzerResult(name, status="error", availability=DataAvailability.NO_DATA,
                          category=category, source=source, error=code)


def number(value, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not isfinite(value) or value < 0:
        raise ValueError("invalid numeric metric")
    return value


def relative_path(value):
    if (not isinstance(value, str) or not value or len(value) > 4096 or "\\" in value or ":" in value
            or any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute()
            or ".." in PurePosixPath(value).parts):
        raise ValueError("invalid relative location")
    return value


def git_result(raw: dict) -> AnalyzerResult:
    if raw.get("status") == "error":
        return unavailable("git_activity", "git_collection_failed")
    if raw.get("status") not in {"ok", "partial"}:
        raise ValueError("invalid git status")
    metrics = {}
    for field in fields(GitActivityMetrics):
        value = raw["metrics"][field.name]
        if field.name in {"first_commit_date", "last_commit_date"}:
            if value is not None:
                date = datetime.fromisoformat(value)
                if date.tzinfo is None:
                    raise ValueError("naive metric timestamp")
                value = date.astimezone(UTC).isoformat()
        elif value is not None:
            # days_since_last_commit can be negative for future-dated commits.
            if field.name == "days_since_last_commit":
                if type(value) not in (int, float) or not isfinite(value):
                    raise ValueError("invalid metric")
            else:
                number(value, integer=field.type == "int")
        elif field.type in {"int", "float"}:
            raise ValueError("missing required metric")
        metrics[field.name] = value
    return AnalyzerResult("git_activity", status=raw["status"], metrics=metrics,
                          category="activity", source="git", metadata={"history_scope": "default_branch_full"})


def sast_result(raw: dict) -> AnalyzerResult:
    # Trusted rule text comes from our package, never from a returned snippet/message.
    from sourcehealth.sast.models import ScanConfig
    from sourcehealth.sast.rules import DEFAULT_RULES

    if raw.get("error"):
        return unavailable("sast", "sast_failed")
    if type(raw.get("complete")) is not bool or not isinstance(raw.get("findings"), list):
        raise ValueError("invalid sast report")
    rules = {rule.id: rule for rule in DEFAULT_RULES}
    metrics = {key: number(raw[key], integer=True) for key in SAST_COUNTERS}
    metrics["summary"] = {key: number(raw["summary"][key], integer=True) for key in ("high", "medium", "low")}
    findings = []
    if len(raw["findings"]) > 1000:
        raise ValueError("too many findings")
    for finding in raw["findings"]:
        rule = rules[finding["rule_id"]]
        findings.append({"rule_id": rule.id, "severity": rule.severity,
                         "path": relative_path(finding["path"]),
                         "line": number(finding["line"], integer=True),
                         "column": number(finding["column"], integer=True),
                         "message": rule.message, "recommendation": rule.recommendation,
                         "category": rule.category, "confidence": rule.confidence,
                         "cwe": rule.cwe, "engine": rule.engine})
    metadata = {"complete": raw["complete"], "duration_seconds": number(raw.get("duration_seconds", 0)),
                "skipped": {key: number(value, integer=True) for key, value in raw.get("skipped", {}).items()
                            if key in SKIP_REASONS}}
    # Preserve numeric budgets; no arbitrary paths, extra fields or diagnostic text.
    metadata["config"] = {field.name: number(raw["config"][field.name]) for field in fields(ScanConfig)
                          if (field.name.startswith("max_") or field.name == "timeout_seconds")
                          and field.name in raw.get("config", {})}
    digest = raw.get("ruleset_digest", "")
    if digest and (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
        raise ValueError("invalid rules digest")
    metadata["ruleset_digest"] = digest
    version = raw.get("analyzer_version", "1")
    if not isinstance(version, str) or len(version) > 32 or any(c not in "0123456789." for c in version):
        raise ValueError("invalid analyzer version")
    return AnalyzerResult("sast", status="ok" if raw["complete"] else "partial", metrics=metrics,
                          findings=findings, metadata=metadata, category="code_health",
                          source="sourcehealth_local", analyzer_version=version)


def snapshot_result(name, raw):
    """Новый snapshot wire format также проходит allowlist перед сохранением."""
    if raw.get("availability") == "no_data":
        return unavailable(name, "snapshot_unavailable")
    metadata, metrics = raw["metadata"], raw["metrics"]
    sha = metadata["head_sha"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        raise ValueError("invalid snapshot SHA")
    complete = metadata["complete"]
    if type(complete) is not bool or raw["status"] != ("ok" if complete else "partial"):
        raise ValueError("invalid snapshot coverage")
    bools = {"readme", "license", "contributing", "codeowners", "docs_directory", "run_instructions",
             "build_instructions", "test_instructions"} if name == "documentation" else {"age_complete"}
    integers = {"readme_bytes", "readme_headings"} if name == "documentation" else {
        "todo_count", "fixme_count", "files_with_debt", "code_files", "large_files"}
    safe = {key: number(metrics[key], integer=True) for key in integers}
    for key in bools:
        if metrics[key] is not None and type(metrics[key]) is not bool:
            raise ValueError("invalid snapshot flag")
        safe[key] = metrics[key]
    if name == "technical_debt":
        for key in ("marker_density", "oldest_marker_age_days"):
            safe[key] = number(metrics[key]) if metrics[key] is not None else None
    configured = metadata.get("ci_configured")
    if configured is not None and type(configured) is not bool:
        raise ValueError("invalid CI flag")
    evidence = [Evidence(id=f"{name}:snapshot", source="git_snapshot", type="snapshot_observation", reference=sha,
                         summary="Проверка tracked snapshot; исходный текст не сохраняется.")]
    if name == "documentation":
        for item in raw.get("evidence", []):
            key = item.get("id", "").removeprefix("documentation:")
            if key in bools and item.get("location"):
                evidence.append(Evidence(id=f"documentation:{key}", source="git_snapshot", type="documentation_marker",
                                         reference=sha, location=relative_path(item["location"]),
                                         summary=f"Обнаружен признак {key}."))
    return AnalyzerResult(name, status="ok" if complete else "partial", category=MVP_CLASSIFICATION[name][0],
                          source="git_snapshot", metrics=safe, evidence=evidence,
                          metadata={"head_sha": sha, "complete": complete, "ci_configured": configured,
                                    "scope": "tracked_default_branch_excluding_generated"})


def normalize_runtime_report(payload: dict, *, with_mvp=False) -> dict[str, AnalyzerResult]:
    """Изолировать невалидные checks; неполный runtime/cleanup не становятся успехом."""
    if (not isinstance(payload, dict) or payload.get("schema_version") != "1.0"
            or type(payload.get("complete")) is not bool or not isinstance(payload.get("checks"), dict)):
        return {name: unavailable(name, "runtime_invalid_report") for name in (MVP_CLASSIFICATION if with_mvp else CLASSIFICATION)}
    error = payload.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    code = code if isinstance(code, str) and code in RUNTIME_ERRORS else "runtime_failed"
    results = {}
    converters = [("git_activity", git_result), ("sast", sast_result)]
    if with_mvp:
        converters += [("documentation", lambda raw: snapshot_result("documentation", raw)),
                       ("technical_debt", lambda raw: snapshot_result("technical_debt", raw))]
    for name, converter in converters:
        raw = payload["checks"].get(name)
        if raw is None:
            results[name] = unavailable(name, code if error else "runtime_missing_check")
            continue
        try:
            result = converter(raw)
            result.to_dict()
            results[name] = result
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            results[name] = unavailable(name, "runtime_invalid_check")
    envelope_incomplete = not payload["complete"] and all(r.status == "ok" for r in results.values())
    if error or payload.get("cleanup_pending") or envelope_incomplete:
        for result in results.values():
            if result.status == "ok":
                result.status, result.availability = "partial", DataAvailability.PARTIAL
            if result.error is None:
                result.error = "runtime_cleanup_pending" if payload.get("cleanup_pending") else "runtime_incomplete"
    return results
