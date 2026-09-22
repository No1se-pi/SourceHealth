"""Foundation-анализаторы безопасных платформенных фактов без сетевого I/O."""

from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.core.domain import DataAvailability, Evidence


class RepositoryMetadataAnalyzer:
    name = "repository_metadata"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        facts = context.sourcecraft_facts.get(self.name, {})
        availability = context.collection_statuses.get(self.name, DataAvailability.NO_DATA)
        evidence = []
        collection = context.metadata.get("collection", {}).get(self.name, {})
        if availability == DataAvailability.AVAILABLE and context.repository:
            evidence = [Evidence(id="repository:metadata", source="sourcecraft", type="repository_metadata",
                                 reference=context.repository.id, summary="Метаданные получены из SourceCraft API.",
                                 url=context.repository.canonical_url,
                                 timestamp=collection.get("collected_at", context.started_at.isoformat()))]
        return AnalyzerResult(self.name, status="ok" if evidence else "partial", metrics=facts,
                              availability=availability, source="sourcecraft", evidence=evidence, metadata=collection)


class SourceCraftSecurityAnalyzer:
    name = "sourcecraft_appsec"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        availability = context.collection_statuses.get("appsec", DataAvailability.NO_DATA)
        facts = context.sourcecraft_facts.get("appsec", {})
        collection = context.metadata.get("collection", {}).get("appsec", {})
        evidence = []
        if availability == DataAvailability.AVAILABLE and facts.get("complete") is True:
            evidence = [Evidence(id="appsec:scan", source="sourcecraft_appsec", type="official_security_scan",
                                 reference=facts.get("scan_uuid", ""),
                                 summary="Агрегат открытых дефектов из официального SourceCraft AppSec; без snippets.",
                                 timestamp=collection.get("collected_at", context.started_at.isoformat()))]
        return AnalyzerResult(self.name, status="ok" if evidence else "partial", category="security",
                              source="sourcecraft_appsec", metrics=facts, availability=availability,
                              evidence=evidence, error=None if evidence else collection.get("error"), metadata=collection)
