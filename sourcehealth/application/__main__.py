"""Операторские команды. Ни одна не исполняет код анализируемого проекта."""

import argparse
import json

from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.logging_config import configure_logging
from sourcehealth.settings import Settings


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes rejected input; URLs/accidental secret arguments are not diagnostics.
        print(json.dumps({"overall": "error", "error": "invalid_arguments"}))
        raise SystemExit(2)


def main(argv=None):
    configure_logging()
    parser = SafeParser()
    parser.add_argument("command", choices=("worker", "worker-code", "enqueue-due", "dispatch", "register", "discover",
                                          "probe-sourcecraft", "accept-public", "doctor"))
    parser.add_argument("url", nargs="?")
    parser.add_argument("--organization", help="Ограничить discovery одной организацией")
    parser.add_argument("--limit", type=int, default=20, help="Максимум импортов discovery (1..100)")
    parser.add_argument("--timeout", type=float, default=900, help="Лимит ожидания accept-public, секунды (0..86400)")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
    except Exception:
        print(json.dumps({"overall": "error", "error": "configuration_invalid"}))
        return 2
    if args.command == "probe-sourcecraft":
        from .acceptance import probe_sourcecraft

        result, code = probe_sourcecraft(settings, args.url)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return code
    if args.command in {"accept-public", "doctor"}:
        return operator_command(args, settings)

    from rq import Queue, Worker

    from sourcehealth.storage.database import create_database

    from .connections import create_redis
    from .jobs import dispatch_pending, recover_abandoned
    from .services import AnalysisService

    engine, sessions = create_database(settings.database_url.get_secret_value())
    redis = create_redis(settings.redis_url.get_secret_value())
    try:
        service = AnalysisService(sessions, settings)
        if args.command in {"worker", "worker-code"}:
            if args.command == "worker-code" and not settings.code_runtime_enabled:
                parser.exit(2, "worker-code requires explicit CODE_RUNTIME_ENABLED=true on a trusted host\n")
            queue = "analysis-code" if args.command == "worker-code" else "analysis"
            Worker([Queue(queue, connection=redis)], connection=redis).work()
        elif args.command == "register":
            if not args.url:
                parser.error("register requires a SourceCraft URL")
            repository_id = service.import_public_repository(args.url)
            run = service.request_analysis(repository_id, trigger="system")
            dispatch_pending(sessions, redis, settings.analysis_timeout)
            print(f"repository_id={repository_id} analysis_id={run.id}")
        elif args.command == "discover":
            from sourcehealth.integrations.sourcecraft.analytics import CatalogCollector

            from .services import ServiceError

            if not 1 <= args.limit <= 100:
                parser.error("limit must be 1..100")
            imported = 0
            with SourceCraftClient(pat=settings.sourcecraft_pat.get_secret_value() if settings.sourcecraft_pat else None,
                                   max_pages=5, deadline_seconds=120) as client:
                found = CatalogCollector(client, max_items=args.limit).discover(args.organization)
                for item in found.facts["items"]:
                    try:
                        repository_id = service.import_public_repository(item["url"], client=client)
                        service.request_analysis(repository_id, trigger="system")
                        imported += 1
                    except ServiceError:
                        continue
            dispatch_pending(sessions, redis, settings.analysis_timeout)
            print(f"imported={imported} discovery_availability={found.availability.value}")
        else:
            recover_abandoned(engine, sessions, settings)
            if args.command == "enqueue-due":
                service.enqueue_due()
            print(f"enqueued={dispatch_pending(sessions, redis, settings.analysis_timeout)}")
    finally:
        redis.close()
        engine.dispose()


def operator_command(args, settings):
    """Операторский JSON boundary: даже ошибки Settings/driver не показывают DSN или traceback."""
    import math

    from sourcehealth.storage.database import create_database

    from .acceptance import accept_public, doctor, preflight
    from .connections import create_redis

    if args.command == "accept-public":
        _, error = preflight(settings, args.url)
        if not error and settings.analysis_profile != "mvp-v1":
            error = "mvp_profile_required"
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 86400:
            error = "invalid_acceptance_timeout"
        if error:
            print(json.dumps({"overall": "error", "error": error}))
            return 2
    engine = redis = None
    try:
        engine, sessions = create_database(settings.database_url.get_secret_value(), statement_timeout=10000)
        redis = create_redis(settings.redis_url.get_secret_value())
        result, code = (doctor(settings, sessions, redis) if args.command == "doctor" else
                        accept_public(settings, args.url, sessions, redis, timeout=args.timeout))
    except Exception:
        result, code = {"overall": "error", "error": "infrastructure_unavailable"}, 2
    finally:
        if redis is not None:
            redis.close()
        if engine is not None:
            engine.dispose()
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
