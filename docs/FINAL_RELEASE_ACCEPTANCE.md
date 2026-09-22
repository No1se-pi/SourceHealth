# Финальная release-приёмка

## Phase A — baseline, 22 сентября 2026

Работа **не завершена**, release/PR gate пока не пройден. Статусы ниже относятся
только к этому запуску; прежние live-проверки не заменяют новую приёмку.

- Base: `11151e4fb2c3341b97a05b00c0afed87dad5ddf4`.
- Generator/benchmark checkpoint: `10fa20c4efaf778627aeaab1ab31e8d3c860b49c`.
- `git fetch origin Dev-No1se` подтвердил тот же SHA удалённой ветки.
- Ветка: `feature/final-mvp-100-closure`; исходное рабочее дерево чистое.
- Окружение: Archcraft, Python 3.14.7. Изолированный venv в `/tmp`, зависимости
  установлены из `requirements-server.lock`, Ruff 0.15.7 из `pyproject.toml`.
  Lock-файлы не менялись.

| Gate | Статус | Evidence |
|---|---|---|
| Unit | PASS с пропусками | Baseline 187 tests, 3.121 s; после generator regressions 189 tests, 4.297 s, OK, skipped=19 (18 integration, 1 live) |
| Ruff | PASS | `python -m ruff check .`: All checks passed |
| Runtime/MVP regressions | PASS | `python -m unittest tests.test_runtime_pipeline tests.test_mvp_collectors tests.test_mvp_analytics tests.test_mvp_snapshot -v`: 42 tests, 1.072 s, OK |
| OpenAPI/TS | PASS на Python 3.11 | Schema SHA256 из backend image совпадает с committed; npm run types, generated diff clean. Drift на 3.14 описан ниже |
| Frontend | PASS | npm ci, npm run types, npm run build; Node 26.9.0/npm 12.0.2 |
| Integration PostgreSQL/Redis/RQ | PASS | 18 tests, 4.116 s, OK; sourcehealth_test, Redis DB 15, Alembic upgrade/check |
| Compose smoke | PASS | scripts/compose_smoke.py: migration, health, HTTP 200, registered worker, down -v |
| MVP snapshot smoke | PASS | scanner image build + scripts/mvp_snapshot_smoke.py: offline Docker, Git/docs/debt/SAST, cleanup |
| Live public / large repo | BLOCKED large | PAT работает; discovery 20, metadata 3, clones 2; оба ниже large threshold. Ожидается разрешение на отдельный fixture: [evidence](LARGE_REPO_ACCEPTANCE.md) |
| Anti-size-skew / performance | NOT ACCEPTED | Целевые unit прошли, large измерений пока нет |
| AppSec investigation | NOT RUN | Новый official review ещё не выполнен |
| Yandex / SourceCraft browser | NOT RUN | Реального browser flow в этой сессии не было |
| Deployment / fallback | NOT PREPARED | Phases F–G ещё не начаты |
| Markdown / leak checks | NOT ACCEPTED | Отдельная release/live приёмка ещё не выполнена |
| Docker cleanup | PARTIAL ACCEPTANCE | Compose/snapshot smoke и 2 public measurement clones убраны; live large/timeout ещё не выполнены |

### Точные отклонения baseline

Первый запуск системным Python до установки dependencies: 179 tests,
`FAILED (errors=19, skipped=35)`, в том числе
`ModuleNotFoundError: No module named 'redis'` и `No module named 'httpx'`.
После установки lock эти ошибки исчезли. Полный suite в sandbox остановился на
`test_database_exception_does_not_leak_credentials`; повтор вне sandbox с внешним
лимитом 120 секунд завершился за 3.121 s, без failures.

OpenAPI drift воспроизводится до изменений кода. В данном Python
`http.HTTPStatus(422).phrase == 'Unprocessable Content'`.
Проверка на Python 3.11.16 внутри штатного backend image дала SHA256
`d686321d20131bd14d49fc3a502c1e937e3fdc1c383fabaf070222a9d37d65c5`,
побайтно совпадающий с `docs/openapi.json`. Для воспроизводимого contract gate
использовать Python 3.11, как в CI. Публичный контракт не обновлялся. Diff сохранён локально в
`/tmp/sourcehealth-baseline-openapi.diff`, generated artifact возвращён к HEAD.

### Продолжение после подготовки окружения

Установка `sudo -n pacman -S --needed --noconfirm nodejs npm docker docker-compose`
сначала остановилась с `sudo: a password is required`. После подтверждения владельца
об отключении password prompt установка выполнена, Docker запущен, доступ к socket
предоставлен только текущему host-пользователю; в web containers socket не монтировался.

Phase A закрыт с явно указанным ограничением Python для OpenAPI generation.
Phase B: добавлены deterministic generator и optional local benchmark, без внешней
публикации. Два дешёвых generator regression tests и Ruff прошли.
Подробные измерения и выявленный вопрос Python SAST score —
[LARGE_REPO_ACCEPTANCE](LARGE_REPO_ACCEPTANCE.md).

PAT настроен владельцем; один повторный bounded discovery подтвердил доступ.
Оба измеренных кандидата не достигли large threshold; cleanup подтверждён.
Следующий ручной шаг: разрешение на создание/push отдельного public fixture и
организация либо URL пустого repo. Запрос владельцу отправлен согласно пунктам
6.2/45 задания. Затем live large acceptance и оставшиеся C–H по порядку.
PR не открыт, push/merge не выполнялись.
