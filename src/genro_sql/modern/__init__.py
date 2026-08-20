# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Modern SQL-model dialect — the optimized grammar.

The current, backend-abstract grammar designed in
``roadmap/05_grammar_design.md`` (§2.4/§2.5): a ``db → schema → table``
hierarchy with a column family, relations on the physical column kinds,
constraints, indexes and database extensions.

:class:`SqlBuilder` carries the grammar; :class:`SqlRenderer` emits DDL.

:class:`SqlMigrationRenderer` projects the tree into the normalized
migration JSON. It needs genro-sqlmigration, an optional dependency, so it
is resolved lazily: importing the name without the ``migration`` extra
installed fails loudly instead of failing this whole module.
"""

from __future__ import annotations

from .builder import SqlBuilder
from .renderer import SqlRenderer

__all__ = ["SqlBuilder", "SqlMigrationRenderer", "SqlRenderer"]

_MIGRATION_EXTRA = (
    "genro-sqlmigration is required for {name}: install genro-sql[migration]"
)


def __getattr__(name: str):  # wf:phase-4:new
    if name == "SqlMigrationRenderer":
        try:
            from .migration import SqlMigrationRenderer
        except ImportError as error:
            raise ImportError(_MIGRATION_EXTRA.format(name=name)) from error
        return SqlMigrationRenderer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
