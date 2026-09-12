"""Общий CLI: python -m sourcehealth PATH --output report.json."""

from sourcehealth.cli import main

if __name__ == "__main__":
    raise SystemExit(main(legacy=False, with_git_default=True))
