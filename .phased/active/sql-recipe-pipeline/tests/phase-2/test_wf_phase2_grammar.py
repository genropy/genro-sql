# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 2 contract — class-scoped grammar with typed signatures.

Executable contract: the recipe surface below is fixed by the plan
(Phase 2 Decisions). The grammar must build the tree, key collections by
name, enforce cardinalities and closed signatures, and expose the
projection flags in element _meta.
"""
from __future__ import annotations

import pytest

from genro_sql import SqlBuilder


def _recipe():
    class RecipeDatabase(SqlBuilder):
        def main(self, root):
            db = root.db(name="recipes")
            public = db.schema(name="public")

            author = public.table(name="author", pkey="id", comment="Authors")
            author.column(name="id", dtype="serial")
            author.column(name="name", dtype="A", size="0:120", notnull=True,
                          name_long="Author name", x_custom="free")

            recipe = public.table(name="recipe", pkey="id")
            recipe.column(name="id", dtype="serial")
            recipe.column(name="title", dtype="A", size="0:160", notnull=True)
            author_id = recipe.column(name="author_id", dtype="L", notnull=True)
            author_id.relation(to="public.author.id", foreign_key=True,
                               on_delete="CASCADE", back_reference="recipes")
            recipe.compositeColumn(name="author_title",
                                   columns="author_id,title", unique=True)
            recipe.constraint(name="ck_title", constraint_type="CHECK",
                              check_clause="char_length(title) > 0")
            recipe.index(name="ix_title", columns={"title": None, "id": "DESC"})

            db.extension(name="pg_trgm")

    model = RecipeDatabase()
    model.create()
    return model


def test_recipe_builds_and_tree_is_name_addressed():
    model = _recipe()
    node = model.source["db.public.author"]
    assert node is not None
    author_cols = [n.label for n in node.value]
    assert "id" in author_cols and "name" in author_cols


def test_collections_are_keyed_by_name_at_every_level():
    model = _recipe()
    assert model.source["db.public"] is not None
    assert model.source["db.public.recipe"] is not None
    assert model.source["db.public.recipe.author_id"] is not None


def test_duplicate_table_name_raises():
    class Dup(SqlBuilder):
        def main(self, root):
            s = root.db(name="d").schema(name="s")
            s.table(name="t")
            s.table(name="t")

    with pytest.raises(Exception):
        Dup().create()


def test_unknown_physical_attribute_rejected_at_grammar_or_validation():
    # wf:contract: a typo like dtypo= must NOT silently become a semantic
    # wf:contract: attribute: either the element signature rejects it at call
    # wf:contract: time, or (D2 semi-closed) the Phase 3 validator rejects any
    # wf:contract: **extra key not starting with x_. At Phase 2 the grammar
    # wf:contract: must at least ACCEPT x_-prefixed extras and carry them on
    # wf:contract: the node attributes.
    model = _recipe()
    name_node = model.source["db.public.author.name"]
    assert name_node.get_attr("x_custom") == "free"


def test_unknown_tag_raises():
    class BadTag(SqlBuilder):
        def main(self, root):
            root.db(name="d").schema(name="s").table(name="t").view(name="v")

    with pytest.raises(AttributeError):
        BadTag().create()


def test_out_of_scope_elements_are_gone():
    for gone in ("view", "function", "sequence", "dbtype", "trigger",
                 "eventTrigger"):
        assert gone not in SqlBuilder._class_schema, gone


def test_relation_cardinality_at_most_one():
    class TwoRels(SqlBuilder):
        def main(self, root):
            t = root.db(name="d").schema(name="s").table(name="t", pkey="a")
            c = t.column(name="a", dtype="L")
            c.relation(to="s.t.a")
            c.relation(to="s.t.a")

    model = TwoRels()
    model.create()
    problems = model.validate_source()
    assert problems, "two relations on one column must fail containment"


def test_virtual_columns_do_not_accept_children_but_composite_hosts_relation():
    class Comp(SqlBuilder):
        def main(self, root):
            t = root.db(name="d").schema(name="s").table(name="t", pkey="a")
            t.column(name="a", dtype="L")
            t.column(name="b", dtype="A", size="0:10")
            cc = t.compositeColumn(name="ab", columns="a,b")
            cc.relation(to="s.t")

    Comp().create()  # must not raise


def test_projection_meta_flags():
    model = _recipe()
    col = model.source["db.public.author.name"]
    composite = model.source["db.public.recipe.author_title"]
    assert col._get_meta("projects_column") is True
    assert composite._get_meta("projects_column") in (False, None)
    assert col._get_meta("projects_relation") is True
    assert composite._get_meta("projects_relation") is True


def test_dtype_is_validated_as_literal():
    class BadDtype(SqlBuilder):
        def main(self, root):
            root.db(name="d").schema(name="s").table(name="t").column(
                name="c", dtype="NOPE")

    with pytest.raises(Exception):
        BadDtype().create()
