# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Legacy SQL-model dialect — the backward-compatible grammar.

Reproduces the legacy GenroPy ``DbModelSrc`` vocabulary (element and
attribute names verbatim from ``roadmap/01_legacy_model_grammar.md``) so
existing models port almost verbatim, while obeying the builders
conventions (kwargs only, loud errors). See ``elements.py`` for the full
inventory and the deliberate divergences.
"""

from __future__ import annotations

from .builder import LegacySqlBuilder

__all__ = ["LegacySqlBuilder"]
