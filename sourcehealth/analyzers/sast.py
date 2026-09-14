"""Адаптация ScanResult без изменения правил и движков SAST."""

from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.core.domain import DataAvailability
from sourcehealth.sast import SASTScanner


class SASTAnalyzerAdapter:
    name = "sast"

    def __init__(self, scanner: SASTScanner | None = None) -> None:
        self.scanner = scanner if scanner is not None else SASTScanner()

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        if context.workspace is None:
            return AnalyzerResult(self.name, status="partial", availability=DataAvailability.NO_DATA,
                                  category="code_health", source="sourcehealth_local", error="workspace_required")
        scan = self.scanner.scan(context.repo_path).to_dict()
        metrics = {key: scan.pop(key) for key in (
            "files_scanned", "bytes_read", "entries_seen", "python_files_parsed",
            "files_with_findings", "code_files_lexed", "summary",
        )}
        findings = scan.pop("findings")
        status = "ok" if scan["complete"] else "partial"
        scan.pop("analyzer")
        return AnalyzerResult(self.name, status, metrics, findings, metadata=scan,
                              category="code_health", source="sourcehealth_local",
                              availability=DataAvailability.AVAILABLE if status == "ok" else DataAvailability.PARTIAL)
