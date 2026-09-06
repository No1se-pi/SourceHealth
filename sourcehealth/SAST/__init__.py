"""Лёгкий SAST: ``SASTScanner().scan(path).to_dict()`` для общего JSON-отчёта."""

from .models import Finding, ScanConfig, ScanResult
from .rules import DEFAULT_RULES, Rule, load_rules, shannon_entropy
from .scanner import SASTScanError, SASTScanner
from .sarif import to_sarif

__all__ = [
    "DEFAULT_RULES", "Finding", "Rule", "SASTScanError", "SASTScanner",
    "ScanConfig", "ScanResult", "load_rules", "shannon_entropy", "to_sarif",
]
