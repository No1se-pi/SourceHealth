# SourceHealth: работа в этом репозитории

Перед существенными изменениями прочитать docs/README.md, docs/ARCHITECTURE.md,
docs/DEVELOPMENT.md и соответствующий docs/adr. Проверить git status/diff и сохранить
чужие изменения. Цель — modular monolith, независимая работа трёх участников.

- Существующие Git/scanner/CLI/SARIF APIs и meaningful comments сохранять.
- Core, HTTP DTO и migrations — общая зона: изменение объяснять и согласовывать в PR.
  Явная задача пользователя на изменение этих границ является рабочим основанием;
  не создавать повторный approval flow для уже порученной работы.
- Analyzer не обращается к DB/queue/frontend; scoring не выполняет I/O.
- Security получает evidence только из SourceCraft AppSec, local SAST — code_health.
- NO_DATA не равно 0. Неподтверждённые endpoints/auth bridge не придумывать.
- Документация на русском, обновляется в том же изменении, что и код.
- Не хранить/логировать PAT, OAuth token, secret values или source snippets.
- Использовать unittest; команды и integration setup — docs/TESTING.md.
- Нельзя выдавать unit mocks/build за live SourceCraft, OAuth или browser acceptance.
- Не push напрямую в стабильную ветку. Не менять архитектуру ради нового анализатора.
