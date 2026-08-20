# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlBuilder — SQL model dialect for genro-builders.

Grammar only: the vocabulary lives in the four mixins of
:mod:`genro_sql.modern.elements`, rendering in :class:`SqlRenderer` exposed
via the ``renderer_sql`` property.
"""

from __future__ import annotations

from genro_builders.builder import BuilderBase

from .elements import ColumnElements, DbElements, SchemaElements, TableElements
from .renderer import SqlRenderer


class SqlBuilder(DbElements, SchemaElements, TableElements, ColumnElements,
                 BuilderBase):
    """SQL model dialect builder.

    One dialect, one flat namespace: the grammar is split into mixins by
    containment level for readability, never into sub-dialects — a mounted
    sub-dialect loses the name-keyed addressing (``db.public.author.id``)
    the whole model rests on.
    """

    _name = "sqlmodel"
    _default_render_mode = "sql"

    @property
    def renderer_sql(self) -> SqlRenderer:
        """Fresh ``SqlRenderer`` instance bound to this builder.

        Each access returns a new instance: the renderer is meant to be
        ephemeral, used for a single ``render`` call and discarded.
        """
        return SqlRenderer(builder=self)


if __name__ == "__main__":
    class _Demo(SqlBuilder):
        def main(self, root):
            db = root.db(name="demo")
            recipe = db.schema(name="public").table(name="recipe", pkey="id")
            recipe.column(name="id", dtype="serial")
            recipe.column(name="title", dtype="A", size="0:160", notnull=True)

    model = _Demo()
    model.create()
    print("source tree:", model.source)
