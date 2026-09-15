"""AnalysisRuntime отделяет sandbox от analyzer logic; прежний Docker workflow сохранён."""

from typing import Protocol

from sourcehealth.core.domain import RepositoryRef


class AnalysisRuntime(Protocol):
    def analyze(self, repository: RepositoryRef) -> dict:
        """Выполнить локальный анализ с гарантированной cleanup-попыткой."""
        ...


class DockerAnalysisRuntime:
    """Только публичный SourceCraft; worker API-only не получает Docker socket."""

    def __init__(self, *, image: str = "sourcehealth-sast", timeout: float = 180) -> None:
        self.image, self.timeout = image, timeout

    def analyze(self, repository: RepositoryRef) -> dict:
        from sourcehealth.sast.container import run_repository

        if repository.visibility != "public":
            raise ValueError("runtime supports verified public repositories only")
        return run_repository(repository.canonical_url, image=self.image, timeout=self.timeout)
