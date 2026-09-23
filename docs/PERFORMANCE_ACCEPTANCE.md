# Performance и anti-size-skew acceptance

Проверка выполнена 2026-09-23 на ветке `feature/final-mvp-100-closure` после перехода на `mvp-score-v1.3`.

## Локальный benchmark

`/tmp/sourcehealth-large-benchmark-v13.json` сравнивает один и тот же fixture с 120 и 10 000 файлами, а также safety boundary 10 001 файл.

| Сценарий | code files analyzed | findings | Health | code_health | status | время |
|---|---:|---:|---:|---:|---|---:|
| 120 файлов | 100 | 2 | 80.89 | 95.35 | complete | 0.122 s |
| 10 000 файлов | 100 | 2 | 80.89 | 95.35 | complete | 4.976 s |
| 10 001 файл | 100 | 2 | — | — | partial, `file_limit` | 5.038 s |

Размер нейтральных данных не меняет code-health и Health. При превышении bounded budget результат становится partial без подмены отсутствующих данных нулём. Scanner сохраняет `max_files=10000`, `max_entries=100000`, `max_total_bytes=512 MiB`, `max_findings=1000` и timeout.

## Реальный SourceCraft large run

Публичный fixture: `https://sourcecraft.dev/yaromirfominyh/sourcehealth-large-fixture`, HEAD `a0919aa50c63a818fc9d34997a2feb2076af3749`, 10 000 tracked files, 1 commit, 810 405 bytes. В полном pipeline v1.3: clone 7.599 s, analysis 3.595 s, total 10.761 s (wrapper wall 11.823 s), max RSS 97 508 KiB. Временные containers/volumes после успешного запуска и timeout probe отсутствуют.

Изменение v1.3 нормализует local SAST по числу проанализированных code files (`code_files_analyzed`), поэтому local SAST остаётся `code_health`, а официальный Security по-прежнему получает только SourceCraft AppSec данные.
