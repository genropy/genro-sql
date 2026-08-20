# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlBuilder — SQL model dialect for genro-builders.

Grammar only: the vocabulary lives in :class:`SqlElements`, rendering
in :class:`SqlRenderer` exposed via the ``renderer_sql`` property.
"""

from __future__ import annotations

from genro_builders.builder import BuilderBase

from .elements import SqlElements
from .renderer import SqlRenderer


class SqlBuilder(BuilderBase, SqlElements):
    """SQL model dialect builder. Grammar only — rendering on
    ``SqlRenderer`` via the ``renderer_sql`` property."""

    _name = "sql"
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
            pass  # grammar not defined yet: empty model

    model = _Demo()
    model.create()
    print("source tree:", model.source)
