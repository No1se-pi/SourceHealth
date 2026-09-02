"""Сбор структурированной истории коммитов из локального Git-репозитория."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from sourcehealth.git.models import Commit


class GitCollectionError(RuntimeError):
    """Ошибка, возникшая при чтении истории репозитория через Git."""


class GitCollector:
    """Получить и нормализовать историю Git без расчёта метрик.

    Коллектор отвечает только за взаимодействие с исполняемым файлом Git и
    преобразование его вывода в список ``Commit``. Расчёт показателей намеренно
    вынесен в отдельные анализаторы.
    """

    # NUL (0x00) выбран разделителем полей, потому что обычные переводы строк
    # встречаются внутри многострочных сообщений коммитов и не подходят
    # для надёжного разделения записей.
    _FIELD_SEPARATOR = "\x00"

    # В пользовательском формате git log на один коммит выводится ровно
    # пять полей: hash, имя автора, email, дата и полное сообщение.
    _FIELDS_PER_COMMIT = 5

    # %H  — полный SHA;
    # %an — имя автора;
    # %ae — email автора;
    # %aI — строгая ISO 8601 дата автора с часовым поясом;
    # %B  — полное сообщение коммита.
    _LOG_FORMAT = "%H%x00%an%x00%ae%x00%aI%x00%B"

    def __init__(self, git_executable: str = "git") -> None:
        """Создать коллектор.

        Args:
            git_executable: Имя или путь к исполняемому файлу Git. Параметр
                полезен для тестов и нестандартных установок Git.
        """

        self._git_executable = git_executable

    def collect(self, repo_path: str | Path) -> list[Commit]:
        """Собрать коммиты, достижимые из текущего ``HEAD`` репозитория.

        Git запускается с ``cwd=repo_path``. Никакие временные файлы с логом
        не создаются: весь вывод читается напрямую из stdout.

        Args:
            repo_path: Путь к локальному Git-репозиторию.

        Returns:
            Список ``Commit`` в порядке, который вернул ``git log``.
            Инициализированный репозиторий без единого коммита возвращает
            пустой список.

        Raises:
            GitCollectionError: Если путь некорректен, каталог не является
                Git-репозиторием, Git недоступен или вернул неожиданный вывод.
        """

        # expanduser() позволяет корректно обрабатывать пути вида ~/project.
        path = Path(repo_path).expanduser()
        if not path.is_dir():
            raise GitCollectionError(f"Repository path is not a directory: {path}")

        # Сначала отдельно проверяем сам факт существования Git-репозитория.
        # Это даёт более понятную ошибку, чем последующий вызов git log.
        self._ensure_repository(path)

        # У только что созданного `git init` ещё нет HEAD. Это нормальный
        # пустой репозиторий, а не ошибка коллектора.
        if not self._has_head(path):
            return []

        # -z добавляет NUL-разделитель между записями git log.
        # Внутри каждой записи NUL также используется в _LOG_FORMAT,
        # поэтому парсер не зависит от локали и многострочных сообщений.
        result = self._run_git(
            path,
            "-c",
            "i18n.logOutputEncoding=UTF-8",
            "log",
            "-z",
            "--no-show-signature",
            f"--format={self._LOG_FORMAT}",
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown Git error"
            raise GitCollectionError(f"Unable to read Git history: {detail}")

        return self._parse_log(result.stdout)

    def _ensure_repository(self, path: Path) -> None:
        """Убедиться, что каталог доступен Git как репозиторий."""

        result = self._run_git(path, "rev-parse", "--git-dir")
        if result.returncode != 0:
            detail = result.stderr.strip() or "not a Git repository"
            raise GitCollectionError(f"Unable to use repository at {path}: {detail}")

    def _has_head(self, path: Path) -> bool:
        """Проверить наличие хотя бы одного коммита через существование HEAD."""

        result = self._run_git(path, "rev-parse", "--verify", "HEAD")
        return result.returncode == 0

    def _run_git(self, path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Запустить Git в указанном репозитории и вернуть завершённый процесс.

        ``check=False`` используется намеренно: код выше сам интерпретирует
        коды возврата и преобразует их в понятные ``GitCollectionError``.
        """

        try:
            return subprocess.run(
                [self._git_executable, *arguments],
                cwd=path,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                # Повреждённая последовательность байтов не должна полностью
                # ломать сбор истории: проблемные символы заменяются.
                errors="replace",
            )
        except FileNotFoundError as error:
            raise GitCollectionError(
                f"Git executable was not found: {self._git_executable}"
            ) from error
        except OSError as error:
            raise GitCollectionError(f"Unable to start Git: {error}") from error

    @classmethod
    def _parse_log(cls, output: str) -> list[Commit]:
        """Преобразовать NUL-разделённый вывод ``git log`` в модели ``Commit``."""

        if not output:
            return []

        fields = output.split(cls._FIELD_SEPARATOR)

        # Из-за `git log -z` вывод обычно завершается разделителем. После split
        # он превращается в лишнюю пустую строку, которую нужно удалить.
        if fields[-1] == "":
            fields.pop()

        # Любое другое количество полей означает, что формат вывода отличается
        # от ожидаемого и данные нельзя безопасно сопоставить с Commit.
        if len(fields) % cls._FIELDS_PER_COMMIT != 0:
            raise GitCollectionError("Git returned an unexpected log format")

        commits: list[Commit] = []

        # Идём блоками по пять полей — один такой блок соответствует коммиту.
        for index in range(0, len(fields), cls._FIELDS_PER_COMMIT):
            commit_hash, author_name, author_email, raw_datetime, message = fields[
                index : index + cls._FIELDS_PER_COMMIT
            ]

            # %aI возвращает ISO 8601 со смещением часового пояса, поэтому
            # datetime.fromisoformat сохраняет timezone-aware значение.
            try:
                commit_datetime = datetime.fromisoformat(raw_datetime)
            except ValueError as error:
                raise GitCollectionError(
                    f"Git returned an invalid commit datetime: {raw_datetime!r}"
                ) from error

            commits.append(
                Commit(
                    hash=commit_hash,
                    author_name=author_name,
                    author_email=author_email,
                    datetime=commit_datetime,
                    # Git добавляет завершающий перевод строки к %B.
                    # Убираем только его, не изменяя внутреннюю структуру текста.
                    message=message.rstrip("\n"),
                )
            )

        return commits
