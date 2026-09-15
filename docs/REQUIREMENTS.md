# Требования и границы текущего этапа

Источник продуктовых требований: «8. Yandex Cloud.pdf», 21 страница, ТЗ ЛЦТ 2026.
Номера ниже — разделы исходного ТЗ. Приложенный архитектурный промпт задаёт объём
foundation-работы, но не заменяет исходные требования к финальной сдаче.

## Матрица соответствия

| Требование ТЗ | Компоненты | Сейчас | Приёмка следующего этапа |
|---|---|---|---|
| 3.1 Documentation / best practices | collectors + documentation analyzer | Planned | README, LICENSE, запуск/сборка/тесты с file evidence |
| 3.1 CI/CD | SourceCraft client + CI collector/analyzer | Foundation клиента | Метрики реальных прогонов, пустой список не выдаётся за отсутствие CI |
| 3.1 Security | отдельный AppSec collector + security analyzer | Boundary, NO_DATA | Реальные SAST/SCA/secrets findings, severity и resolution из AppSec |
| 3.1 Activity | GitCollector, GitActivityAnalyzer, adapter | Работает локально | Подключить безопасный runtime к фоновому профилю; MR/releases/contributors через API |
| 3.1 Issues | SourceCraft client pagination + будущий analyzer | Foundation | Open/closed, зависшие задачи; объяснить окна наблюдений |
| 3.1 Code health / debt | local SAST + новые code analyzers | SAST работает локально | TODO/FIXME/сложность и debt evidence; SAST не подменяет AppSec |
| 3.2 Score 0–100 | ScoringEngine / ScoringPolicy | Контракт, null Score | Версионированная формула, веса, нормализация, контрольные сценарии |
| 3.3 Рекомендации | Recommendation / evidence_refs / rule protocol | Контракт | Каждое правило показывает факт, приоритет, действие и воспроизводимый эффект |
| 3.4 Страница анализа | FastAPI DTO, React routes | Foundation | Шесть категорий, сильные/слабые стороны, переход к evidence |
| 4 Публичный рейтинг | repositories, индексы, API, React | Список реальной БД и sort | Наполнение публичным каталогом, язык, лайки, активность, шкала Score |
| 5 Я ID и собственный репозиторий | auth + будущая SourceCraft authorization | Я ID flow реализован; bridge открыт | Реальный вход, список доступных repo, проверка прав на каждом действии |
| 6 Регулярный анализ | enqueue-due, RQ, PostgreSQL | Команда реализована | Cron каждую минуту, демонстрация первого/повторного run |
| Markdown или PDF | markdown renderer + HTTP download | Markdown реализован | Сравнить отчёт с API по одному analysis_id |
| 9.2 Большие repo | существующий sandbox + лимиты | Локальный runtime, ограничение истории описано | Реальный SourceCraft repo ≥10 000 tracked files ИЛИ ≥20 000 commits ИЛИ ≥500 МБ |
| 9.2 Масштабирование | stateless API, shared PG/Redis, RQ workers | Foundation | Несколько workers; десять конкурентных запросов → один run |
| 9.2 Приватность | deny-by-default visibility, public-only API | Закрытые repo запрещены | ACL bridge + scoped caches до включения private flow |
| 9.5 Документация | docs + ADR + runnable commands | Подготовлена | Новый участник запускает сервис и добавляет анализатор по инструкциям |

## Что исходное ТЗ НЕ навязывает

FastAPI, React, PostgreSQL, Redis/RQ — наши архитектурные решения. ТЗ не фиксирует
стек. Пример весов Security 20%, Activity 15%, Documentation 15%, CI 15%, Issues 15%,
Code health 20% является ориентиром, а не обязательной формулой. Сейчас эти веса
не включены в код: пустая реализация не должна генерировать правдоподобный Score.

## Приоритет сдачи

Обязательные сценарии важнее AI/ML, badges, истории рейтинга и защиты от накрутки.
ТЗ оценивает работающий продукт на 35 баллов, аналитику на 30, UX на 15,
демонстрацию на 15 и презентацию на 5. До 5 бонусных баллов доступны лишь после
обязательных сценариев. Синтетические test fixtures не заменяют демонстрацию на SourceCraft.

Для финальной сдачи нужны репозиторий **в SourceCraft**, демонстрационный URL,
презентация, видео, документация запуска, методика и экспортируемые примеры отчётов.
Текущий GitHub checkout — рабочая площадка команды; публикация и стенд ещё не выполнены.

## Проверка полноты перед демо

1. Публичный рейтинг содержит настоящие репозитории и время актуальности.
2. Score воспроизводится из сохранённого report и версии policy.
3. NO_DATA, плохой результат и неполный анализ различимы.
4. Security использует AppSec SourceCraft; нет замены локальным сканером.
5. Вход Я ID и доступ к своему repo проверены сквозным сценарием.
6. Первый и повторный запуск, восстановление очереди и выгрузка работают.
7. Большой repo соответствует хотя бы одному порогу; метод проверки размера описан.
8. Нет временной копии исходников после runtime cleanup и секретов в отчётах.
