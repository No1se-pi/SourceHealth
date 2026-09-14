"""Обновить versioned контракт; запуск из корня репозитория."""

import json
from pathlib import Path

from sourcehealth.api.app import create_app

destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
destination.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
