# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL model grammar — element definitions (optimized dialect).

Grammar mixin for :class:`~genro_sql.sql_builder.SqlBuilder`. The design is
documented in ``roadmap/05_grammar_design.md``; this is the "optimized"
dialect (§2.4/§2.5 decisions), a superset of the legacy ``DbModelSrc``
vocabulary (inventory in ``roadmap/01_legacy_model_grammar.md``).

Hierarchy::

    db
    ├── schema
    │   ├── table
    │   │   ├── column / aliasColumn / formulaColumn / subQueryColumn /
    │   │   │   pyColumn / compositeColumn   (each carries one relation)
    │   │   ├── constraint
    │   │   ├── index
    │   │   └── trigger        (beyond legacy — migrator wave 2)
    │   ├── view               (beyond legacy — migrator wave 1)
    │   ├── function           (beyond legacy — migrator wave 2)
    │   ├── sequence           (beyond legacy — migrator wave 3)
    │   └── dbtype             (beyond legacy — migrator wave 3)
    ├── extension              (migrate-only in legacy)
    └── eventTrigger           (migrate-only in legacy — no-op today)

Two planes (§2.3). The **physical** plane projects into the
genro-sqlmigration JSON (``structure-1.0``): ``db``/``schema``/``table``,
physical ``column`` attributes, ``foreign_key`` relations, ``constraint``,
``index`` (plus the beyond-legacy entities the migrator waves consume). The
**semantic** plane (``name_*``, ``group``, ``caption_field``, triggers,
validators…) travels as open node attributes; the migrator projection
ignores it, the compiler/GUI read it.

Conventions (§2.5): element names ARE the grammar (documented — the SQL
model is a non-obvious domain); kwargs only, no ``name::dtype`` shorthand;
loud errors, no silent fallbacks. ``db``/``schema``/``table`` are name-keyed
collections (``collection_key="name"``): a node is addressed by its own
name (``public.recipe.id``) — a 1:1 map onto the name-keyed dicts of the
migration JSON.

Dialect-divergence register (forms deferred, resolved when the strict
dialect + migration land): ``caption_field`` (optimized primary) vs
``rowcaption`` (legacy template); attribute naming case (snake vs camel).
"""

from __future__ import annotations

from genro_builders.builder import element

# Column-family tags: every kind that can host a relation. Reused as the
# table's column-family sub_tags (kept in one place to stay in sync).
_COLUMN_TAGS = (
    "column, aliasColumn, formulaColumn, subQueryColumn, "
    "pyColumn, compositeColumn"
)


class SqlElements:
    """Grammar mixin for SqlBuilder — the optimized SQL-model dialect."""

    # -- structure ------------------------------------------------------

    @element(sub_tags="schema, extension, eventTrigger", collection_key="name")
    def db(self):
        """Database root. ``name`` -> the JSON ``entity_name`` (dbname)."""
        ...

    @element(sub_tags="table, view, function, sequence, dbtype",
             collection_key="name")
    def schema(self):
        """A database schema (legacy 'package').

        Physical: ``sqlschema``, ``sqlprefix``, ``multi_tenant``.
        Semantic (open): ``comment``, ``name_*``, ``pkgcode``.
        """
        ...

    @element(sub_tags=f"{_COLUMN_TAGS}, constraint, index, trigger",
             collection_key="name")
    def table(self):
        """A table.

        Physical: ``pkey`` (comma-joined physical column names, the JSON
        ``pkeys`` string). Semantic (open): ``comment``, ``caption_field``
        (optimized primary) / ``rowcaption`` (legacy template),
        ``name_plural``, ``lastTS``, ``logicalDeletionField``,
        ``draftField``, ``name_*``.
        """
        ...

    # -- column family (each carries at most one relation) --------------

    @element(sub_tags="relation[:1]")
    def column(self):
        """A physical column.

        Physical attrs projected to the migrator JSON (``COL_JSON_KEYS``):
        ``dtype``, ``size``, ``notnull``, ``sqldefault``, ``unique``,
        ``indexed``, ``sql_type``, ``extra_sql``, ``generated_expression``,
        ``comment``. ``dtype`` uses the Genro normalized codes; ``sql_type``
        is the native-type escape hatch and wins when present. Semantic
        (open): ``group``, ``readonly``, ``encrypted``, ``localized``,
        ``variant``, field triggers (``onInserting``/``onUpdating``/…),
        ``name_*``.
        """
        ...

    @element(sub_tags="relation[:1]")
    def aliasColumn(self):
        """A virtual column that projects a related column. Attr:
        ``relation_path`` (``@rel.column``). Does not project physically.
        """
        ...

    @element(sub_tags="relation[:1]")
    def formulaColumn(self):
        """A virtual column defined by SQL. One of ``sql_formula`` /
        ``select`` / ``exists``; ``dtype`` (default ``'A'``). Does not
        project physically.
        """
        ...

    @element(sub_tags="relation[:1]")
    def subQueryColumn(self):
        """A virtual column defined by a sub-query. Attrs: ``query``,
        ``mode`` (``json`` | ``xml`` | scalar-aggregate). Mode expansion is
        the renderer's job, not grammar-time (§3 q7). Does not project
        physically.
        """
        ...

    @element(sub_tags="relation[:1]")
    def pyColumn(self):
        """A virtual column computed in Python. Attr: ``py_method``
        (default ``pyColumn_<name>`` on the table class). Does not project
        physically.
        """
        ...

    @element(sub_tags="relation[:1]")
    def compositeColumn(self):
        """A column packing N physical columns as one navigable key
        (first-class, §2.2). Attr: ``columns`` (comma-joined member
        names). THE mechanism for composite pkey / unique / FK: a composite
        relation is a ``relation`` on one compositeColumn. Its members are
        physical, so a composite key projects as multi-column
        ``columns``/``related_columns`` in the migrator JSON.
        """
        ...

    # -- relation (declared on any column kind) -------------------------

    @element(sub_tags="")
    def relation(self):
        """A relation on a column. Logical/navigable by default; the
        physical FK is opt-in (``foreign_key=True``, §2.4).

        Attrs: ``to`` (target ``schema.table.column``; target columns
        default to the target pkey), ``foreign_key`` (default False),
        ``case_insensitive``, ``back_reference`` (navigable path of the
        many side, mandatory-with-error on ambiguity), ``one_name`` /
        ``many_name`` (human labels), ``navigable``, ``one_one``,
        ``on_delete`` / ``on_update`` (+ ``_sql`` physical variants),
        ``deferred``. Only ``foreign_key=True`` relations project into the
        migrator JSON; a relation under a virtual column cannot be a
        physical FK.
        """
        ...

    # -- secondary structures -------------------------------------------

    @element(sub_tags="", collection_key="name")
    def constraint(self):
        """A multi-column table constraint. ``constraint_type`` is
        ``'UNIQUE'`` (with ``columns``) or ``'CHECK'`` (with
        ``check_clause``). Single-column unique is the ``unique`` column
        attribute, not a constraint entity.
        """
        ...

    @element(sub_tags="", collection_key="name")
    def index(self):
        """A table index. Attrs: ``columns`` (ordered), ``unique``,
        ``method`` (btree/gin/…), ``where`` (partial), ``tablespace``.
        """
        ...

    # -- beyond-legacy entities (grammar slots; migrator waves 1-3) -----

    @element(sub_tags="", collection_key="name")
    def trigger(self):
        """A table SQL trigger (migrator wave 2). Attrs: ``timing``,
        ``events``, ``for_each``, ``function_name``, ``function_schema``,
        ``condition``, ``arguments``. Distinct from the application-level
        field triggers (``onInserting``/…), which are column/table
        attributes and do not project.
        """
        ...

    @element(sub_tags="", collection_key="name")
    def view(self):
        """A schema view (migrator wave 1). Attrs: ``definition`` (the
        SELECT — verbatim or compiled from a query), ``materialized``,
        ``columns``, ``with_data``, ``depends_on`` (dependency order).
        """
        ...

    @element(sub_tags="", collection_key="name")
    def function(self):
        """A schema function/procedure (migrator wave 2). Attrs:
        ``language``, ``return_type``, ``arguments``, ``body``,
        ``volatility``, ``security``, ``is_procedure``. The migrator keys
        functions by identity signature ``name(argtypes)`` for overloads;
        spell types canonically (``integer``, not ``int``).
        """
        ...

    @element(sub_tags="", collection_key="name")
    def sequence(self):
        """A standalone schema sequence (migrator wave 3). Attrs:
        ``start_value``, ``increment``, ``min_value``, ``max_value``,
        ``cycle``, ``owned_by``. Serial/IDENTITY sequences stay implicit
        (a column ``dtype``), not declared here.
        """
        ...

    @element(sub_tags="", collection_key="name")
    def dbtype(self):
        """A custom schema type (migrator wave 3). Attrs: ``type_kind``
        (``ENUM`` | ``DOMAIN`` | ``COMPOSITE`` | ``RANGE``),
        ``enum_values``, ``columns``, ``base_type``, ``constraint``. A
        column typed on a custom dbtype emits ``sql_type=<type name>``.
        """
        ...

    # -- database-level entities ----------------------------------------

    @element(sub_tags="", collection_key="name")
    def extension(self):
        """A PostgreSQL extension. Rendered ``CREATE EXTENSION IF NOT
        EXISTS`` — never dropped. Attrs: open (``attributes`` in the JSON).
        """
        ...

    @element(sub_tags="", collection_key="name")
    def eventTrigger(self):
        """A database-level event trigger. Introspected by the migrator but
        its handler is a deliberate no-op today (grammar slot).
        """
        ...
