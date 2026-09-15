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
        # No formula until actual SAST/SCA/secret evidence is integrated.
        availability = context.collection_statuses.get("appsec", DataAvailability.NO_DATA)
        return AnalyzerResult(self.name, status="partial", category="security", source="sourcecraft_appsec",
                              availability=availability, error="appsec_interface_unconfirmed")
