# Large repository: подготовка и evidence

Дата: 22.09.2026. Base SourceHealth:
`11151e4fb2c3341b97a05b00c0afed87dad5ddf4` + generator/benchmark scripts этого изменения.

**Live status: BLOCKED — SourceCraft PAT не настроен в текущем окружении.**
Один запрос официального `GET https://api.sourcecraft.tech/repos` с `page_size=20`,
`sort_by=created_at`, timeout=10, общим budget=30 секунд без PAT вернул
`authentication_required`. Страницы дальше не обходились, кандидаты не клонировались.
Это ограничение доступа текущего запуска, а не доказательство отсутствия large repos.

## Генератор

```bash
python scripts/generate_large_sourcecraft_fixture.py /tmp/sourcehealth-large-fixture
```

Destination должен не существовать и находиться вне SourceHealth. Генератор не
обращается к сети, не публикует repository, не выполняет target code. Создаёт ровно
10 000 tracked files: 100 Python modules, 9 docs/metadata files и 9891 neutral text
records. Два контролируемых `eval`, два TODO/FIXME; credentials не генерируются.
Фиксированы seed, Git author/committer/date, main branch и SHA-1 object format;
внешняя Git configuration/hooks/signing отключены. Детерминизм проверен на двух
независимых дешёвых fixtures в unittest. Summary не содержит абсолютного пути.

`--files 10001` проверяет границу safety budget. Допустимый диапазон CLI —
10 000–100 000. Обычный unit suite не создаёт 10k файлов.

Итог локального fixture текущей версии генератора:

| Поле | Значение |
|---|---|
| SourceCraft URL | Не создан / не выбран |
| Fixture HEAD | `a0919aa50c63a818fc9d34997a2feb2076af3749` |
| Tracked files | 10 000 |
| Commits | 1 |
| Working copy bytes | 810 405 (сумма tracked file bytes, без `.git`) |
| Порог | ≥10 000 tracked files локально; на SourceCraft пока не подтверждён |
| Live probe / full pipeline | NOT RUN |
| Live clone / analysis duration | NOT MEASURED |
| Live Health / coverage / cleanup | NOT ACCEPTED |

В benchmark fixtures создаются во временной директории и удаляются при выходе.
Для ручной публикации нужно заново выполнить генератор с отдельным destination.
Публикация разрешается только после явного согласия владельца; сначала повторить
bounded discovery с PAT и проверить несколько разумных существующих кандидатов.

## Локальная проверка границы

```bash
python -m scripts.large_repository_benchmark
```

Это **локальная synthetic проверка**, без API, RQ, PostgreSQL и Docker. Platform
facts отсутствуют: CI/Issues/Security остаются NO_DATA, Activity partial. Reference
time фиксирован: 2026-09-19 UTC. Policy `mvp-score-v1.2`. Это не acceptance live
репозитория и не замена полного Phase C. Измерение на Python 3.14.7:

| Files | Git, s | Snapshot/blame, s | SAST, s | Total, s | Report bytes | Health | Code Health | Coverage |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 120 | 0.0136 | 0.0543 | 0.051520 | 0.1270 | 12 237 | 82.31 | 98.91 | 50% |
| 10 000 | 0.0135 | 1.3295 | 3.875462 | 5.2259 | 12 243 | 82.31 | 98.91 | 50% |
| 10 001 | 0.0186 | 1.4142 | 3.994897 | 5.4351 | 11 939 | null | null | 15% |

Serialization: 0.0011–0.0013 s. Во всех трёх случаях 2 findings, 2 уникальных
координаты/rule combinations; source snippets отсутствуют. На 10 001 scanner
прочитал ровно 10 000 файлов, сообщил `file_limit=1`, complete=false. Snapshot
тоже partial; отсутствие оценки не превращено в 0. Лимиты не менялись.

**Наблюдение для Phase C:** Python-only fixture имеет `python_files_parsed=2`,
`code_files_lexed=0`, хотя два AST findings присутствуют. Текущая policy включает
SAST-компонент только при `code_files_lexed>0`. Поэтому совпадение Health этой
пары не доказывает независимость штрафа SAST от размера или корректность его
участия для Python. Нужны отдельные regressions и проверка density перед решением
о policy v1.3. Также ещё не измерены finding_limit=1000 и live false positives.

## Продолжение live-приёмки

1. Владелец задаёт PAT в локальном игнорируемом `.env`, не в чате/PR.
2. Повторить bounded discovery (до 20 metadata records, до 3 обоснованных clones).
3. Если нет кандидата — запросить разрешение на отдельный public fixture repo.
4. На реальном SourceCraft URL подтвердить HEAD, tracked files, commits и размер.
5. `probe-sourcecraft`, затем `accept-public URL --timeout 1800` на `mvp-v1` с
   trusted worker-code и `sourcehealth-sast`. Не снимать runtime bounds;
   `ANALYSIS_TIMEOUT >= 2 * CODE_RUNTIME_TIMEOUT + 180`.
6. Измерить clone/analysis/total, terminal/coverage/Health/categories; сохранить
   только safe aggregates. До/после сверить принадлежащие run containers/volume,
   отдельно проверить timeout cleanup. SIGKILL оркестратора не покрыт finally.

Исторические 10 live calibration cases остаются в [MANDATORY_100_CLOSURE](MANDATORY_100_CLOSURE.md).
Этот local fixture не добавлен в таблицу как одиннадцатый live case.
