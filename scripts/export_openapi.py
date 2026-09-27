"""Обновить versioned контракт; запуск из корня репозитория."""

import json
from pathlib import Path

from sourcehealth.api.app import create_app

destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
content = json.dumps(create_app().openapi(), indent=2, ensure_ascii=False)
content = content.replace('"description": "Unprocessable Content"', '"description": "Unprocessable Entity"')
destination.write_text(content + "\n", encoding="utf-8", newline="\n")
