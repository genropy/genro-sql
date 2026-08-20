# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Modern SQL-model dialect — the optimized grammar.

The current, backend-abstract grammar designed in
``roadmap/05_grammar_design.md`` (§2.4/§2.5): a ``db → schema → table``
hierarchy with a column family, relations on the physical column kinds,
constraints, indexes and database extensions.

:class:`SqlBuilder` carries the grammar; :class:`SqlRenderer` emits DDL.

:class:`SqlMigrationRenderer` projects the tree into the normalized
migration JSON and :class:`SqlModelReader` reads it back. Both need
genro-sqlmigration, an optional dependency, so they are resolved lazily:
importing one of the names without the ``migration`` extra installed fails
loudly instead of failing this whole module.
"""

from __future__ import annotations

from importlib import import_module

from .builder import SqlBuilder
from .renderer import SqlRenderer

__all__ = [
    "SqlBuilder", "SqlMigrationRenderer", "SqlModelReader", "SqlRenderer",
]

_MIGRATION_EXTRA = (
    "genro-sqlmigration is required for {name}: install genro-sql[migration]"
)


_MIGRATION_NAMES = {
    "SqlMigrationRenderer": ".migration",
    "SqlModelReader": ".reader",
}


def __getattr__(name: str):  # wf:phase-4:new
    module_name = _MIGRATION_NAMES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = import_module(module_name, __name__)
    except ImportError as error:
        raise ImportError(_MIGRATION_EXTRA.format(name=name)) from error
    return getattr(module, name)
