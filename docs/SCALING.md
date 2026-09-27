# SourceHealth Scaling & Concurrency Architecture

## 1. Overview and Operational Topology

SourceHealth implements a modular monolithic architecture with independent process-level scaling for ingestion, scheduling, and code analysis.

### Process Topology

```text
               ┌────────────────┐
               │    FastAPI     │ (Stateless HTTP API, multi-instance)
               └───────┬────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────┐               ┌──────────────┐
│  PostgreSQL  │               │    Redis     │
│ (Persistence,│               │ (Queues,     │
│ Advisory Lock│               │  Dispatcher  │
│  Single-     │               │  Locks,      │
│   Flight)    │               │  Credential  │
└──────┬───────┘               │   Leases)    │
       │                       └──────┬───────┘
       │                              │
 ┌─────┴──────────────────────────────┴─────┐
 │                                          │
 ▼                                          ▼
┌────────────────────────┐      ┌────────────────────────────────┐
│   Generic RQ Worker    │      │  N x Trusted Worker-Code       │
│  (Queue: 'analysis')   │      │  (Queue: 'analysis-code')      │
│  - API metadata facts  │      │  - Docker execution runtime    │
│  - AppSec integration  │      │  - Ephemeral containers        │
│  - No Docker socket    │      │  - SAST & Git analysis         │
└────────────────────────┘      └────────────────────────────────┘
```

The system separates workloads into two distinct operational classes:
1. **Lightweight Platform Worker (`analysis` queue):**
   - Consumes only public and authorized REST API facts.
   - Operates without Docker daemon access.
   - Low CPU and RAM footprint; can scale to high concurrency on minimal infrastructure.
2. **Trusted Code Worker (`analysis-code` queue):**
   - Dedicated processes running `python -m sourcehealth.application worker-code`.
   - Has access to the local Docker socket to spawn isolated clone and scanner containers.
   - Scales horizontally on the host via systemd template instances (`sourcehealth-worker-code@1`, `sourcehealth-worker-code@2`, etc.).

---

## 2. Concurrency Guarantees & Single-Flight Model

SourceHealth enforces strict single-flight execution per repository and profile to eliminate duplicate heavy work:

1. **Database Partial Unique Index:**
   - Active runs (`queued`, `collecting`, `analyzing`, `scoring`) are guarded by a PostgreSQL partial unique index on `(repository_id, profile)`.
   - Concurrent API requests (`POST /api/v1/repositories/{id}/analyses`) return the existing active run ID rather than creating duplicates.
2. **Durable Outbox Dispatcher:**
   - Rows are committed as `queued` in PostgreSQL first.
   - `dispatch_pending` acts as a durable outbox processor, using short Redis locks (`sourcehealth:dispatch:{analysis_id}`) to safely enqueue jobs to RQ in bounded batches (up to 100 per cycle).
   - Duplicate RQ deliveries are idempotent: only the first worker acquiring the database advisory lock proceeds.
3. **Session Advisory Locks:**
   - Worker execution acquires a 64-bit PostgreSQL session advisory lock derived deterministically from the `analysis_id` (`pg_try_advisory_lock(lock_key)`).
   - If a duplicate job is dequeued by another worker, lock acquisition immediately fails, causing the redundant worker to exit cleanly without redundant network calls or container execution.
4. **Terminal Status Immutability:**
   - Transitions follow a strictly validated state machine:
     `queued -> collecting -> analyzing -> scoring -> (completed | partial | failed)`.
   - A terminal run (`completed`, `partial`, `failed`) can never be reopened or overwritten.

---

## 3. Worker-Code Security & Resource Boundary

When executing code analysis on untrusted repositories, the worker guarantees total isolation:

- **Ephemeral Workspaces:**
  - Each job allocates a unique Docker volume/directory (`sourcehealth-<uuid>`).
  - Workspaces are mounted read-only (`:ro`) into the scanner container.
  - Job cleanup only removes its own designated workspace; other concurrent workspaces remain untouched.
- **Resource Constraints:**
  - Analyzer containers enforce strict memory limits (`--memory=1g`), CPU limits (`--cpus=2`), and process limits (`--pids-limit=256`).
  - No network egress is permitted in the scanner container (`--network=none`).
- **Target Code Execution:**
  - Target code is NEVER executed, compiled, or evaluated. Only verified static analyzers inspect file trees.
- **Credential Isolation:**
  - Personal Access Tokens (PATs) are encrypted with AES-256-GCM under key separation (`sourcecraft_credential_key` vs `session_secret`).
  - PAT leases are bound strictly to `auth:analysis-sourcecraft:{analysis_id}` with short TTLs.
  - Tokens NEVER enter RQ job payloads, arguments, logs, database rows, or public report DTOs.
  - Credentials are automatically revoked and deleted from Redis upon job termination (success, partial, or failure).

---

## 4. Failure Recovery & Orphan Cleanup

- **Advisory Lock Fate Sharing:**
  - PostgreSQL advisory locks are bound to the worker's active database connection. If a worker process crashes, segfaults, or loses power, the operating system closes the socket and PostgreSQL immediately releases the advisory lock.
- **Dead Worker Recovery (`recover_abandoned`):**
  - Runs exceeding their `deadline_at` are scanned by the periodic cleanup task.
  - The cleaner attempts `pg_try_advisory_lock(:key)`. If the lock is held, the worker is alive and the job is untouched. If the lock is acquired, the cleaner confirms the worker is dead and transitions the run to `failed` with code `worker_interrupted`.
- **Failure Containment:**
  - Failures in one job (e.g. rate limit, worker crash, or timeout) never affect concurrent sibling jobs running in other worker processes.

---

## 5. Capacity Planning & Measured Benchmark Metrics

Measurements taken with the automated benchmark harness (`scripts/benchmark_workers.py`) on dev environment (Windows 11, 16 vCPUs, Docker Desktop, local PostgreSQL & Redis):

| Scenario | Workers | Repositories | Queue Drain Time | Avg Run Duration | Max Simultaneous Active | Effective Speedup |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 1 | 2 | 3.52 s | 1.63 s | 1 | Baseline (1w) |
| **B** | 1 | 4 | 7.02 s | 1.64 s | 1 | Baseline (1w) |
| **C** | 2 | 2 | 1.83 s | 1.65 s | 2 | **1.92x** |
| **D** | 2 | 4 | 2.94 s | 1.34 s | 2 | **2.39x** |

### Host Resource Planning Guidelines

When sizing hosts for `N` concurrent `worker-code` processes:
- **CPU:** Reserve 1.5–2 cores per worker process (e.g. 4 worker instances -> 8 cores recommended).
- **RAM:** Baseline host OS + Postgres + Redis requires ~2 GB. Each active `worker-code` process requires ~500 MB RAM, and each active scanner container requires up to 1 GB RAM limit.
  - For $N=2$: Minimum 6 GB RAM.
  - For $N=4$: Minimum 10 GB RAM.
- **Disk I/O:** Fast NVMe storage is strongly recommended for concurrent git clones.

---

## 6. Operational Monitoring

Operators can inspect live queue and database processing state using:

```bash
python -m sourcehealth.application queue-status
```

Sample output:
```json
{
  "analysis_queue_length": 0,
  "analysis_code_queue_length": 0,
  "queued_runs": 0,
  "collecting_runs": 0,
  "analyzing_runs": 0,
  "scoring_runs": 0,
  "oldest_queued_age_seconds": null,
  "failed_runs_24h": 0,
  "completed_runs_24h": 4
}
```

Structured JSON logging events emitted during processing:
- `worker_job_started`: Emitted when worker picks up a run (`analysis_id`, `repository_id`, `profile`, `queue`).
- `worker_job_finished`: Emitted upon job completion or failure (`duration_ms`, `status`).

---

## 7. Known Limitations & Future Roadmap

1. **Docker Host Contention:** All `worker-code` instances on a single host share the local Docker daemon socket (`/var/run/docker.sock`). At very high concurrency ($N > 8$), Docker daemon API locking can become a bottleneck.
   - *Future Solution:* Distribute worker nodes with isolated Docker engines behind a shared Redis queue.
2. **Git Clones In-Memory History:** `GitCollector` currently parses commit history into memory. For repos with $>100,000$ commits, streaming/chunked commit inspection should be implemented.
3. **External Rate Limits:** SourceCraft REST API limits apply across the IP/organization. Multiple workers requesting the same host will encounter 429 retries if total request frequency exceeds tier limits. Exponential backoff and jitter guard against thundering herds.
