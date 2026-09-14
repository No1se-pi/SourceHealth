# Методика оценки и её границы

Численная production-методика **ещё не утверждена**. Текущий UnconfiguredPolicy version
unconfigured-v1 возвращает шесть CategoryScore и health_score=null. Это сознательный
контракт foundation: наличие работающей очереди не должно создавать fake число.

## Контракт

ScoringPolicy имеет version и evaluate(results) → ScoreResult. ScoringEngine проверяет
полный набор категорий, version, допустимость диапазона 0–100 и evidence references.
CategoryScore включает nullable score, availability, explanation и evidence_refs.
Численная оценка требует evidence; NaN/Infinity и неизвестные refs недопустимы.
Health Score требует хотя бы одной рассчитанной категории; минимально достаточный
охват и веса должны быть частью будущей policy, а не незаметным default engine.

Security inputs фильтруются по source=sourcecraft_appsec. Численная Security category
должна ссылаться на evidence из соответствующего SourceCraft result. `sast` с source
sourcehealth_local не становится официальным AppSec даже при одинаковых severity.
Доверенные адаптеры отвечают за честность source metadata; недоверенный repo не может
назначать себе source или загружать analyzer code.

## Доступность

NO_DATA, SOURCE_UNAVAILABLE, ERROR, NOT_APPLICABLE не превращаются в Score=0.
NOT_CONFIGURED может быть фактом и штрафоваться только явно описанным правилом.
PARTIAL может иметь осторожный Score только если policy объясняет границы охвата;
часть результатов не следует автоматически масштабировать до полного репозитория.
Полный пустой набор уязвимостей и неудачный запрос AppSec — разные ситуации.

## Требования к первой численной policy

1. Для каждой метрики — units, окно, transform/normalization, ограничения и provenance.
2. Для каждой категории — формула, веса, handling missing/partial, score explanation.
3. Для итогового Score — агрегация, минимальный coverage и правила исключений.
4. Проверить независимые сценарии security/CI/docs/activity/issues/code health:
   существенная проблема снижает Score, исправление повышает, outage не наказывает проект.
5. Проверить устойчивость к пустым commits, likes и второстепенным счётчикам.
6. Сохранить policy version и всё необходимое для воспроизведения старого результата.

Пример весов исходного ТЗ не включён автоматически. Popularity — отдельное поле
рейтинга, не Health. ML residual/context может помогать сравнивать проекты, но базовая
детерминированная оценка должна работать без ML/LLM и сетевого запроса.

## Versioning и повторный расчёт

Finished report хранит analyzer versions, facts, timestamps, policy version и evidence.
Новая формула получает новую version и новый fingerprint run/profile. Старые reports
не переписываются. Сначала сравнить policy на одних и тех же fixtures/сохранённых inputs,
потом включать её в application profile. Точность обещанных expected impact рекомендаций
проверяется тем же deterministic replay, а не оценкой LLM.
