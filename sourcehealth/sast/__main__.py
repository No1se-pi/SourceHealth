"""Совместимый SAST CLI с JSON 1.0; общий CLI: python -m sourcehealth."""

import os  # noqa: F401 -- совместимость patch(...__main__.os.replace)

from sourcehealth.cli import main as _main
from sourcehealth.cli import write_report
from sourcehealth.reporting import build_report

__all__ = ["build_report", "main", "write_report"]


def main(argv: list[str] | None = None) -> int:
    return _main(argv, legacy=True, with_git_default=False)


if __name__ == "__main__":
    raise SystemExit(main())
