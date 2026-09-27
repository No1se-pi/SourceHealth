"""Bounded Git analytics that publish aggregates, never repository identities."""

from __future__ import annotations

import hashlib
import time
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from sourcehealth.snapshot import git

MAX_HISTORY_COMMITS = 5000
MAX_OWNERSHIP_COMMITS = 1000
MAX_PATH_TOUCHES = 20_000
MAX_OWNERSHIP_GROUPS = 20


def _identity(name: str, email: str) -> str:
    """Keep a stable in-memory key without ever returning the raw Git identity."""
    normalized = f"{name.strip().casefold()}\0{email.strip().casefold()}".encode("utf-8", "replace")
    return hashlib.sha256(normalized).hexdigest()


def summarize_contributors(identities: list[str], *, history_complete: bool) -> dict:
    counts = Counter(identities)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    aliases = {identity: f"Contributor {index}" for index, (identity, _) in enumerate(ordered[:10], 1)}
    total = len(identities)
    distribution = [
        {"alias": aliases[identity], "commits": count, "share": round(count / total, 4)}
        for identity, count in ordered[:10]
    ]
    if len(ordered) > 10:
        other = sum(count for _, count in ordered[10:])
        distribution.append({"alias": "Other", "commits": other, "share": round(other / total, 4)})
    shares = [count / total for _, count in ordered] if total else []
    bus_factor = None
    if total >= 5:
        cumulative = 0
        for index, (_, count) in enumerate(ordered, 1):
            cumulative += count
            if cumulative / total >= 0.5:
                bus_factor = index
                break
    return {
        "sampled_commits": total,
        "history_complete": history_complete,
        "contributors_count": len(ordered),
        "top_contributor_share": round(shares[0], 4) if shares else None,
        "top_2_contributors_share": round(sum(shares[:2]), 4) if shares else None,
        "top_3_contributors_share": round(sum(shares[:3]), 4) if shares else None,
        "contributor_distribution": distribution,
        "bus_factor_proxy": bus_factor,
        "bus_factor_threshold": 0.5,
        "bus_factor_basis": "commit_concentration",
        "bus_factor_sample_commits": total,
        "bus_factor_complete": history_complete,
        "bus_factor_reason": "insufficient_commit_sample" if total < 5 else None,
    }, aliases


def summarize_ownership(touches: list[tuple[str, str]], aliases: dict[str, str], *, complete: bool,
                        sampled_commits: int | None = None) -> dict:
    groups: dict[str, Counter] = defaultdict(Counter)
    for identity, relative in touches[:MAX_PATH_TOUCHES]:
        path = PurePosixPath(relative)
        if (path.is_absolute() or ".." in path.parts or any(ord(char) < 32 for char in relative)
                or "\\" in relative or ":" in relative):
            continue
        group = f"{path.parts[0]}/" if len(path.parts) > 1 else "(root)"
        groups[group][identity] += 1
    ordered = sorted(groups.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:MAX_OWNERSHIP_GROUPS]
    public = []
    for group, counts in ordered:
        dominant, amount = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        total = sum(counts.values())
        public.append({"path_group": group, "contributors": len(counts),
                       "dominant_alias": aliases.get(dominant, "Other"),
                       "dominant_share": round(amount / total, 4), "observed_touches": total})
    return {"ownership_groups": public, "ownership_complete": complete and len(touches) <= MAX_PATH_TOUCHES,
            "ownership_sample_commits": min(MAX_OWNERSHIP_COMMITS, sampled_commits if sampled_commits is not None else len(touches)),
            "path_touches_observed": min(len(touches), MAX_PATH_TOUCHES)}


class DeepGitCollector:
    """Use fixed Git arguments and strict limits inside the already isolated workspace."""

    def __init__(self, *, timeout: float = 20) -> None:
        self.timeout = timeout

    def collect(self, root: Path) -> dict:
        started = time.monotonic()
        history = git(root, "log", f"--max-count={MAX_HISTORY_COMMITS + 1}",
                      "--format=%aN%x1f%aE%x00", timeout=self.timeout)
        raw_identities = [item for item in history.decode("utf-8", "replace").split("\0")
                          if item.strip("\r\n")]
        identities = []
        for item in raw_identities[:MAX_HISTORY_COMMITS]:
            name, separator, email = item.lstrip("\n").partition("\x1f")
            identities.append(_identity(name, email if separator else ""))
        metrics, aliases = summarize_contributors(
            identities, history_complete=len(raw_identities) <= MAX_HISTORY_COMMITS)

        remaining = max(0.1, self.timeout - (time.monotonic() - started))
        output = git(root, "log", f"--max-count={MAX_OWNERSHIP_COMMITS + 1}",
                     "--format=%x1e%aN%x1f%aE", "--name-only", "-z", timeout=remaining)
        touches: list[tuple[str, str]] = []
        ownership_commits = 0
        for record in output.decode("utf-8", "replace").split("\x1e"):
            if not record:
                continue
            identity_line, _, names = record.partition("\n")
            name, separator, email = identity_line.strip("\0").partition("\x1f")
            identity = _identity(name, email if separator else "")
            ownership_commits += 1
            for path in names.split("\0"):
                path = path.strip("\n")
                if path:
                    touches.append((identity, path))
                    if len(touches) > MAX_PATH_TOUCHES:
                        break
            if len(touches) > MAX_PATH_TOUCHES:
                break
        metrics.update(summarize_ownership(
            touches, aliases,
            complete=ownership_commits <= MAX_OWNERSHIP_COMMITS and len(touches) <= MAX_PATH_TOUCHES,
            sampled_commits=min(ownership_commits, MAX_OWNERSHIP_COMMITS),
        ))
        metrics["deep_analytics_ms"] = round((time.monotonic() - started) * 1000)
        return metrics
