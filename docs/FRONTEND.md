# Frontend для независимой разработки

React + TypeScript + Vite, React Router используется для экранов. TanStack Query
пока не добавлен: текущий маленький набор fetch/polling не требует дополнительного слоя.
`frontend/src/api/client.ts` — единственная HTTP boundary, generated.ts — DTO из OpenAPI.
В компонентах не должны появляться Python imports, PostgreSQL connections или SourceCraft PAT.

## Запуск

Node 22.12+ (проверять engines установленной Vite; использован Node 24), npm.

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
npm run build --prefix frontend
```

Vite: http://127.0.0.1:5173, proxy /api → http://127.0.0.1:8000.
Frontend/API одного origin для cookies/CSRF. Для HTTP OAuth dev явно настроить
PUBLIC_ORIGIN/redirect/COOKIE_SECURE по [AUTH](AUTH.md), не редактировать API client URL.

## Routes и состояния

| Route | Назначение |
|---|---|
| / | Repository list, sort, offset pagination, empty/loading/error |
| /repositories/:id | Детали, последний report, async запуск |
| /analyses/:id | Polling lifecycle, nullable categories, Markdown download |
| /auth/callback | Проверка server session через /me; code/token не читает |
| * | 404 |

Polling 2 секунды до completed/partial/failed, отменяется при unmount. Ошибки отображаются
отдельно с request ID. Сейчас визуал — минимальная основа без финального дизайна.
Следующий frontend PR должен добавить evidence navigation, recommendations, strengths,
локализацию availability/category labels, language filter UI, retry и session menu/logout.
Backend sort/filter/DTO уже позволяют делать это независимо.

## Контракт и fixtures

```powershell
python scripts/export_openapi.py
npm run types --prefix frontend
```

generated.ts вручную не редактировать. В PR обновлять OpenAPI и generated.ts вместе.
Для разработки без сервисов использовать test/story fixtures с TypeScript `satisfies`
соответствующему DTO из generated.ts. Не встраивать fixture fallback в production API
client: ошибка сервера не должна заменяться красивым fake leaderboard.
Готовый demo mode сейчас не включён; пустая БД даёт честный пустой список.

Пример правила UI: `score === null ? 'Нет оценки' : score`. `available` означает
наличие фактов, не «хорошо». `partial` требует объяснения охвата. Все ссылки evidence
должны быть валидированы; external links открывать с безопасными attributes. Недоверенный
текст рендерить как React text; не использовать dangerouslySetInnerHTML для repository data.

## Что согласовывать

Изменение маршрутов UI/визуала — frontend ownership. Изменение HTTP DTO, nullable
semantics, пагинации, lifecycle названий и API version — общий архитектурный review.
Не добавлять analyzer-specific обязательный endpoint ради новой метрики: перечислять
checks и работать через общий контракт. Компиляция не заменяет browser acceptance:
проверить loading/error/empty/no-data/partial на desktop и узком экране.
