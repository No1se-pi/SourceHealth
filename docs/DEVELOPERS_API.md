# SourceHealth для разработчиков

Публичная страница `/developers` описывает существующие read-only endpoints и формирует Markdown для README badge.

```bash
curl 'https://sourcehealth.tech/api/v1/repositories?sort=health_score'
```

Основные endpoints: `GET /api/v1/repositories`, `GET /api/v1/repositories/{id}`, `GET /api/v1/repositories/{id}/analyses/latest`, `GET /api/v1/analyses/{id}` и экспорт `report.md`, `report.pdf`, `report.docx`. Актуальная схема доступна в `/openapi.json`.

`health_score=null` означает, что официальный Health ещё не рассчитан; это не ноль. `availability` описывает доступность фактов для категории. `score_preview` остаётся предварительным Source Soul и не является официальной оценкой.

Badge читает только сохранённый публичный результат и не запускает анализ:

```markdown
![SourceHealth](https://sourcehealth.tech/api/v1/badges/organization/repository.svg)
```

Числовой badge показывает только Health. При `health_score=null` выводится `no score`; неизвестный или непубличный репозиторий возвращает 404. Ответ кешируется на 5 минут.
