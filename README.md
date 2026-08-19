# SourceHealth

SourceHealth collects Git history once and passes structured commits to
independent analyzers:

```text
Git repository -> GitCollector -> list[Commit] -> GitActivityAnalyzer
```

`GitCollector` runs Git with `cwd=repo_path` and a NUL-delimited custom
`git log --format`. It returns `Commit` dataclasses containing the hash, author
name and email, timezone-aware author datetime, and full commit message. It
does not calculate metrics or create an intermediate log file.

`GitActivityAnalyzer` never starts Git. It sorts collector output by absolute
time and returns `GitActivityMetrics`. Dates use ISO 8601 in UTC; all duration
and gap fields use days. Both `Commit` and `GitActivityMetrics` provide
`to_dict()` for JSON serialization.

## Example

Run from the project root and replace the path with any local repository:

```python
import json

from sourcehealth.git import GitActivityAnalyzer, GitCollector

commits = GitCollector().collect(r"D:\path\to\repository")
metrics = GitActivityAnalyzer().analyze(commits)

print(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2))
```

The analyzer reports commit totals, first and last dates, repository age,
time since the last commit, min/max/mean/median gaps, rolling commit counts,
active days and months, per-active-day and per-month averages, and the longest
gap without commits.

## Tests

The suite uses only the Python standard library plus a locally installed Git:

```powershell
python -m unittest discover -s tests -v
```
