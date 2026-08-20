# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Grammar tests: the element vocabulary, its signatures and containment.

Outcome-based: the tests mutate only through the canonical builder API and
assert observable results (a model built with every element mounts; illegal
placements and undeclared attributes raise), never auto-generated labels or
node internals.
"""

import pytest
from genro_sqlmigration import JsonStructureProducer
from genro_sqlmigration.structures import json_equal

from genro_sql import SqlBuilder, SqlMigrationRenderer, SqlModelReader


class _Model(SqlBuilder):
    def main(self, root):
        pass  # built per-test on model.source


def _mount():
    model = _Model()
    model.create()
    return model


def test_full_vocabulary_mounts():
    """Every element in the grammar builds a well-formed tree."""
    model = _mount()
    db = model.source.db(name="testdb")
    db.extension(name="unaccent")
    s = db.schema(name="public", comment="the default schema")
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
    assert sum(1 for _ in model.source) == 1  # one db at the top


def test_tree_is_addressed_by_name():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t", pkey="c")
    t.column(name="c", dtype="L")
    assert model.source.get_node("db.p.t.c") is not None


def test_column_rejects_non_column_child():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    col = t.column(name="c", dtype="L")
    with pytest.raises(ValueError):
        col.column(name="nested", dtype="L")


def test_virtual_column_rejects_relation():
    """A virtual column reads through an existing relation, never its own."""
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    fc = t.formulaColumn(name="f", sql_formula="1")
    with pytest.raises(ValueError):
        fc.relation(to="p.other.id")


def test_relation_is_at_most_one_per_column():
    """The violation is reported by validation, not raised at insertion."""
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    col = t.column(name="c", dtype="L")
    col.relation(to="p.a.id")
    assert model.validate_source() == []  # one relation is legal
    col.relation(to="p.b.id")
    problems = model.validate_source()
    assert any("at most one" in msg for _path, msgs in problems for msg in msgs)


def test_undeclared_attribute_is_rejected_where_the_signature_is_closed():
    """``db`` declares no ``**extra``, so a typo cannot become an attribute."""
    model = _mount()
    with pytest.raises(ValueError):
        model.source.db(name="d", dbnmae="typo")


def test_extra_attributes_are_carried_where_the_signature_is_open():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    t.column(name="c", dtype="L", x_widget="slider")
    node = model.source.get_node("db.p.t.c")
    assert node.get_attr("x_widget") == "slider"


def test_dtype_must_be_a_known_code():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    with pytest.raises(ValueError):
        t.column(name="c", dtype="NOPE")


def test_constraint_type_must_be_known():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    with pytest.raises(ValueError):
        t.constraint(name="x", constraint_type="EXCLUDE", columns="c")


def test_projection_flags_ride_on_the_nodes():
    model = _mount()
    t = model.source.db(name="d").schema(name="p").table(name="t")
    t.column(name="a", dtype="L")
    t.column(name="b", dtype="L")
    t.compositeColumn(name="ab", columns="a,b")
    t.formulaColumn(name="f", sql_formula="1")
    col = model.source.get_node("db.p.t.a")
    composite = model.source.get_node("db.p.t.ab")
    formula = model.source.get_node("db.p.t.f")
    assert col._get_meta("projects_column") is True
    assert col._get_meta("projects_relation") is True
    assert composite._get_meta("projects_column") is None
    assert composite._get_meta("projects_relation") is True
    assert formula._get_meta("projects_column") is None
    assert formula._get_meta("projects_relation") is None


def test_out_of_scope_elements_are_absent():
    for gone in ("view", "function", "sequence", "dbtype", "trigger",
                 "eventTrigger"):
        assert gone not in SqlBuilder._class_schema, gone


def test_composite_target_resolves_to_its_member_columns():
    """D4: a multi-column FK to a non-pkey key targets a composite."""
    normalized = JsonStructureProducer({
        "db": "d",
        "schemas": [{"name": "s", "tables": [
            {"name": "parent", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "a", "dtype": "L"},
                         {"name": "b", "dtype": "L"}],
             "constraints": [{"type": "UNIQUE", "columns": ["a", "b"]}]},
            {"name": "child", "pkey": "id",
             "columns": [{"name": "id", "dtype": "serial"},
                         {"name": "pa", "dtype": "L"},
                         {"name": "pb", "dtype": "L"}],
             "relations": [
                 {"columns": ["pa", "pb"], "related_schema": "s",
                  "related_table": "parent", "related_columns": ["a", "b"]},
             ]},
        ]}],
    }).get_json_struct()
    builder = SqlModelReader(normalized).to_builder()
    relation = builder.source.query(
        "#n", deep=True, condition=lambda n: n.node_tag == "relation")[0]
    assert relation.get_attr("to") == "s.parent.a_b"
    assert json_equal(normalized, SqlMigrationRenderer(builder).render())
