# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlBuilder — SQL model dialect for genro-builders.

Grammar only: the vocabulary lives in the four mixins of
:mod:`genro_sql.modern.elements`, rendering in :class:`SqlRenderer` exposed
via the ``renderer_sql`` property.
"""

from __future__ import annotations

from genro_bag import Bag, BagNode

from genro_builders.builder import BuilderBase, SourceBag
from genro_builders.builder.base import SOURCE_ROOT

from .elements import ColumnElements, DbElements, SchemaElements, TableElements
from .renderer import SqlRenderer
from .validators import SqlModelValidator


class SqlSourceBag(SourceBag):  # wf:phase-2:new
    """Source bag whose bracket access is name addressing over NODES.

    ``model.source["db.public.author"]`` returns the grammar node — its
    attributes, ``_meta`` flags and children — because the SQL model is a
    name-keyed catalog, not a value store: every consumer (renderer,
    validators, emitter) reads nodes. ``get_item``/``get`` keep the plain
    Bag value semantics. Sub-bags inherit this class automatically (the
    grammar spawns them as ``type(node.parent_bag)``), so the whole tree
    is addressed the same way.

    The override also reshapes every Bag form that reads through
    ``__getitem__``: the ``?attr`` path suffix and ``bag(path)`` return
    the node instead of value/attribute, an empty path returns the
    owning node, and the scoped ``query``/``digest`` form
    (``"where:what"``) is unsupported — scope with ``get_item(where)``
    or walk from a node's ``.value`` instead.
    """

    def __getitem__(self, path: str) -> BagNode | None:  # wf:phase-2:new
        return self.get_node(path)


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

    def __init__(self, name: str | None = None) -> None:  # wf:phase-2:new
        super().__init__(name)
        source = SqlSourceBag(builder=self)
        self._sourceroot[SOURCE_ROOT] = source
        self.source = source

    def validate_source(self) -> list[tuple[str, list[str]]]:  # wf:phase-2:new
        """Extend the framework report with the dialect's containment rules.

        The framework reports unmet minima and enforces maxima at insertion;
        ``relation`` is instead declared unbounded so an over-full document
        can be BUILT and then reported here — one report for the whole
        document beats an exception at the first offending line.
        """
        problems = super().validate_source()
        for _path, node in self.source.walk():
            if not node._get_meta("projects_relation"):
                continue
            children = node.value
            if not isinstance(children, Bag):
                continue
            relations = [n for n in children if n.node_tag == "relation"]
            if len(relations) > 1:
                problems.append(
                    (node.fullpath, ["relation: at most one per column"]),
                )
        return problems

    def validate_model(self):  # wf:phase-3:new
        """Run the domain validation on this model and return it.

        Convenience over ``SqlModelValidator().validate(self)``; raises
        :class:`~genro_sql.modern.validators.SqlModelValidationError`
        listing every violation.
        """
        return SqlModelValidator().validate(self)

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
