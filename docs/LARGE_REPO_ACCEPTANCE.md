# Large repository acceptance

## Fixture

- URL: <https://sourcecraft.dev/yaromirfominyh/sourcehealth-large-fixture>
- Threshold: `tracked files >= 10 000`.
- Fixture is deterministic, generated outside SourceHealth, uses one fixed commit/date,
  disables hooks and system/global Git config, and never executes target code.
- Composition: 100 small Python files, a few docs/metadata files, and tiny deterministic
  text records. No secrets, binary junk or artificial history.

## Final live result

The final run must be repeated after PR #13 is merged. The safe evidence fields below are
the only values to record: fixture HEAD, tracked files, commits, working-copy bytes,
analysis id, duration, terminal status, Health, coverage and cleanup status. Never record
PATs, headers, cookies, raw responses or target source.

Current known fixture evidence:

| Field | Value |
|---|---|
| HEAD | `a0919aa50c63a818fc9d34997a2feb2076af3749` |
| tracked files | 10 000 |
| commits | 1 |
| working copy | 810 405 bytes |

## Local boundary benchmark

Run `python -m scripts.large_repository_benchmark`. It measures the current policy and
contracts dynamically through `MVPPolicy.version`; it does not change production scoring.

- small fixture (120): below large threshold;
- large fixture (10 000): bounded scan completes;
- over-limit fixture (10 001): scanner reports `file_limit`, result is partial/incomplete,
  and no quality score is fabricated as zero.

## Limits and cleanup

The existing scanner budgets remain bounded (`max_files=10 000`, `max_entries=100 000`,
`max_total_bytes=512 MiB`, `max_findings=1000`, timeout). Clone/scan containers and volumes
must be absent after success, failure and timeout. This acceptance does not change scoring,
AppSec, partial semantics or Docker isolation.

## Known limitations

The fixture qualifies by file count, not commit count or working-copy size. Browser OAuth
acceptance and production run evidence are separate gates.
