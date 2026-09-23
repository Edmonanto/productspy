"""Static integrity checks on the SQL.

None of this SQL runs during the unit tests — the database layer is stubbed —
so the first real execution is the first ingestion run in production. These
tests close that gap: a wrong column name, a placeholder/argument mismatch or
a syntax error is caught here instead of at 03:00 in a cron job.

The grammar checks use pglast (bindings to PostgreSQL's own parser) and skip
cleanly when it isn't installed, so the rest of the file still guards.
"""
import ast
import collections
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((BACKEND / "migrations").glob("*.sql"))
REPOSITORY = BACKEND / "app" / "repository.py"
REPO_SRC = REPOSITORY.read_text()
DB_METHODS = {"execute", "fetchval", "fetchrow", "fetch"}

try:
    import pglast as _pglast
except ImportError:  # pragma: no cover
    _pglast = None

needs_pglast = pytest.mark.skipif(_pglast is None, reason="pglast not installed")


def schema() -> dict[str, set[str]]:
    """Column set per table, built from the migrations."""
    tables: dict[str, set[str]] = collections.defaultdict(set)
    sql = "\n".join(p.read_text() for p in MIGRATIONS)

    for match in re.finditer(
        r"create table if not exists (\w+)\s*\((.*?)\n\);", sql, re.S
    ):
        table, body = match.group(1), match.group(2)
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.startswith(
                ("--", "unique", "primary key", "check", "constraint", "foreign")
            ):
                continue
            column = line.split()[0]
            if column.isidentifier():
                tables[table].add(column)

    for match in re.finditer(r"alter table (\w+) add column if not exists (\w+)", sql):
        tables[match.group(1)].add(match.group(2))

    return dict(tables)


def db_queries() -> list[tuple[str, str, int | None]]:
    """(function name, SQL, positional arg count) for each db.* call.

    The arg count is None when the call unpacks a list (`*args`) or the SQL
    interpolates a dynamically built predicate — in both cases the real
    placeholder count is only known at runtime, so it cannot be asserted here.
    The statement is still grammar-checked.
    """
    product_select = re.search(r'_PRODUCT_SELECT = """(.*?)"""', REPO_SRC, re.S)
    found = []

    for fn in ast.walk(ast.parse(REPO_SRC)):
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if not (isinstance(func, ast.Attribute) and func.attr in DB_METHODS):
                continue
            if not call.args:
                continue

            # `*args` unpacking makes the argument count dynamic.
            variadic = any(isinstance(a, ast.Starred) for a in call.args)

            node = call.args[0]
            dynamic_sql = False
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                parts = []
                for value in node.values:
                    if isinstance(value, ast.Constant):
                        parts.append(value.value)
                    elif isinstance(value, ast.FormattedValue):
                        name = getattr(value.value, "id", None)
                        # Only _PRODUCT_SELECT is a real fragment; the rest are
                        # dynamic predicates, stubbed so the statement parses.
                        if name == "_PRODUCT_SELECT" and product_select:
                            parts.append(product_select.group(1))
                        else:
                            # A runtime-built predicate; stub it so the rest of
                            # the statement can still be parsed.
                            dynamic_sql = True
                            parts.append("1=1")
                text = "".join(parts)
            else:
                continue

            countable = None if (variadic or dynamic_sql) else len(call.args) - 1
            found.append((fn.name, text, countable))
    return found


# ── schema sanity ───────────────────────────────────────────────────────────
def test_every_expected_table_is_created():
    tables = schema()
    for name in (
        "products", "product_scores", "suppliers", "ad_signals", "watchlists",
        "subscriptions", "search_usage", "product_snapshots", "ingestion_runs",
        "billing_events",
    ):
        assert name in tables, f"{name} is never created by a migration"


def test_queries_only_reference_columns_that_exist():
    """A typo'd column passes every unit test and fails the first real insert."""
    tables = schema()
    problems = []

    for _, sql, _ in db_queries():
        for match in re.finditer(r"insert into (\w+)\s*\(([^)]*)\)", sql, re.I | re.S):
            table, columns = match.group(1), match.group(2)
            if table not in tables:
                problems.append(f"insert into unknown table '{table}'")
                continue
            for column in re.findall(r"\b([a-z_]+)\b", columns):
                if column not in tables[table]:
                    problems.append(f"{table}.{column} does not exist")

    # Qualified references anywhere in the file, e.g. subscriptions.plan
    for table, column in re.findall(r"\b(\w+)\.(\w+)\b", REPO_SRC):
        if table in tables and column not in tables[table]:
            problems.append(f"{table}.{column} does not exist")

    assert not problems, "\n".join(sorted(set(problems)))


# ── parameter binding ───────────────────────────────────────────────────────
def test_placeholder_count_matches_arguments():
    """asyncpg raises at runtime when $N and the argument count disagree."""
    problems = []
    checked = 0
    for name, sql, n_args in db_queries():
        if n_args is None:
            continue  # dynamic predicate or *args — not statically knowable
        checked += 1
        placeholders = {int(n) for n in re.findall(r"\$(\d+)", sql)}
        if not placeholders:
            if n_args:
                problems.append(f"{name}(): {n_args} args but no placeholders")
            continue
        highest = max(placeholders)
        if highest != n_args:
            problems.append(f"{name}(): highest is ${highest} but {n_args} args passed")
        if placeholders != set(range(1, highest + 1)):
            missing = sorted(set(range(1, highest + 1)) - placeholders)
            problems.append(f"{name}(): placeholders skip {missing}")
    assert not problems, "\n".join(problems)
    assert checked >= 15, f"only {checked} queries were statically checkable"


# ── real PostgreSQL grammar ─────────────────────────────────────────────────
@needs_pglast
@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_migration_parses(path):
    """Each migration must survive `psql -f` before it reaches Supabase."""
    statements = _pglast.parse_sql(path.read_text())
    assert statements, f"{path.name} contains no statements"


@needs_pglast
def test_every_query_parses():
    failures = []
    for name, sql, _ in db_queries():
        try:
            _pglast.parse_sql(sql)
        except Exception as exc:
            failures.append(f"{name}(): {exc}")
    assert not failures, "\n".join(failures)


@needs_pglast
def test_suite_actually_covers_the_queries():
    """Guards the guard: if extraction silently breaks, the checks above pass
    vacuously. repository.py has ~25 db calls; far fewer means a parser bug."""
    assert len(db_queries()) >= 20
