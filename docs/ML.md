# ML и optional AI

ML — дополнительный analytical layer. Базовая оценка детерминирована и должна
работать без модели. Сейчас scikit-learn/LLM SDK не добавлены: реализованы только
ContextModel и EvidenceExplainer Protocol в `sourcehealth/ml/contracts.py`.

## Эксперименты по порядку

| Эксперимент | Вход | Выход | Как проверять |
|---|---|---|---|
| Context / expected metrics | Возраст/размер/язык/тип, numeric features | Ожидаемые значения метрик | Разделение train/test по repository, temporal holdout |
| Regression / Poisson | Counts + exposure window | Expected count/rate | Проверить overdispersion, калибровку, baseline |
| Residual normalization | Observed - expected | Сопоставимый residual | Малые/молодые repo не штрафуются автоматически |
| Repository fingerprint | Стандартизованные features | Versioned vector | Missingness mask, drift и leakage |
| PCA / clustering | Fingerprint | Peer groups / low-dimensional view | Устойчивость групп, explained variance, интерпретация |
| Peer comparison | Repo + похожая группа | Относительное положение | Не сравнивать учебный проект с большим SDK без контекста |

## Границы model function

Только `dict[str, float | None]`/подготовленные массивы, версия модели и предсказание.
Нет clone, Docker, SQL queries, очереди, auth и HTTP внутри predict. Missing feature
не равен 0; правила imputation фиксируются вместе с моделью. Feature extraction и
train/eval datasets версионировать отдельно. Popularity/likes не являются label Health.

Не обучаться на случайных выставленных нами Scores и затем объявлять модель
независимой проверкой. Контроль leakage: будущая активность не может попадать во
входы прошлого snapshot. Нужны baseline, метрики качества и описание ограничений.
Новый dependency добавляется вместе с первым runnable experiment и test/eval artifact.

## LLM / AI

План: понятное summary, объяснение уже сформированных рекомендаций, documentation
drift. EvidenceExplainer принимает structured Evidence. LLM не меняет Score и не
получает права исполнять инструменты/инструкции из README/code/comments. Repository
text рассматривается как untrusted input, включая prompt injection.

До передачи внешнему сервису решить лицензии/конфиденциальность и минимизацию данных.
Private source/secret findings нельзя отправлять автоматически. Проверять groundedness:
каждый существенный вывод связан с существующим evidence, выдуманные ссылки отклоняются.
AI функции не включены в current production flow и не заменяют обязательную часть ТЗ.
