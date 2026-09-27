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
  - Analyzer and clone containers enforce strict memory limits (`--memory=512m`, `--memory-swap=512m`), CPU limits (`--cpus=1`), process limits (`--pids-limit=128`), and temporary storage limits (`--tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m`).
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

## 5. Capacity Planning & Synthetic Concurrency Benchmark

### Synthetic Concurrency / Queue-Drain Benchmark

To verify concurrency guarantees without hitting live network services, an automated harness is provided in `scripts/benchmark_workers.py`.

> [!NOTE] Benchmark Scope & Methodology
> This is a **synthetic concurrency / queue-drain benchmark** using mocked external collectors and simulated stage latencies (50 ms per stage), executed with concurrent `SimpleWorker` consumers in threads.
> It does **not** benchmark:
> - Real Docker cloning;
> - Real SAST scanning;
> - Real SourceCraft HTTP latency;
> - Real worker-code OS processes.
>
> Its purpose is strictly to verify that:
> 1. There is no global serialization or lock bottleneck in database outbox dispatch or analysis lifecycle;
> 2. Multiple worker consumers process independent jobs concurrently without contention;
> 3. Queue drain throughput scales as consumer capacity increases under controlled workloads.

#### Example Synthetic Run (Simulated Stage Latency: 50 ms/stage)

Below is an example synthetic run conducted on a local development environment (16 vCPUs, local PostgreSQL & Redis):

| Scenario | Worker Consumers | Repositories | Queue Drain Time | Avg Run Duration | Max Simultaneous Active | Drain Speedup (Example Run) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 1 | 2 | ~3.5 s | ~1.6 s | 1 | Baseline (1w) |
| **B** | 1 | 4 | ~7.0 s | ~1.6 s | 1 | Baseline (1w) |
| **C** | 2 | 2 | ~1.8 s | ~1.6 s | 2 | ~1.9x |
| **D** | 2 | 4 | ~2.9 s | ~1.3 s | 2 | ~2.4x |

*Note: The figures above reflect one synthetic test run under simulated delays. They must not be interpreted as universal production speedup.*

### Host Capacity Sizing (Planning Guidance / Estimates)

The following sizing recommendations represent **planning guidance and estimates**, not measured production maximums:

- **Per-Container Footprint:**
  - Memory: 512 MB RAM + 512 MB swap (`--memory=512m --memory-swap=512m`).
  - CPU: 1 CPU limit (`--cpus=1`).
  - Processes: 128 PIDs (`--pids-limit=128`).
  - Tmpfs: 64 MB (`--tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m`).
- **Worker Process Footprint:**
  - Each `python -m sourcehealth.application worker-code` process typically consumes ~150–300 MB RSS base memory.
- **Estimated Host Allocation per Worker Instance ($N$):**
  - **CPU:** Allocate approximately 1 to 1.5 CPU cores per concurrent worker-code instance to prevent CPU throttling during static analysis.
  - **RAM (Planning Estimate):** Sizing should account for baseline host OS and shared infrastructure (PostgreSQL + Redis, ~1.5–2 GB) plus roughly 0.8–1 GB per active worker slot (covering worker process RSS and the 512 MB container ceiling). Actual RAM consumption depends on repository tree sizes and AST complexity.
- **Disk I/O:** Fast SSD/NVMe storage is recommended for concurrent ephemeral workspace volumes and git operations.

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
