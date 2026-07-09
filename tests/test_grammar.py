# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Grammar tests: the element vocabulary and sub_tags validation.

Outcome-based: the tests mutate only through the canonical builder API and
assert observable results (a model built with every element mounts; illegal
placements raise), never auto-generated labels or node internals.
"""

import pytest
from genro_builders.builder import BuilderHandler

from genro_sql import SqlBuilder


class _Model(SqlBuilder):
    def main(self, root):
        pass  # built per-test on model.source


def _mount():
    model = _Model()
    BuilderHandler().add_builder(model)  # add_builder calls create()
    return model


def test_full_vocabulary_mounts():
    """Every element in the grammar builds a well-formed tree."""
    model = _mount()
    db = model.source.db(name="testdb")
    db.extension(name="unaccent")
    db.eventTrigger(name="on_ddl")
    s = db.schema(name="public", sqlschema="public")
    t = s.table(name="recipe", pkey="id", caption_field="title")
    t.column(name="id", dtype="L", notnull=True)
    author = t.column(name="author_id", dtype="L", indexed=True)
    author.relation(to="public.author.id", foreign_key=True)
    t.formulaColumn(name="up", sql_formula="upper($title)")
    t.aliasColumn(name="an", relation_path="@author_id.name")
    t.subQueryColumn(name="cnt", query="...", mode="json")
    t.pyColumn(name="calc")
    cc = t.compositeColumn(name="k2", columns="id,author_id")
    cc.relation(to="public.other.k2", foreign_key=True)
    t.constraint(name="uq", constraint_type="UNIQUE", columns="id,author_id")
    t.index(name="ix", columns="author_id")
    t.trigger(name="trg", timing="BEFORE", events="INSERT")
    s.view(name="v", definition="SELECT 1")
    s.function(name="fn", language="sql", body="SELECT 1")
    s.sequence(name="seq", start_value="1")
    s.dbtype(name="mood", type_kind="ENUM", enum_values="a,b")
    assert sum(1 for _ in model.source) == 1  # one db at the top


def test_column_rejects_non_column_child():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    col = t.column(name="c", dtype="L")
    with pytest.raises(ValueError):
        col.column(name="nested", dtype="L")


def test_virtual_column_accepts_relation():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    fc = t.formulaColumn(name="f", sql_formula="1")
    fc.relation(to="p.other.id")  # a relation under a virtual column is legal


def test_relation_is_at_most_one_per_column():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    col = t.column(name="c", dtype="L")
    col.relation(to="p.a.id")
    with pytest.raises(ValueError):
        col.relation(to="p.b.id")  # relation[:1]: the second exceeds the max
