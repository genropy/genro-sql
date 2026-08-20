# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Legacy-dialect grammar tests: vocabulary, containers, keying, kwargs.

Outcome-based: the tests mutate only through the canonical builder API and
assert observable results (tags, labels, attributes, raises), never node
internals. The model mirrors a small legacy GenroPy package, in the
legacy tree shape: explicit plural containers
(``packages.<pkg>.tables.<tbl>.columns.<col>`` …).
"""

import pytest
from genro_builders.builder import BuilderHandler

from genro_sql import LegacySqlBuilder


class _Model(LegacySqlBuilder):
    def main(self, root):
        pass  # built per-test on model.source


def _mount():
    model = _Model()
    BuilderHandler().add_builder(model)  # add_builder calls create()
    return model


def _node(container, key):
    return container.value.get_node(key)


def test_full_slice1_vocabulary_mounts():
    """Every Slice 1 element builds a well-formed legacy-style tree."""
    model = _mount()
    pkg = model.source.packages().package(
        name="fatt", sqlschema="fatt", pkgcode="FT")
    t = pkg.tables().table(name="fattura", pkey="id", rowcaption="$numero")
    cols = t.columns()
    cols.column(name="id", dtype="L", notnull=True)
    cols.column(name="numero", dtype="A", size=":20")
    cliente = cols.column(name="cliente_id", dtype="L", indexed=True)
    cliente.relation(
        related_column="anag.cliente.id",
        mode="foreignkey",
        one_name="Cliente",
        many_name="Fatture",
        onDelete="raise",
        onDelete_sql="cascade",
        deferred=True,
    )
    vcols = t.virtual_columns()
    vcols.virtual_column(name="vc", sql_formula="1")
    vcols.aliasColumn(name="cliente_nome", relation_path="@cliente_id.nome")
    vcols.formulaColumn(name="totale_up", sql_formula="upper($numero)")
    vcols.pyColumn(name="calcolo", py_method="pyColumn_calcolo")
    vcols.subQueryColumn(name="righe_json", query="...", mode="json")
    cc = vcols.compositeColumn(name="chiave2", columns="numero,cliente_id")
    cc.relation(related_column="fatt.altra.chiave2")
    idx = t.indexes()
    idx.index(columns="numero", unique=True)  # no name: auto-labelled
    assert sum(1 for _ in model.source) == 1  # one 'packages' at the top


def test_tree_structure_and_tags():
    """The tree mirrors the legacy container hierarchy with legacy tags."""
    model = _mount()
    pkg = model.source.packages().package(name="glbl")
    t = pkg.tables().table(name="user", pkey="id")
    cols = t.columns()
    cols.column(name="id", dtype="L")
    fk = cols.column(name="group_id", dtype="L")
    fk.relation(related_column="glbl.group.id")
    packages_node = next(iter(model.source))
    assert packages_node.node_tag == "packages"
    assert packages_node.label == "packages"
    pkg_node = _node(packages_node, "glbl")
    assert pkg_node.node_tag == "package"
    tables_node = _node(pkg_node, "tables")
    assert tables_node.node_tag == "tables"
    tbl_node = _node(tables_node, "user")
    assert tbl_node.node_tag == "table"
    columns_node = _node(tbl_node, "columns")
    col_node = _node(columns_node, "group_id")
    assert col_node.node_tag == "column"
    rel_nodes = [n for n in col_node.value]
    assert [n.node_tag for n in rel_nodes] == ["relation"]
    assert rel_nodes[0].attr.get("related_column") == "glbl.group.id"


def test_legacy_paths_are_navigable():
    """The legacy dotted paths address the tree exactly as in GenroPy."""
    model = _mount()
    pkg = model.source.packages().package(name="anag")
    t = pkg.tables().table(name="cliente", pkey="id")
    t.columns().column(name="id", dtype="L")
    t.virtual_columns().formulaColumn(name="denominazione",
                                      sql_formula="$nome")
    node = model.source.bag_get_node(
        "packages.anag.tables.cliente.columns.id")
    assert node is not None and node.node_tag == "column"
    vnode = model.source.bag_get_node(
        "packages.anag.tables.cliente.virtual_columns.denominazione")
    assert vnode is not None and vnode.node_tag == "formulaColumn"


def test_separate_keyspaces_physical_virtual_index():
    """The same name may live in columns, virtual_columns and indexes."""
    model = _mount()
    t = (model.source.packages().package(name="p")
         .tables().table(name="t"))
    t.columns().column(name="total", dtype="N")
    t.virtual_columns().formulaColumn(name="total", sql_formula="1+1")
    t.indexes().index(name="total", columns="total")
    tbl = model.source.bag_get_node("packages.p.tables.t")
    labels = [n.label for n in tbl.value]
    assert labels == ["columns", "virtual_columns", "indexes"]


def test_index_without_name_is_auto_labelled():
    """Indexes need no name: the container auto-labels them."""
    model = _mount()
    idx = (model.source.packages().package(name="p")
           .tables().table(name="t").indexes())
    idx.index(columns="a")
    idx.index(columns="b,c", unique=True)
    idx_node = model.source.bag_get_node("packages.p.tables.t.indexes")
    labels = [n.label for n in idx_node.value]
    assert labels == ["index_0", "index_1"]
    assert all(n.node_tag == "index" for n in idx_node.value)


def test_duplicate_name_in_collection_raises():
    """Two tables with the same name clash loudly (no silent overwrite)."""
    model = _mount()
    tables = model.source.packages().package(name="p").tables()
    tables.table(name="t")
    with pytest.raises(ValueError):
        tables.table(name="t")


def test_relation_under_virtual_column_is_accepted():
    """A relation may sit on any column kind, including virtual ones."""
    model = _mount()
    vcols = (model.source.packages().package(name="p")
             .tables().table(name="t").virtual_columns())
    fc = vcols.formulaColumn(name="f", sql_formula="1")
    fc.relation(related_column="p.other.id")  # legal on a virtual column
    vc = vcols.virtual_column(name="v", relation_path="@x.id")
    vc.relation(related_column="p.other.id")  # legal on the generic virtual


def test_relation_is_at_most_one_per_column():
    model = _mount()
    col = (model.source.packages().package(name="p")
           .tables().table(name="t").columns().column(name="c", dtype="L"))
    col.relation(related_column="p.a.id")
    with pytest.raises(ValueError):
        col.relation(related_column="p.b.id")  # relation[:1] exceeded


def test_open_kwargs_land_as_node_attributes():
    """Arbitrary extension metadata rides through untouched (hard req)."""
    model = _mount()
    pkg = model.source.packages().package(name="p", ltx_scope="app")
    t = pkg.tables().table(name="t", ltx_owner="crm", variant_total_dtype="N")
    col = t.columns().column(name="c", dtype="A", ltx_mask="upper",
                             ext_biz={"k": 1})
    rel = col.relation(related_column="p.o.id", cnd="$c>0", meta_childmode="x")
    pkg_node = model.source.bag_get_node("packages.p")
    assert pkg_node.attr.get("ltx_scope") == "app"
    tbl_node = model.source.bag_get_node("packages.p.tables.t")
    assert tbl_node.attr.get("ltx_owner") == "crm"
    assert tbl_node.attr.get("variant_total_dtype") == "N"
    col_node = model.source.bag_get_node("packages.p.tables.t.columns.c")
    assert col_node.attr.get("ltx_mask") == "upper"
    assert col_node.attr.get("ext_biz") == {"k": 1}
    rel_node = next(iter(col_node.value))
    assert rel_node.attr.get("cnd") == "$c>0"
    assert rel_node.attr.get("meta_childmode") == "x"
    assert rel is not None


def test_declared_attribute_types_are_validated():
    """Declared legacy attributes are typed: a wrong type raises."""
    model = _mount()
    cols = (model.source.packages().package(name="p")
            .tables().table(name="t").columns())
    with pytest.raises(ValueError):
        cols.column(name="c", dtype="N", unique="si")  # bool expected
    with pytest.raises(ValueError):
        (model.source.bag_get_node("packages.p.tables.t")
         .virtual_columns().aliasColumn(name="a"))  # relation_path required


def test_column_rejects_non_column_child():
    """A column accepts only a relation, nothing else."""
    model = _mount()
    col = (model.source.packages().package(name="p")
           .tables().table(name="t").columns().column(name="c", dtype="L"))
    with pytest.raises(ValueError):
        col.column(name="nested", dtype="L")


def test_containers_are_mandatory():
    """Elements cannot skip their container: no column under a table,
    no table under a package, no column under a package."""
    model = _mount()
    pkg = model.source.packages().package(name="p")
    with pytest.raises(ValueError):
        pkg.table(name="stray")  # tables() container is mandatory
    t = pkg.tables().table(name="t")
    with pytest.raises(ValueError):
        t.column(name="stray", dtype="L")  # columns() is mandatory
    with pytest.raises(ValueError):
        pkg.column(name="stray", dtype="L")
