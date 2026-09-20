"""Операторские команды. Ни одна не исполняет код анализируемого проекта."""

import argparse

from rq import Queue, Worker

from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.logging_config import configure_logging
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database

from .connections import create_redis
from .jobs import dispatch_pending, recover_abandoned
from .services import AnalysisService


def main():
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("worker", "worker-code", "enqueue-due", "dispatch", "register", "discover"))
    parser.add_argument("url", nargs="?")
    parser.add_argument("--organization", help="Ограничить discovery одной организацией")
    parser.add_argument("--limit", type=int, default=20, help="Максимум импортов discovery (1..100)")
    args = parser.parse_args()
    settings = Settings()
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


if __name__ == "__main__":
    main()
