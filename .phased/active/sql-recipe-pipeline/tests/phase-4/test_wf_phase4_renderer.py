# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 4 contract — SqlMigrationRenderer: source tree to normalized JSON.

The golden oracle is JsonStructureProducer: the same physical model written
as a recipe and as a human JSON must converge on the same normalized dict
(codex/02 Slice B). StructureValidator guards the boundary.
"""
from __future__ import annotations

import json
import typing

from genro_sqlmigration import JsonStructureProducer, StructureValidator
from genro_sqlmigration.structures import DTYPE_CODES, json_equal

from genro_sql.modern import elements

from genro_sql import SqlBuilder, SqlMigrationRenderer


class GoldenRecipe(SqlBuilder):
    def main(self, root):
        db = root.db(name="recipes")
        public = db.schema(name="public")

        author = public.table(name="author", pkey="id", comment="Authors")
        author.column(name="id", dtype="serial")
        author.column(name="name", dtype="A", size="0:120", notnull=True,
                      name_long="Author name", x_gui="hidden")

        recipe = public.table(name="recipe", pkey="id")
        recipe.column(name="id", dtype="serial")
        recipe.column(name="title", dtype="A", size="0:160", notnull=True)
        author_id = recipe.column(name="author_id", dtype="L", notnull=True)
        author_id.relation(to="public.author.id", foreign_key=True,
                           on_delete="CASCADE", back_reference="recipes",
                           one_name="Author", many_name="Recipes")
        recipe.constraint(name="uq_author_title", constraint_type="UNIQUE",
                          columns="author_id,title")
        recipe.constraint(name="ck_title", constraint_type="CHECK",
                          check_clause="(char_length(title) > 0)")
        recipe.index(name="ix_title", columns={"title": None, "id": "DESC"})

        db.extension(name="pg_trgm")


GOLDEN_HUMAN_JSON = {
    "db": "recipes",
    "extensions": ["pg_trgm"],
    "schemas": [{
        "name": "public",
        "tables": [
            {
                "name": "author",
                "pkey": "id",
                "comment": "Authors",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "name", "dtype": "A", "size": "0:120",
                     "notnull": True},
                ],
            },
            {
                "name": "recipe",
                "pkey": "id",
                "columns": [
                    {"name": "id", "dtype": "serial"},
                    {"name": "title", "dtype": "A", "size": "0:160",
                     "notnull": True},
                    {"name": "author_id", "dtype": "L", "notnull": True},
                ],
                "relations": [
                    {"columns": ["author_id"], "related_schema": "public",
                     "related_table": "author", "related_columns": ["id"],
                     "on_delete": "CASCADE"},
                ],
                "constraints": [
                    {"type": "UNIQUE", "name": "uq_author_title",
                     "columns": ["author_id", "title"]},
                    {"type": "CHECK", "name": "ck_title",
                     "check_clause": "(char_length(title) > 0)"},
                ],
                "indexes": [
                    {"name": "ix_title",
                     "columns": {"title": None, "id": "DESC"}},
                    # D3: FK column always indexed (legacy parity)
                    {"columns": ["author_id"]},
                ],
            },
        ],
    }],
}


def _render():
    model = GoldenRecipe()
    model.create()
    return SqlMigrationRenderer(model).render()


def test_golden_convergence_with_json_twin():
    rendered = _render()
    twin = JsonStructureProducer(GOLDEN_HUMAN_JSON).get_json_struct()
    assert json_equal(rendered, twin)


def test_output_passes_structure_validator():
    StructureValidator().validate(_render())


def test_semantic_plane_never_reaches_the_json():
    flat = json.dumps(_render())
    for banned in ("name_long", "one_name", "many_name", "back_reference",
                   "x_gui", "caption_field"):
        assert banned not in flat, banned


def test_render_returns_a_fresh_structure_each_call():
    model = GoldenRecipe()
    model.create()
    renderer = SqlMigrationRenderer(model)
    first, second = renderer.render(), renderer.render()
    assert first is not second
    assert json_equal(first, second)


def test_virtual_columns_do_not_project():
    class WithVirtuals(SqlBuilder):
        def main(self, root):
            t = root.db(name="d").schema(name="s").table(name="t", pkey="id")
            t.column(name="id", dtype="serial")
            t.aliasColumn(name="al", relation_path="@rel.name")
            t.formulaColumn(name="fx", sql_formula="1+1")
            t.pyColumn(name="py", py_method="calc")
            t.subQueryColumn(name="sq", query="select 1")

    model = WithVirtuals()
    model.create()
    cols = SqlMigrationRenderer(model).render()["root"]["schemas"]["s"][
        "tables"]["t"]["columns"]
    assert set(cols) == {"id"}


def test_composite_relation_projects_multicolumn_fk():
    class CompositeFk(SqlBuilder):
        def main(self, root):
            s = root.db(name="geo").schema(name="geo")
            country = s.table(name="country", pkey="code")
            country.column(name="code", dtype="C", size="2")
            city = s.table(name="city", pkey="country_code,code")
            city.column(name="country_code", dtype="C", size="2")
            city.column(name="code", dtype="C", size="4")
            addr = s.table(name="address", pkey="id")
            addr.column(name="id", dtype="serial")
            addr.column(name="c1", dtype="C", size="2")
            addr.column(name="c2", dtype="C", size="4")
            cc = addr.compositeColumn(name="city_key", columns="c1,c2")
            cc.relation(to="geo.city", foreign_key=True)

    model = CompositeFk()
    model.create()
    rels = SqlMigrationRenderer(model).render()["root"]["schemas"]["geo"][
        "tables"]["address"]["relations"]
    (rel,) = rels.values()
    assert rel["attributes"]["columns"] == ["c1", "c2"]
    assert rel["attributes"]["related_columns"] == ["country_code", "code"]


def test_composite_unique_projects_unique_constraint():
    class CompositeUq(SqlBuilder):
        def main(self, root):
            t = root.db(name="d").schema(name="s").table(name="t", pkey="id")
            t.column(name="id", dtype="serial")
            t.column(name="a", dtype="L")
            t.column(name="b", dtype="L")
            t.compositeColumn(name="ab", columns="a,b", unique=True)

    model = CompositeUq()
    model.create()
    constraints = SqlMigrationRenderer(model).render()["root"]["schemas"][
        "s"]["tables"]["t"]["constraints"]
    (cst,) = constraints.values()
    assert cst["attributes"]["constraint_type"] == "UNIQUE"
    assert cst["attributes"]["columns"] == ["a", "b"]


def test_indexed_true_materializes_an_index_item():
    class Indexed(SqlBuilder):
        def main(self, root):
            t = root.db(name="d").schema(name="s").table(name="t", pkey="id")
            t.column(name="id", dtype="serial")
            t.column(name="email", dtype="A", size="0:80", indexed=True)

    model = Indexed()
    model.create()
    table = SqlMigrationRenderer(model).render()["root"]["schemas"]["s"][
        "tables"]["t"]
    assert "indexed" not in table["columns"]["email"]["attributes"]
    assert any(
        list(ix["attributes"]["columns"]) == ["email"]
        for ix in table["indexes"].values()
    )


def test_dtype_and_fk_action_literals_match_the_installed_contract():
    # wf:contract: the Literal aliases declared in modern/elements.py must
    # wf:contract: enumerate exactly genro_sqlmigration.structures.DTYPE_CODES
    # wf:contract: and the fk_action enum of schemas/structure-1.0.json
    # wf:contract: (RESTRICT, CASCADE, SET NULL, SET DEFAULT).
    assert set(typing.get_args(elements.DTYPE)) == set(DTYPE_CODES)
    assert set(typing.get_args(elements.FK_ACTION)) == {
        "RESTRICT", "CASCADE", "SET NULL", "SET DEFAULT"}
