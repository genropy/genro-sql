# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Legacy SQL-model grammar — element definitions (backward-compatible).

Grammar mixin for :class:`~genro_sql.legacy.builder.LegacySqlBuilder`. It
reproduces the legacy GenroPy ``DbModelSrc`` vocabulary (inventory in
``roadmap/01_legacy_model_grammar.md``) so an existing legacy model can be
ported almost verbatim: **same element names, same attribute names** as
the legacy grammar. The docstrings are the living documentation of the
domain — a newcomer (or an LLM writing a model) should understand each
construct from here alone.

Hierarchy (Slice 1) — the tree has the exact shape of the legacy source
tree, with the plural **containers as explicit grammar elements** the
author writes (``packages``, ``tables``, ``columns``, ``virtual_columns``,
``indexes``)::

    packages                       # container, fixed label
    └── package                    # keyed by name
        └── tables                 # container, fixed label
            └── table              # keyed by name
                ├── columns            → column        (keyed by name)
                ├── virtual_columns    → virtual_column, aliasColumn,
                │                        formulaColumn, pyColumn,
                │                        subQueryColumn, compositeColumn
                │                        (keyed by name)
                ├── indexes            → index         (auto-labelled;
                │                        ``name`` optional)
                └── <any column>.relation   # child of ANY column kind

Every container is a collection of its own: separate keyspaces by
construction (a column ``total`` and an index ``total`` never clash), and
per-container keying (``indexes`` has none, so ``index`` needs no name —
the migrator generates a hashed one downstream).

Two planes, kept distinct exactly as in the legacy. The **physical /
SQL** plane (``dtype``, ``size``, ``notnull``, ``onDelete_sql``…) is what
the DDL/migrate consumes; the **semantic / application** plane
(``name_*``, ``group``, triggers, ``onDelete``…) travels alongside it.

Open kwargs everywhere (hard requirement): every element accepts
arbitrary extra keyword arguments, stored untouched as node attributes.
Application/extension metadata (``ltx_*``, ``variant_*``, ``ext_*``, …)
therefore rides through the tree without the grammar having to know it —
matching the legacy's open ``**kwargs`` (doc `01` §2).

Typed signatures: the known legacy attributes are declared as real typed
parameters — the signature IS documentation, and the engine validates
type and presence of the declared ones. Any extra kwarg still passes
through untouched.

Deliberate divergences from legacy source-compatibility — the ONLY ones,
all of them builders conventions:

- **kwargs only**: no positional arguments, no ``name::dtype`` shorthand
  (inconsistent even in the legacy — doc `01` §5.3).
- **explicit containers**: the legacy grammar methods created the plural
  containers lazily (``table()`` materialized ``tables``); here the
  author writes them (``pkg.tables().table(...)``) — clarity over magic.
- **no silent string-to-bool coercion**: the legacy coerced string
  ``indexed``/``unique`` flags via ``gnrstring.boolean`` (doc `01` §1.6);
  here a boolean attribute must be a real bool.
- **loud errors, no silent fallbacks**: illegal placements and duplicate
  names raise (contrast the legacy ``addRelation`` swallowing every
  exception — doc `01` §5.10). Two siblings with the same ``name`` in a
  keyed collection raise instead of silently overwriting.

A virtual column whose name clashes with a **physical** column no longer
clashes at grammar time (separate containers); the legacy raised unless
``_override=True``. That coherence check — and the ``_override``
replacement used by extension packages customizing a base model — belong
to the build/validation step; collection customization is tracked in
genro-builders#31.

Not grammar (excluded, see doc `05` §5.4): ``sysFields`` is a legacy
helper method, not an element. Backend-specific vocabulary (Postgres
``extension``/``eventTrigger``/``dbtype``) belongs in a composable
backend mixin (doc `05` §5.3), not here.
"""

from __future__ import annotations

from genro_builders.builder import element

# The virtual-column family: every non-persisted column kind. They all
# live in the ``virtual_columns`` container and can host a relation.
_VIRTUAL_TAGS = (
    "virtual_column, aliasColumn, formulaColumn, "
    "pyColumn, subQueryColumn, compositeColumn"
)


class LegacySqlElements:
    """Grammar mixin for LegacySqlBuilder — the legacy SQL-model dialect."""

    # -- containers (explicit, fixed label, own keyspace) ----------------

    @element(sub_tags="package", collection_key="name",
             node_label="packages")
    def packages(self):
        """The container of the packages — the root of a legacy model
        tree. Fixed label ``packages``; children are keyed by ``name``
        (path: ``packages.<pkg>``).
        """
        ...

    @element(sub_tags="table", collection_key="name",
             node_label="tables", parent_tags="package")
    def tables(self):
        """The container of a package's tables. Fixed label ``tables``;
        children are keyed by ``name`` (path:
        ``packages.<pkg>.tables.<table>``).
        """
        ...

    @element(sub_tags="column", collection_key="name",
             node_label="columns", parent_tags="table")
    def columns(self):
        """The container of a table's **physical** columns. Fixed label
        ``columns``; children are keyed by ``name``. Its keyspace is its
        own: a virtual column or an index may carry the same name without
        clashing (they live in their own containers).
        """
        ...

    @element(sub_tags=_VIRTUAL_TAGS, collection_key="name",
             node_label="virtual_columns", parent_tags="table")
    def virtual_columns(self):
        """The container of a table's **virtual** (non-persisted)
        columns — the whole family: ``virtual_column``, ``aliasColumn``,
        ``formulaColumn``, ``pyColumn``, ``subQueryColumn``,
        ``compositeColumn``. Fixed label ``virtual_columns``; children
        are keyed by ``name``, in a keyspace separate from the physical
        ``columns``.
        """
        ...

    @element(sub_tags="index", node_label="indexes", parent_tags="table")
    def indexes(self):
        """The container of a table's indexes. Fixed label ``indexes``.
        No natural key: children are auto-labelled (``index_0``, …), so
        an ``index`` needs no ``name`` — the migrator generates a
        deterministic hashed name downstream when one is absent.
        """
        ...

    # -- structure ------------------------------------------------------

    @element(sub_tags="tables[:1]", parent_tags="packages")
    def package(self, name: str, sqlschema: str | None = None,
                comment: str | None = None, name_short: str | None = None,
                name_long: str | None = None, name_full: str | None = None):
        """A package: the **logical** namespace grouping tables (legacy
        `package`, doc `01` §1.1). It often coincides with an SQL schema
        (package ``fatt`` → schema ``fatt``) but the two are distinct
        concepts: the package groups tables for the application, the
        schema is where they physically live — ``sqlschema`` exists
        precisely for when they diverge.

        Physical: ``sqlschema`` (the SQL schema the tables live in),
        ``sqlprefix`` (table-name prefixing: falsy = bare name, ``True`` =
        ``<pkg>_<table>``, a string = custom prefix). Semantic (open):
        ``comment``, ``name_short``, ``name_long``, ``name_full``,
        ``pkgcode``, ``multi_tenant`` (inherited by the tables).
        """
        ...

    @element(sub_tags="columns[:1], virtual_columns[:1], indexes[:1]",
             parent_tags="tables")
    def table(self, name: str, pkey: str | None = None,
              lastTS: str | None = None, rowcaption: str | None = None,
              sqlname: str | None = None, sqlschema: str | None = None,
              comment: str | None = None, name_short: str | None = None,
              name_long: str | None = None, name_full: str | None = None):
        """A table. Its children are the three containers (``columns``,
        ``virtual_columns``, ``indexes``), at most one each.

        Physical: ``pkey`` (primary-key column name; a composite pkey is a
        comma-joined list ``"a,b"`` — the members must be real columns),
        ``sqlname`` (explicit SQL table name; defaults downstream to
        ``<pkg>_<table>`` via ``sqlprefix``), ``sqlschema`` (overrides the
        package schema; multi-tenant aware). Semantic (open): ``lastTS``,
        ``rowcaption`` / ``caption_field`` (record label), ``name_plural``,
        ``newrecord_caption``, ``queryfields``, ``logicalDeletionField``,
        ``draftField``, ``noChangeMerge``, ``mixin`` (per-table Python
        class), ``partition_*``, ``multi_tenant``, ``name_*``.
        """
        ...

    # -- column family (each carries at most one relation) --------------

    @element(sub_tags="relation[:1]", parent_tags="columns")
    def column(self, name: str, dtype: str | None = None, size=None,
               default=None, notnull: bool | None = None,
               unique: bool | None = None, indexed: bool | None = None,
               sqlname: str | None = None, comment: str | None = None,
               name_short: str | None = None, name_long: str | None = None,
               name_full: str | None = None, group: str | None = None,
               onInserting: str | None = None, onUpdating: str | None = None,
               onDeleting: str | None = None, localized=None,
               variant: str | None = None):
        """A physical (persisted) column — the one that becomes a real
        table column in the DDL (doc `01` §1.6).

        Physical: ``dtype`` (Genro normalized type code, default ``'T'``),
        ``size`` (``'n'`` fixed or ``'min:max'``), ``default``, ``notnull``,
        ``unique``, ``indexed``, ``sqlname``. Semantic (open): ``group``
        (UI grouping; a leading ``_`` marks the column reserved/hidden),
        ``comment``, ``name_short``/``name_long``/``name_full``,
        ``readonly``, ``encrypted``, ``localized`` (per-language column),
        ``variant`` + ``variant_*`` (derived read-only projections), and
        the field triggers ``onInserting``/``onUpdating``/``onDeleting``
        (and their ``…ed`` counterparts).

        Divergence from legacy: ``indexed``/``unique`` must be real booleans
        (no string coercion), and there is no ``name::dtype`` shorthand.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def virtual_column(self, name: str, relation_path: str | None = None,
                       sql_formula: str | None = None, select=None,
                       exists=None, py_method: str | None = None,
                       variant: str | None = None):
        """A virtual (non-persisted) column — the generic base of the
        virtual family (doc `01` §1.7). It is not stored; it is computed
        or navigated at query time. Exactly one of the computation attrs
        is given: ``relation_path`` (navigate a related column),
        ``sql_formula`` (an SQL expression over ``$col`` tokens),
        ``select`` / ``exists`` (a sub-select), or ``py_method`` (compute
        in Python). ``dtype`` types the result. The other column kinds
        (aliasColumn/formulaColumn/…) are thin wrappers over this element.

        A name clash **within** ``virtual_columns`` raises (duplicate
        collection key). A clash with a **physical** column does not — the
        containers keep separate keyspaces; the legacy raised unless
        ``_override=True`` (replace the physical column, used by extension
        packages customizing a base model). That coherence check and the
        replacement belong to the build/validation step; collection
        customization is tracked in genro-builders#31.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def aliasColumn(self, name: str, relation_path: str):
        """A virtual column that simply **projects a column of a related
        table** through a relation path (doc `01` §1.8). Attr:
        ``relation_path`` (``@relation.column``, e.g. ``@customer_id.name``
        to surface the customer's name on the invoice). It carries no value
        of its own — it is a read-through to the target column.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def formulaColumn(self, name: str, sql_formula: str | None = None,
                      select=None, exists=None, dtype: str | None = None):
        """A virtual column defined by an **SQL expression** evaluated by
        the database (doc `01` §1.14). One of ``sql_formula`` (an
        expression over ``$col`` tokens, e.g. ``upper($name)``), ``select``
        (a scalar sub-select) or ``exists`` (an EXISTS predicate);
        ``dtype`` defaults downstream to ``'A'`` (alphanumeric). The SQL
        is evaluated by the database, not computed in Python.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def pyColumn(self, name: str, py_method: str | None = None):
        """A virtual column **computed in Python** on the loaded record
        (doc `01` §1.15), for values SQL cannot express. Attr:
        ``py_method`` — the name of the method on the table's Python class
        that returns the value; when omitted the legacy convention is the
        method ``pyColumn_<name>`` (applied downstream). Unlike a
        formulaColumn it is not queryable in SQL: it exists only once the
        record is in memory.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def subQueryColumn(self, name: str, query=None, mode: str | None = None):
        """A virtual column defined by a **correlated sub-query** that
        aggregates related rows (doc `01` §1.13). Attrs: ``query`` (the
        sub-query definition) and ``mode``:

        - ``'json'`` — aggregate the related rows into a JSON array
          (``json_agg`` of ``row_to_json``);
        - ``'xml'`` — aggregate into XML (``xmlagg`` of ``xmlforest``);
          ``query`` must carry a ``columns`` list;
        - anything else (or omitted) — a **scalar aggregate**: a plain
          sub-select where ``mode`` names the aggregation function
          (``sum``, ``count``, …), or a bare scalar sub-select.

        The json/xml expansion into backend SQL is the renderer's job, not
        the grammar's (doc `05` §3 q7): the element only stores intent.
        """
        ...

    @element(sub_tags="relation[:1]", parent_tags="virtual_columns")
    def compositeColumn(self, name: str, columns: str | None = None,
                        static: bool | None = None):
        """A virtual column that **packs N physical columns into one
        named, navigable key** (doc `01` §1.10). Attr: ``columns`` (the
        comma-joined member column names, all of which must be real
        physical columns); ``static`` defaults downstream to ``True``.

        It generates a single composite value (the legacy builds a
        JSON-array text expression, ``dtype='JS'``) so that a multi-column
        key behaves like one column. It is THE mechanism for composite
        keys: a composite primary key, a composite unique, and — by
        hosting a ``relation`` — a composite foreign key are all expressed
        as one compositeColumn instead of table-level column lists.
        """
        ...

    # -- relation (declared on any column kind) -------------------------

    @element(sub_tags="")
    def relation(self, related_column: str | None = None,
                 mode: str | None = None, one_name: str | None = None,
                 many_name: str | None = None, eager_one=None,
                 eager_many=None, one_one: str | None = None, child=None,
                 one_group: str | None = None, many_group: str | None = None,
                 onUpdate: str | None = None, onUpdate_sql: str | None = None,
                 onDelete: str | None = None, onDelete_sql: str | None = None,
                 deferred: bool | None = None,
                 relation_name: str | None = None,
                 onDuplicate: str | None = None):
        """A relationship, declared as a child of the column that carries
        the key (doc `01` §1.18). It can sit on **any** column kind —
        physical or virtual — and there is at most one per column:
        cardinality is ``[:1]`` from this column's side (a foreign-key
        column points at one target row).

        The legacy dual plane is preserved verbatim. The **semantic /
        application** plane describes the relationship to the app:
        ``related_column`` (the target ``pkg.table.column``), ``mode``
        (default downstream ``'relation'``), ``one_name`` / ``many_name``
        (human labels of the two directions), ``relation_name`` (the
        inverse navigation name on the one-side), ``one_one``, ``child``,
        ``one_group`` / ``many_group``, ``eager_one`` / ``eager_many``,
        ``onDelete`` / ``onUpdate`` (what the application does on the
        parent event), ``onDuplicate``. The **physical / FK-constraint**
        plane describes the SQL foreign key the migrate emits:
        ``onDelete_sql`` / ``onUpdate_sql`` (default downstream
        ``'cascade'``) and ``deferred`` (deferrable constraint).

        The two ``onDelete`` planes exist because they answer different
        questions: ``onDelete`` is application logic run by GenroPy when a
        parent record is deleted, whereas ``onDelete_sql`` is the actual
        ``ON DELETE`` clause of the SQL foreign-key constraint — a
        relationship can be navigable and cascade at the app level without
        emitting any physical FK at all. Open kwargs (``cnd``,
        ``join_on``, ``between``, ``storefield``, ``external_relation``,
        ``resolver_*``, ``meta_*``, …) land as node attributes untouched.
        """
        ...

    # -- indexes --------------------------------------------------------

    @element(sub_tags="", parent_tags="indexes")
    def index(self, columns: str | None = None, name: str | None = None,
              unique: bool | None = None, method: str | None = None,
              where: str | None = None, tablespace: str | None = None,
              with_options: dict | None = None):
        """A table index (doc `01` §1.17).

        ``columns`` — the indexed column(s), comma-joined and ordered;
        ``unique`` — uniqueness constraint on the index; ``name`` — the
        SQL index name, **optional**: when a model reaches the migrator
        without one, the migrator generates a deterministic hashed name
        (the legacy ORM used ``<table>_<columns>_key``).

        Beyond-legacy attributes, already consumed by the migrator:
        ``method`` (access method: ``btree`` default, ``gin``, ``gist``,
        …), ``where`` (predicate of a partial index), ``tablespace``, and
        ``with_options`` (dict of storage ``WITH`` options).
        """
        ...
