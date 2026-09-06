"""Анализ реальных Python-вызовов без импорта/исполнения проверяемого кода.

AST устраняет совпадения в комментариях и строках, поддерживает многострочные
вызовы и import aliases. Разрешение имён консервативное, без исполнения и SSA:
переопределённый символ не считается исходной библиотечной функцией.
Это не межфайловый анализ потоков данных и не полноценная система типов.
"""

from __future__ import annotations

import ast
import time
import warnings
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .rules import Rule


@dataclass
class PythonAnalysis:
    """Внутренний результат; только правило и координаты, без AST и исходников."""

    hits: list[tuple[Rule, int, int]] = field(default_factory=list)
    parsed: bool = False
    reason: str | None = None
    line: int | None = None


def _argument(call: ast.Call, selector: str | int | None) -> ast.AST | None:
    """Прочитать явный аргумент; *args/**kwargs не вычисляются."""
    if type(selector) is int:
        if selector < len(call.args) and not any(isinstance(a, ast.Starred) for a in call.args[:selector + 1]):
            return call.args[selector]
        return None
    return next((keyword.value for keyword in call.keywords if keyword.arg == selector), None)


def _literal(node: ast.AST | None, value: object) -> bool:
    """Сравнить точный литерал; True и 1 намеренно считаются разными значениями."""
    return isinstance(node, ast.Constant) and type(node.value) is type(value) and node.value == value


def _formatted_sql(node: ast.AST | None) -> bool:
    """Найти форматирование SQL прямо в execute, без предположений о taint.

    Параметризованный execute('SELECT ... WHERE id=?', [value]) не срабатывает.
    Нужны одновременно динамическая вставка и SQL-глагол в начале литерала.
    """
    prefix = None
    if isinstance(node, ast.JoinedStr) and any(isinstance(v, ast.FormattedValue) for v in node.values):
        prefix = node.values[0] if node.values else None
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
        if not isinstance(node.right, ast.Constant):
            prefix = node.left
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        if node.args or node.keywords:
            prefix = node.func.value
    if not isinstance(prefix, ast.Constant) or not isinstance(prefix.value, str):
        return False
    return prefix.value.lstrip().upper().startswith(("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "WITH ", "REPLACE "))


class _CallVisitor(ast.NodeVisitor):
    """Обойти AST с таблицами импортов и локальных затенений для каждой области."""

    # Только известные фабрики: нельзя приписывать тип результату любого вызова.
    _FACTORIES = {"requests.Session", "requests.session", "httpx.Client", "httpx.AsyncClient",
                  "flask.Flask", "jinja2.Environment", "tarfile.open"}

    def __init__(self, rules: tuple[Rule, ...], lines: list[str], result: PythonAnalysis,
                 deadline: float, max_findings: int) -> None:
        self.lines = lines
        self.result = result
        self.deadline = deadline
        self.max_findings = max_findings
        self.scopes: list[dict[str, str | None]] = []
        self.by_name: dict[str, list[Rule]] = {}
        self.by_method: dict[str, list[Rule]] = {}
        self.visited = 0
        for rule in rules:
            for name in rule.calls:
                index = self.by_method if name.startswith("*.") else self.by_name
                index.setdefault(name[2:] if name.startswith("*.") else name, []).append(rule)

    def visit(self, node: ast.AST) -> None:
        """Остановить обход по лимиту; проверять часы раз в 128 узлов."""
        if self.result.reason:
            return
        self.visited += 1
        if self.visited % 128 == 0 and time.monotonic() >= self.deadline:
            self.result.reason = "timeout"
            return
        super().visit(node)

    def qualified(self, node: ast.AST, local: dict[str, str | None] | None = None) -> str | None:
        """Разрешить a.b.c с учётом imports; неизвестный объект не получает тип."""
        suffix = []
        while isinstance(node, ast.Attribute):
            suffix.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        scopes = [*self.scopes, local] if local is not None else self.scopes
        name = node.id
        for scope in reversed(scopes):
            if name in scope:
                name = scope[name]
                if name is None:
                    return None
                break
        return ".".join([name, *reversed(suffix)])

    def bindings(self, body: list[ast.AST], arguments: ast.arguments | None = None) -> dict[str, str | None]:
        """Собрать локальные имена, не заходя в дочерние функции/классы.

        Анализ всей области заранее учитывает затенение даже присваиванием ниже
        вызова. В спорных случаях символ теряет библиотечный тип: это уменьшает
        ложные срабатывания, но может пропустить вызовы до переопределения.
        """
        bindings: dict[str, str | None] = {}
        stores: dict[str, int] = {}
        assignments: list[ast.Assign | ast.AnnAssign] = []
        pending = list(body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stores[node.name] = stores.get(node.name, 0) + 1
                continue
            if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    resolved = alias.name if alias.asname else name
                    bindings[name] = resolved if name not in bindings or bindings[name] == resolved else None
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    resolved = f"{node.module}.{alias.name}" if not node.level else None
                    bindings[name] = resolved if name not in bindings or bindings[name] == resolved else None
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                stores[node.id] = stores.get(node.id, 0) + 1
            elif isinstance(node, ast.ExceptHandler) and node.name:
                stores[node.name] = stores.get(node.name, 0) + 1
            elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                stores[node.name] = stores.get(node.name, 0) + 1
            elif isinstance(node, ast.MatchMapping) and node.rest:
                stores[node.rest] = stores.get(node.rest, 0) + 1
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                for name in node.names:
                    stores[name] = stores.get(name, 0) + 1
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                assignments.append(node)
            pending.extend(ast.iter_child_nodes(node))
        if arguments:
            for arg in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                        *([arguments.vararg] if arguments.vararg else []),
                        *([arguments.kwarg] if arguments.kwarg else [])]:
                stores[arg.arg] = stores.get(arg.arg, 0) + 1
        bindings.update({name: None for name in stores})
        for assignment in assignments:
            targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
            if len(targets) != 1 or not isinstance(targets[0], ast.Name) or not isinstance(assignment.value, ast.Call):
                continue
            name = targets[0].id
            factory = self.qualified(assignment.value.func, bindings)
            if stores[name] == 1 and factory in self._FACTORIES:
                bindings[name] = "requests.Session" if factory == "requests.session" else factory
        return bindings

    def visit_Module(self, node: ast.Module) -> None:
        self.scopes.append(self.bindings(node.body))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Defaults/decorators относятся к внешней области, тело — к локальной."""
        for expression in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)
        self.scopes.append(self.bindings(node.body, node.args))
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in [*node.args.defaults, *node.args.kw_defaults]:
            if expression is not None:
                self.visit(expression)
        self.scopes.append(self.bindings([node.body], node.args))
        self.visit(node.body)
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expression in [*node.bases, *node.decorator_list, *node.keywords]:
            self.visit(expression)
        # Класс имеет отдельную область; в методах её имена не являются closure.
        scope = self.bindings(node.body)
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(statement)
            else:
                self.scopes.append(scope)
                self.visit(statement)
                self.scopes.pop()

    def visit_ListComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        """Targets comprehensions не затеняют символы окружающей функции."""
        self.visit(node.generators[0].iter)
        local: dict[str, str | None] = {}
        self.scopes.append(local)
        for index, generator in enumerate(node.generators):
            if index:
                self.visit(generator.iter)
            for child in ast.walk(generator.target):
                if isinstance(child, ast.Name):
                    local[child.id] = None
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.scopes.pop()

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def matches(self, rule: Rule, node: ast.Call, name: str | None) -> bool:
        """Применить небольшой набор явно документированных AST-предикатов."""
        argument = _argument(node, rule.argument)
        if rule.check == "any":
            return True
        if rule.check == "equals":
            return _literal(argument, rule.value)
        if rule.check == "dynamic":
            return argument is not None and not isinstance(argument, ast.Constant)
        if rule.check == "formatted_sql":
            return _formatted_sql(_argument(node, 0))
        if rule.check == "unsafe_yaml":
            if name and name.rsplit(".", 1)[-1].startswith("unsafe_"):
                return True
            loader = _argument(node, "Loader") or _argument(node, 1)
            return loader is not None and self.qualified(loader) in {
                "yaml.Loader", "yaml.CLoader", "yaml.UnsafeLoader", "yaml.CUnsafeLoader",
            }
        if rule.check == "weak_hash":
            if _literal(_argument(node, "usedforsecurity"), False):
                return False
            if name == "hashlib.new":
                algorithm = _argument(node, "name") or _argument(node, 0)
                return isinstance(algorithm, ast.Constant) and isinstance(algorithm.value, str) and algorithm.value.lower() in {"md5", "sha1"}
            return True
        if rule.check == "jwt_verification":
            options = _argument(node, "options")
            if isinstance(options, ast.Dict):
                return any(_literal(key, "verify_signature") and _literal(value, False)
                           for key, value in zip(options.keys, options.values))
            return _literal(_argument(node, "verify"), False)
        return False

    def visit_Call(self, node: ast.Call) -> None:
        name = self.qualified(node.func)
        candidates = list(self.by_name.get(name, ()))
        if isinstance(node.func, ast.Attribute):
            candidates.extend(self.by_method.get(node.func.attr, ()))
        seen = set()
        for rule in candidates:
            if rule.id in seen or not self.matches(rule, node, name):
                continue
            seen.add(rule.id)
            # AST col_offset — UTF-8 bytes; публичный API обещает Unicode-символы.
            prefix = self.lines[node.lineno - 1].encode("utf-8")[:node.col_offset]
            column = len(prefix.decode("utf-8")) + 1
            self.result.hits.append((rule, node.lineno, column))
            if len(self.result.hits) >= self.max_findings:
                self.result.reason = "finding_limit"
                return
        self.generic_visit(node)


@lru_cache(maxsize=32)
def _prefilter(rules: tuple[Rule, ...]) -> re.Pattern[str]:
    """Компилировать один фильтр на набор правил; get не должен совпасть с getenv."""
    # Имя исходной функции присутствует и при `from pickle import loads as x`.
    # Имена модулей не нужны: os.getenv не повод разбирать файл ради os.system.
    seeds = {name.rsplit(".", 1)[-1] for rule in rules for name in rule.calls}
    return re.compile(r"\b(?:" + "|".join(re.escape(seed) for seed in sorted(seeds)) + r")\b")


def analyze_python(content: str, rules: tuple[Rule, ...], *, max_nodes: int,
                   deadline: float, max_findings: int) -> PythonAnalysis:
    """Разобрать ограниченный файл; SyntaxError/RecursionError не теряют secret findings.

    Предфильтр использует имена функций из calls, присутствующие также в import
    aliases. Он не анализирует комментарии, а лишь позволяет
    избежать ast.parse, если ни один поддерживаемый символ вообще не встречается.
    AST не исполняется. Для враждебных файлов всё равно нужен внешний worker:
    ast.parse имеет ограничения стека, а его время не прерывается этим таймером.
    """
    result = PythonAnalysis()
    if not rules or not _prefilter(rules).search(content):
        return result
    try:
        # SyntaxWarning может печатать исходную строку: не допускаем утечку.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(content, filename="<scanned-source>")
        result.parsed = True
        for count, _ in enumerate(ast.walk(tree), 1):
            if count > max_nodes:
                result.reason = "python_ast_limit"
                return result
            if count % 256 == 0 and time.monotonic() >= deadline:
                result.reason = "timeout"
                return result
        if time.monotonic() >= deadline:
            result.reason = "timeout"
            return result
        _CallVisitor(rules, content.split("\n"), result, deadline, max_findings).visit(tree)
    except SyntaxError as error:
        result.reason = "python_syntax_error"
        result.line = error.lineno
    except (RecursionError, MemoryError, ValueError):
        result.reason = "python_ast_limit"
    return result
