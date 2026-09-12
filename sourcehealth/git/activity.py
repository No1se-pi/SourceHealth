"""Расчёт временных метрик активности по структурированной истории Git."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Any, Iterable

from sourcehealth.git.models import Commit

# Все интервалы в публичных метриках выражаются в днях как float.
# Константа нужна для точного перевода секунд timedelta в дни.
_SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class GitActivityMetrics:
    """Набор временных метрик активности Git-репозитория.

    Даты хранятся как строки ISO 8601 и нормализуются в UTC. Все длительности
    и интервалы между коммитами выражаются в днях. Если для вычисления
    интервала требуется минимум два коммита, а данных недостаточно, поле
    принимает ``None``.

    Объект заморожен (``frozen=True``), чтобы результат анализа нельзя было
    случайно изменить после расчёта.
    """

    # Общая информация об истории.
    total_commits: int
    first_commit_date: str | None
    last_commit_date: str | None

    # Возраст истории и время с последней активности, в днях.
    repository_age: float | None
    days_since_last_commit: float | None

    # Статистика интервалов между соседними коммитами, в днях.
    min_commit_gap: float | None
    max_commit_gap: float | None
    mean_commit_gap: float | None
    median_commit_gap: float | None

    # Количество коммитов в скользящих временных окнах относительно `now`.
    commits_last_7_days: int
    commits_last_30_days: int
    commits_last_90_days: int
    commits_last_180_days: int
    commits_last_365_days: int

    # Количество уникальных календарных дней с хотя бы одним коммитом.
    unique_active_days: int
    active_days_last_30_days: int
    active_days_last_90_days: int
    active_days_last_365_days: int

    # Число активных календарных месяцев среди текущего и 11 предыдущих.
    active_months_last_12_months: int

    # Усреднённые показатели интенсивности разработки.
    average_commits_per_active_day: float
    average_commits_per_month: float

    # Самый большой интервал между двумя соседними коммитами, в днях.
    longest_inactivity_period: float | None

    def to_dict(self) -> dict[str, Any]:
        """Вернуть словарь, пригодный для последующей JSON-сериализации."""

        return asdict(self)


class GitActivityAnalyzer:
    """Рассчитать временные метрики по уже собранным объектам ``Commit``.

    Анализатор не запускает Git и не обращается к файловой системе. Благодаря
    этому его можно независимо тестировать и использовать с любым источником,
    который способен сформировать модели ``Commit``.
    """

    # Окна, для которых считаем количество недавних коммитов.
    _WINDOWS = (7, 30, 90, 180, 365)

    def analyze(
        self,
        commits: Iterable[Commit],
        *,
        now: datetime | None = None,
    ) -> GitActivityMetrics:
        """Рассчитать метрики активности.

        Args:
            commits: Любой итерируемый набор нормализованных коммитов.
            now: Опорное текущее время. Если не передано, используется текущее
                время UTC. Параметр существует в том числе ради детерминированных
                тестов.

        Returns:
            Заполненный объект ``GitActivityMetrics``.

        Raises:
            ValueError: Если ``now`` или время какого-либо коммита не содержит
                информации о часовом поясе.
        """

        # Сначала приводим точку отсчёта к UTC. Нельзя смешивать timezone-aware
        # и naive datetime: сравнение таких значений неоднозначно.
        current_time = now or datetime.now(UTC)
        self._require_aware(current_time, "now")
        current_time = current_time.astimezone(UTC)

        # Коммиты могут прийти в любом порядке и из разных часовых поясов.
        # Нормализуем каждый момент в UTC, а затем сортируем по абсолютному времени.
        commit_times: list[datetime] = []
        for commit in commits:
            self._require_aware(commit.datetime, "commit datetime")
            commit_times.append(commit.datetime.astimezone(UTC))
        commit_times.sort()

        # Пустой репозиторий — валидный сценарий. Возвращаем объект с нулевыми
        # счётчиками и None там, где метрику физически невозможно вычислить.
        if not commit_times:
            return self._empty_metrics()

        first = commit_times[0]
        last = commit_times[-1]

        # Разности считаются только между соседними коммитами в хронологическом
        # порядке. Для одного коммита список gaps останется пустым.
        gaps = [
            self._days(later - earlier)
            for earlier, later in zip(commit_times, commit_times[1:])
        ]

        # Формируем показатели для всех стандартных окон. Границы включаются:
        # [now - N дней, now].
        commit_counts = {
            days: self._commits_in_window(commit_times, current_time, days)
            for days in self._WINDOWS
        }

        # Активный день считается один раз независимо от количества коммитов.
        active_days = {
            days: self._active_days_in_window(commit_times, current_time, days)
            for days in (30, 90, 365)
        }

        # Набор используется и как количество всех активных дней за историю,
        # и как знаменатель для среднего числа коммитов на активный день.
        unique_days = {commit_time.date() for commit_time in commit_times}

        # Среднее по месяцам считается по календарным месяцам включительно:
        # например, январь -> март означает три месяца: январь, февраль, март.
        lifetime_months = self._months_inclusive(first, last)

        return GitActivityMetrics(
            total_commits=len(commit_times),
            first_commit_date=first.isoformat(),
            last_commit_date=last.isoformat(),
            # repository_age — интервал между первым и последним коммитом,
            # а не время от первого коммита до сегодняшней даты.
            repository_age=self._days(last - first),
            days_since_last_commit=self._days(current_time - last),
            min_commit_gap=min(gaps) if gaps else None,
            max_commit_gap=max(gaps) if gaps else None,
            mean_commit_gap=mean(gaps) if gaps else None,
            median_commit_gap=median(gaps) if gaps else None,
            commits_last_7_days=commit_counts[7],
            commits_last_30_days=commit_counts[30],
            commits_last_90_days=commit_counts[90],
            commits_last_180_days=commit_counts[180],
            commits_last_365_days=commit_counts[365],
            unique_active_days=len(unique_days),
            active_days_last_30_days=active_days[30],
            active_days_last_90_days=active_days[90],
            active_days_last_365_days=active_days[365],
            active_months_last_12_months=self._active_months_last_12_months(
                commit_times, current_time
            ),
            average_commits_per_active_day=len(commit_times) / len(unique_days),
            average_commits_per_month=len(commit_times) / lifetime_months,
            # На текущем этапе longest_inactivity_period совпадает с max_commit_gap.
            # Отдельное поле оставлено как семантически понятная метрика API.
            longest_inactivity_period=max(gaps) if gaps else None,
        )

    @staticmethod
    def _empty_metrics() -> GitActivityMetrics:
        """Сформировать результат для репозитория без коммитов."""

        return GitActivityMetrics(
            total_commits=0,
            first_commit_date=None,
            last_commit_date=None,
            repository_age=None,
            days_since_last_commit=None,
            min_commit_gap=None,
            max_commit_gap=None,
            mean_commit_gap=None,
            median_commit_gap=None,
            commits_last_7_days=0,
            commits_last_30_days=0,
            commits_last_90_days=0,
            commits_last_180_days=0,
            commits_last_365_days=0,
            unique_active_days=0,
            active_days_last_30_days=0,
            active_days_last_90_days=0,
            active_days_last_365_days=0,
            active_months_last_12_months=0,
            average_commits_per_active_day=0.0,
            average_commits_per_month=0.0,
            longest_inactivity_period=None,
        )

    @staticmethod
    def _require_aware(value: datetime, name: str) -> None:
        """Отклонить ``datetime`` без корректной информации о часовом поясе."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")

    @staticmethod
    def _days(value: timedelta) -> float:
        """Преобразовать ``timedelta`` в дробное количество суток."""

        return value.total_seconds() / _SECONDS_PER_DAY

    @classmethod
    def _commits_in_window(
        cls, commit_times: list[datetime], now: datetime, days: int
    ) -> int:
        """Посчитать коммиты в закрытом интервале ``[now - days, now]``."""

        start = now - timedelta(days=days)
        return sum(start <= commit_time <= now for commit_time in commit_times)

    @classmethod
    def _active_days_in_window(
        cls, commit_times: list[datetime], now: datetime, days: int
    ) -> int:
        """Посчитать уникальные календарные дни с коммитами в заданном окне."""

        start = now - timedelta(days=days)
        return len(
            {
                commit_time.date()
                for commit_time in commit_times
                if start <= commit_time <= now
            }
        )

    @staticmethod
    def _active_months_last_12_months(
        commit_times: list[datetime], now: datetime
    ) -> int:
        """Посчитать активные месяцы среди текущего и 11 предыдущих месяцев."""

        # Линейный номер месяца упрощает сравнение на границах годов:
        # декабрь 2025 и январь 2026 становятся соседними целыми числами.
        current_month = now.year * 12 + now.month - 1
        first_included_month = current_month - 11

        return len(
            {
                commit_time.year * 12 + commit_time.month - 1
                for commit_time in commit_times
                if first_included_month
                <= commit_time.year * 12 + commit_time.month - 1
                <= current_month
                # Коммит из будущего внутри текущего календарного месяца
                # не должен считаться активностью относительно заданного `now`.
                and commit_time <= now
            }
        )

    @staticmethod
    def _months_inclusive(first: datetime, last: datetime) -> int:
        """Вернуть число календарных месяцев между датами включительно."""

        return (last.year - first.year) * 12 + last.month - first.month + 1
