# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL model grammar — element definitions.

Vocabulary under design. The target shape, inspired by the legacy
``DbModelSrc`` (gnr.sql.gnrsqlmodel) and by the genro-proxy SQL layer:

- ``db`` — root of the model
- ``schema`` — a database schema (the legacy "package")
- ``table`` — with ``pkey`` and metadata
- ``column`` — typed column; may declare an inline relation
- ``relation`` — table-level foreign key with ``from_columns`` /
  ``to_columns`` (composite keys supported), ``on_delete`` strategy
  and back-relation naming
- ``index`` / ``constraint`` — secondary structures

No element is defined yet: the grammar is the next design step.
"""

from __future__ import annotations


class SqlElements:
    """Grammar mixin for :class:`~genro_sql.sql_builder.SqlBuilder`."""
