# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Modern SQL-model dialect — the optimized grammar.

The current, backend-abstract grammar designed in
``roadmap/05_grammar_design.md`` (§2.4/§2.5): a ``db → schema → table``
hierarchy with a column family, relations on the physical column kinds,
constraints, indexes and database extensions.

:class:`SqlBuilder` carries the grammar; :class:`SqlRenderer` emits DDL.
"""

from __future__ import annotations

from .builder import SqlBuilder
from .renderer import SqlRenderer

__all__ = ["SqlBuilder", "SqlRenderer"]
