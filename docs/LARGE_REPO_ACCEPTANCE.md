# Large repository acceptance

## Fixture

- URL: <https://sourcecraft.dev/yaromirfominyh/sourcehealth-large-fixture>
- Threshold: `tracked files >= 10 000`.
- Fixture is deterministic, generated outside SourceHealth, uses one fixed commit/date,
  disables hooks and system/global Git config, and never executes target code.
- Composition: 100 small Python files, a few docs/metadata files, and tiny deterministic
  text records. No secrets, binary junk or artificial history.

## Final live result (after PR #13 merge)

Run date: 2026-09-23. The safe evidence fields below are the only values recorded. PATs,
headers, cookies, raw responses and target source were not persisted.

Current known fixture evidence:

| Field | Value |
|---|---|
| HEAD | `a0919aa50c63a818fc9d34997a2feb2076af3749` |
| tracked files | 10 000 |
| commits | 1 |
| working copy | 810 405 bytes |
| analysis id | `9991e363-8ec0-4a1b-9a5e-8ec5f4c092e2` |
| terminal status | `partial` (AppSec credential unavailable for CLI acceptance run) |
| Health / coverage | `61.17` / `65%` |
| duration | `10.707 s` reported by acceptance; `12 s` wall clock |
| scoring policy | `mvp-score-v1.2` from current base |
| cleanup | PASS: no temporary analysis containers or volumes |

Probe completed `overall=ok`, authenticated `true`, with all platform collectors available.
The analysis scanned 10 000 files / 810 405 bytes and observed 10 026 entries. Partial status
is explicit and does not convert unavailable AppSec data to a zero score.

## Local boundary benchmark

Run `python -m scripts.large_repository_benchmark`. It measures the current policy and
contracts dynamically through `MVPPolicy.version`; it does not change production scoring.

- small fixture (120): complete scan below large threshold (Health 82.31);
- large fixture (10 000): bounded local analysis; on this environment SAST reaches the 30-second timeout before exhausting the 10 000 file-count limit (files_scanned ~4 155, health 82.31, partial status);
- over-limit fixture (10 001): snapshot collector detects over-limit file count (>10 000), leaving documentation and code_health unscored (partial); coverage drops to 15% (below 50% threshold) and overall Health is null (not zero). In local benchmark runs, SAST reaches the 30-second timeout before exhausting 10 000 files, so the local benchmark log does not observe `file_limit` precedence directly.

### File-limit precedence
FILE-LIMIT PRECEDENCE: NOT PROVEN BY LOCAL 10K BENCHMARK DUE TO TIMEOUT PRECEDENCE.
On this environment, SAST cooperative timeout (30 s) triggers before 10 000 files are scanned. Production SAST file limit (`max_files=10 000`) is verified deterministically in `tests/test_sast.py::SASTTests::test_limits_bound_results_and_work` and `tests/test_large_fixture.py::LargeFixtureTests::test_sast_file_limit_guard_is_bounded_and_deterministic`.


## Limits and cleanup

The existing scanner budgets remain bounded (`max_files=10 000`, `max_entries=100 000`,
`max_total_bytes=512 MiB`, `max_findings=1000`, timeout). Clone/scan containers and volumes
must be absent after success, failure and timeout. This acceptance does not change scoring,
AppSec, partial semantics or Docker isolation.

## Known limitations

The fixture qualifies by file count, not commit count or working-copy size. Browser OAuth
acceptance and production deployment checks are separate gates.
