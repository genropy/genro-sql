# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Shared base classes for the SQL-model dialects.

This package is the home of code shared across the grammar dialects
(``legacy`` and ``modern``) — a common builder base and/or a common
renderer base, once the dialects genuinely share such code.

As of the current slice they do not: the ``legacy`` dialect is
grammar-only (no renderer yet) and the ``modern`` dialect's renderer is
dialect-specific and lives under ``modern/``. Rather than invent a
speculative abstraction, ``base/`` stays empty on purpose and will grow
the first concrete shared base when a second consumer actually needs it.

See ``roadmap/05_grammar_design.md`` §5.1 for the layout decision.
"""

from __future__ import annotations

__all__: list[str] = []
