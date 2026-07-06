# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""genro-sql — describe a database pythonically, render it as SQL.

A dialect of genro-builders: :class:`SqlBuilder` carries the grammar
(db, schema, table, column, relation, index, ...), :class:`SqlRenderer`
emits DDL from the source tree. The same tree is the pivot for the
migration tooling (genro-sqlmigration) and, later, for the round-trip:
a reader (live database -> tree) and an emitter (tree -> idiomatic .py).

The grammar is under design; see ``sql_elements.py`` for the target
vocabulary.
"""

from .sql_builder import SqlBuilder
from .sql_renderer import SqlRenderer

__version__ = "0.1.0"

__all__ = ["SqlBuilder", "SqlRenderer"]
