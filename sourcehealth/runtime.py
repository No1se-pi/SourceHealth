"""AnalysisRuntime отделяет sandbox от analyzer logic; прежний Docker workflow сохранён."""

from typing import Protocol

from sourcehealth.core.domain import RepositoryRef


class AnalysisRuntime(Protocol):
    def analyze(self, repository: RepositoryRef) -> dict:
        """Выполнить локальный анализ с гарантированной cleanup-попыткой."""
        ...


def configured_runtime(settings) -> AnalysisRuntime | None:
    """Composition boundary: Docker доступ включается только в явном trusted процессе."""
    if not settings.code_runtime_enabled:
        return None
    return DockerAnalysisRuntime(image=settings.code_runtime_image, timeout=settings.code_runtime_timeout)


class DockerAnalysisRuntime:
    """Только публичный SourceCraft; worker API-only не получает Docker socket."""

    def __init__(self, *, image: str = "sourcehealth-sast", timeout: float = 180) -> None:
        self.image, self.timeout = image, timeout

    def analyze(self, repository: RepositoryRef) -> dict:
        from sourcehealth.sast.container import run_repository

        if repository.visibility != "public":
            raise ValueError("runtime supports verified public repositories only")
        return run_repository(repository.canonical_url, image=self.image, timeout=self.timeout)
