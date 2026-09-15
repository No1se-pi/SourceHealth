"""Операторские команды. Ни одна не исполняет код анализируемого проекта."""

import argparse

from rq import Queue, Worker

from sourcehealth.core.domain import RepositoryRef
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.integrations.sourcecraft.collectors import RepositoryCollector
from sourcehealth.logging_config import configure_logging
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database

from .connections import create_redis
from .jobs import dispatch_pending, recover_abandoned
from .services import AnalysisService


def main():
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("worker", "enqueue-due", "dispatch", "register"))
    parser.add_argument("url", nargs="?")
    args = parser.parse_args()
    settings = Settings()
    engine, sessions = create_database(settings.database_url.get_secret_value())
    redis = create_redis(settings.redis_url.get_secret_value())
    try:
        service = AnalysisService(sessions, settings)
        if args.command == "worker":
            Worker([Queue("analysis", connection=redis)], connection=redis).work()
        elif args.command == "register":
            if not args.url:
                parser.error("register requires a SourceCraft URL")
            ref = RepositoryRef.from_url(args.url)
            with SourceCraftClient(pat=settings.sourcecraft_pat.get_secret_value() if settings.sourcecraft_pat else None) as client:
                result = RepositoryCollector(client).collect(ref)
            if result.availability != "available":
                parser.exit(2, "SourceCraft: cannot verify public repository\n")
            ref = RepositoryRef.from_url(ref.canonical_url, sourcecraft_id=result.facts["id"], visibility="public",
                                         default_branch=result.facts.get("default_branch"))
            repository_id = service.register_repository(ref)
            run = service.request_analysis(repository_id, trigger="system")
            dispatch_pending(sessions, redis, settings.analysis_timeout)
            print(f"repository_id={repository_id} analysis_id={run.id}")
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
