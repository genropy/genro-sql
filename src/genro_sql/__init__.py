# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""genro-sql — describe a database pythonically, render it as SQL.

A dialect family of genro-builders, one sub-package per grammar dialect
(see ``roadmap/05_grammar_design.md`` §5.1):

- :mod:`genro_sql.modern` — the optimized grammar: :class:`SqlBuilder`
  carries the vocabulary (db, schema, table, column, relation, index, …),
  :class:`SqlRenderer` emits DDL from the source tree.
- :mod:`genro_sql.legacy` — the backward-compatible grammar:
  :class:`LegacySqlBuilder` mirrors the legacy GenroPy ``DbModelSrc``
  vocabulary so existing models port almost verbatim.
- :mod:`genro_sql.base` — shared base classes (minimal for now).

The same source tree is the pivot for the migration tooling
(genro-sqlmigration) and, later, for the round-trip: a reader (live
database -> tree) and an emitter (tree -> idiomatic .py).
"""

from .legacy import LegacySqlBuilder
from .modern import SqlBuilder, SqlRenderer

__version__ = "0.1.0"

__all__ = [
    "LegacySqlBuilder", "SqlBuilder", "SqlMigrationRenderer", "SqlRenderer",
]


def __getattr__(name: str):  # wf:phase-4:new
    """Resolve the names that need an optional dependency, on first use."""
    if name == "SqlMigrationRenderer":
        from . import modern
        return getattr(modern, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
