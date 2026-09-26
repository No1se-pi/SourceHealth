# Mandatory 100 Closure — журнал приёмки

Статус: **независимые этапы закрыты; Definition of Done заблокирован browser OAuth и large repo**.
Дата: 21.09.2026.
Ветка: `feature/` + `mandatory-100-closure`.
Базовый GitHub commit: 679e10ea3a7cea45f6f022371b28f953aaac4966.
PR/merge/push feature в SourceCraft main запрещены до отдельного разрешения.

## Проверенная исходная картина

- GitHub Actions для базы: success, https://github.com/No1se-pi/SourceHealth/actions/runs/35510831612.
- SourceCraft main: `aa225141a057fb0ad28c49e6bc37409f8d8903fd`,
  `Run SourceCraft checks in native Python and Node cubes`, 2026-09-20T19:57:15+03:00.
- Сравнены Git blob IDs всех 257 файлов: содержимое GitHub базы и SourceCraft совпадает,
  кроме дополнительного `.sourcecraft/ci.yaml`. Повторный перенос не требуется.
- Репозиторий public, default branch main; CI run 4 success.
- Миграция базы 0001; повторный OpenAPI export не изменил контракт.

## Текущий атомарный этап

- Likes читаются только из `rating.reaction_counts.positive_low` (uint64 string).
  Отсутствующий rating/невалидный count — null. Полный sparse список без Like — 0.
  Существующее поле PostgreSQL int32: слишком большой count остаётся null, не обрезается.
- Import и worker refresh обновляют likes; cache metadata переведён на новый ключ.
- CI Run: официальный Swagger говорит, что public IDs пока отсутствуют;
  collector использует slug при пустом id. Epoch незавершённых стадий — неизвестная дата.
- Regression tests добавлены. Полный unit suite: 180 tests, OK, skipped=16.
  Ruff passed; live probe team-41 overall=ok; opt-in contract test passed.
- Рейтинг team-41: один Diamond, likes=0, rating.value=5 не является likes.

## Исследование официального API

Swagger https://api.sourcecraft.tech/docs/sourcecraft.swagger.json, version 0.0.1,
SHA256 `c3b1d84647cdf553cda63ff6e6ddf59d00ee36a5aa40470ad44607320639d7c3`.
В paths не найдены appsec/sast/vulnerability/sarif/finding/incident/scanning routes.
Это предварительный результат; полный AppSec/CLI review ещё не закончен.
GET /user и GET /orgs/lct-hackaton-2026/repos успешно проверены с локальным PAT;
личные данные и credential не сохранялись.
Документация PAT: https://sourcecraft.dev/portal/docs/en/sourcecraft/operations/api-start.
CLI IAM/PAT: https://sourcecraft.dev/portal/docs/en/cli-ref/src-auth-login.
Delegated Я ID → SourceCraft bridge этими проверками не подтверждён.

## Ограниченная discovery

GET /repos: одна страница, page_size=10, sort_by=created_at; есть следующая страница,
её не обходили. Получены public repositories:

- suzev/advent-test
- appolimp/hello
- sourcecraft/sourcecraft
- mibon2019/test
- fy-demonar/test1
- kamoksin/hello-world
- ellesaify/kitty-new
- sourcecraft/template-docker-image
- sourcecraft/template-node-js
- организация sourcecraft, repository `template-java-with-maven`

Это доказательство catalog API, **не** end-to-end leaderboard/UI/calibration acceptance.

## Второй checkpoint

Реализован SourceCraft PAT connection API/UI: AES-GCM Redis, отдельный ключ,
сессионный TTL, atomic write, logout/disconnect, /user verification, org listing
до 100 элементов с explicit has_more. Private/internal не сохраняются в public DB.
Обновлены OpenAPI и generated TS; добавлены cryptography/cffi/pycparser в server lock.
Это реализация и integration proof, не browser OAuth acceptance.
16 PostgreSQL/Redis integration tests прошли, Alembic upgrade/check прошли.
Frontend typecheck/build прошли. SourceCraft CI перенесён в feature tree без push.

## Продолжение

1. Integration tests import/refresh likes, затем import/discover этих 10 repositories,
   worker-code и 5–10 accept-public; сохранить только безопасные численные результаты.
2. Расширить security tests connection: wrong Origin, malformed PAT no-leak,
   invalid ciphertext, TTL expiry, concurrent logout. Пройти browser acceptance после OAuth setup.
3. Scoring control/calibration, empty issues semantics с новой v1.2; large-repo measurement.
4. AppSec evidence review, security review, SourceCraft CI в feature branch, docs/DEMO.
5. Полный acceptance gate из пользовательского задания, включая integration/Compose/runtime.

OAuth client/secret/callback настроены локально; случайные session/credential keys сгенерированы
в игнорируемом `.env`. HTTP login подтверждает redirect на Яндекс и secure cookie boundary.
Ручной browser acceptance не выполнен из-за отказа browser tooling до открытия страницы;
не подменять его HTTP или тестовой сессией.
PostgreSQL/Redis подняты локально командой `docker compose up -d postgres redis migrate`.
Никакого deployment на сторонний сервер не выполнялось.

Точная следующая проверка: `python -m unittest tests.test_integration -v`
после настройки изолированной `_test` БД и Redis DB 15 по docs/TESTING.md.
Текущий checkpoint можно определить `git log -1 --format=%H`; журнал коммитится
вместе с описанными изменениями, поэтому self-referencing SHA в нём не записывается.

## Closure 21.09.2026

### Scoring v1.2 и контрольные сценарии

`mvp-score-v1.2` устранил два подтверждённых gaming case: полностью пустой issue tracker
остаётся наблюдаемым, но имеет score=null; recent Activity использует минимум нормализованных
commits и active days, поэтому однодневный burst не максимизирует компонент. Policy/version,
coverage, ADR и документация изменены вместе. Deterministic tests покрывают missing data,
улучшение docs, broken/healthy CI, stale/repair Issues, TODO/FIXME и local SAST, official
AppSec severity, второстепенные likes, commit burst и независимость score от масштаба repo.

### Live calibration v1.2

Сохранены только нормализованные числа, без исходников target repositories. `—` означает
недостаточный coverage, а не ноль.

| Repository | Language | Commits | Code files | Health | Coverage | Docs | Issues | CI | Activity | Code |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| appolimp/hello | — | 28 | 0 | — | 30% | 20 | — | — | 6.65 | — |
| ellesaify/kitty-new | — | 1 | 0 | — | 30% | 20 | — | — | 1.67 | — |
| fy-demonar/test1 | TypeScript | 1893 | 987 | 59.91 | 50% | 65 | — | — | 1.67 | 99.77 |
| team-41 | Python | 6 | 125 | 69.35 | 65% | 90 | — | 25 | 55.24 | 97.72 |
| mibon2019/test | Shell | 10 | 1 | 31.15 | 65% | 0 | 0 | — | 1.67 | 100 |
| sourcecraft/sourcecraft | — | 14 | 0 | — | 30% | 20 | — | — | 51.55 | — |
| sourcecraft/template-docker-image | — | 9 | 0 | — | 30% | 20 | — | — | 1.67 | — |
| sourcecraft/java-maven-template | Java | 16 | 2 | 47.00 | 50% | 20 | — | — | 3.33 | 100 |
| sourcecraft/template-node-js | JavaScript | 7 | 1 | 35.77 | 65% | 20 | 0 | — | 1.67 | 100 |
| suzev/advent-test | C++ | 102 | 1 | 53.97 | 50% | 0 | — | — | 46.56 | 100 |

На пустых trackers Issues больше не даёт 100. У четырёх repositories coverage ниже
минимума и общий Health честно null. Security у всей выборки NO_DATA. Абсолютные local SAST
findings пока остаются калибровочным риском для очень больших codebases.

### Live team-41 и RQ repair

`probe-sourcecraft` — exit 0, все collectors complete. Opt-in live contract — passed.
`accept-public` analysis `bf27205e-899f-4a22-902d-dacfe9860a5b` — exit 0,
`overall=ok`, terminal `partial`, SourceCraft HEAD `aa225141a057fb0ad28c49e6bc37409f8d8903fd`,
Health 69.35 и coverage 65%. Partial означает AppSec NO_DATA/неполный набор оценок, а
overall=ok — прохождение acceptance invariants.

Реальный запуск обнаружил orphaned RQ job: DB run был queued, RQ hash имел queued, но ID
исчез из списка очереди после shutdown worker. Dispatcher теперь восстанавливает такую
доставку под per-run Redis lock. Тот же зависший run восстановлен (`enqueued=1`) и завершён;
integration regression добавлен.

### Deployment, OAuth и AppSec

Linux `operation not permitted` устранён: Compose migration и Docker CMD используют
`python -m alembic`/`python -m uvicorn`. Изолированный Compose smoke подтвердил build,
migration, PostgreSQL/Redis/backend health, HTTP 200 и registered worker с cleanup.

OAuth preflight: client/secret/session/callback присутствуют; GET login вернул 302 на
`oauth.yandex.ru`, HttpOnly `sh_oauth` и `no-store`. Browser tool завершился ошибкой
`missing field sandboxPolicy` до открытия страницы, поэтому ручной Я ID flow не принят.

Полный recursive review официального Swagger: 167 paths, версия 0.0.1, SHA256
`c3b1d84647cdf553cda63ff6e6ddf59d00ee36a5aa40470ad44607320639d7c3`; AppSec/SAST/SCA/
vulnerability/SARIF/findings interface не найден. SourceCraft CLI в среде отсутствует.
Security остаётся NO_DATA. От организаторов нужны endpoint, auth/scopes, enums, pagination
и очищенный реальный response; `/secrets` не используется как secret scanning.

### Оставшиеся внешние блокеры

- Ручной browser flow: Я ID → `/me` → SourceCraft connection → public repo → analysis/history/
  evidence/recommendations/Markdown → logout.
- Среди bounded первых 20 public repositories не подтверждён кандидат с ≥10 000 tracked
  files, ≥20 000 commits или ≥500 MB. Наибольший измеренный кандидат имел 1893 commits и
  987 code files, то есть не удовлетворяет порогу.

Нужна авторизация на создание специального SourceCraft large-repo fixture.

### Последний локальный gate

- full unit: 187 tests, OK, 20 expected skips;
- PostgreSQL/Redis/RQ integration: 18 tests, OK;
- Ruff: passed; Alembic upgrade/check: passed;
- OpenAPI export + generated TypeScript diff: clean;
- frontend typecheck/production build: passed;
- offline Docker MVP snapshot smoke: passed;
- disposable Compose build/migrate/health/worker smoke: passed с удалением volumes;
- live probe, opt-in contract и accept-public: passed;
- `git diff --check`: passed.

SourceCraft CI config остаётся в feature branch и не использует PAT: Python 3.11 unit/Ruff/
OpenAPI и Node 24 generated TypeScript/build. Feature tree не отправлялся в SourceCraft main.

### Official AppSec closure 23.09.2026

Отдельный AppSec Swagger `/openapi` и Bearer PAT подтверждены live. Реализованы отдельный
клиент, bounded pagination defect groups, безопасная нормализация severity, run-scoped encrypted
Redis credential и удаление lease после worker. Live probe team-41 вернул finished scan и только
санитизированный агрегат; scoring policy `mvp-score-v1.2` не менялась. Scheduled runs без
пользовательского PAT по-прежнему получают Security `NO_DATA`; private analysis не включён.
