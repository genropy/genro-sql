# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""LegacySqlBuilder — backward-compatible SQL-model dialect.

Grammar only: the vocabulary lives in :class:`LegacySqlElements`. It
reproduces the legacy GenroPy ``DbModelSrc`` grammar so an existing model
ports almost verbatim (see ``elements.py`` for the element/attribute
inventory and the deliberate divergences). DDL rendering is a later slice;
this dialect declares no renderer yet.
"""

from __future__ import annotations

from genro_builders.builder import BuilderBase

from .elements import LegacySqlElements


class LegacySqlBuilder(BuilderBase, LegacySqlElements):
    """Legacy SQL-model dialect builder. Grammar only — DDL rendering
    arrives in a later slice, so no renderer is bound yet."""

    _name = "sql_legacy"


if __name__ == "__main__":
    class _Demo(LegacySqlBuilder):
        def main(self, root):
            pkg = root.packages().package(name="glbl", sqlschema="glbl")
            tbl = pkg.tables().table(name="user", pkey="id")
            cols = tbl.columns()
            cols.column(name="id", dtype="L", notnull=True)
            fk = cols.column(name="parent_id", dtype="L", indexed=True)
            fk.relation(related_column="glbl.user.id", relation_name="children")

    model = _Demo()
    model.create()
    print("source tree:", model.source)
