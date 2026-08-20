# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlRenderer — DDL renderer for the SQL model dialect.

Walks the source tree and emits DDL (CREATE TABLE, ALTER TABLE, ...).
Placeholder: the real rendering arrives with the grammar. Database
dialect renderers (PostgreSQL, SQLite, ...) will specialise this class.
"""

from __future__ import annotations

from genro_builders.renderer import RendererBase


class SqlRenderer(RendererBase):
    """DDL renderer — implementation follows the grammar design."""
