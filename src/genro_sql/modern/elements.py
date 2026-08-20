# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL model grammar — element definitions (optimized dialect).

Four grammar mixins, one per containment level, composed into
:class:`~genro_sql.modern.builder.SqlBuilder`:

- :class:`DbElements` — ``db``, ``extension``
- :class:`SchemaElements` — ``schema``
- :class:`TableElements` — ``table`` and everything a table holds
- :class:`ColumnElements` — ``relation``

Hierarchy::

    db
    ├── schema
    │   └── table
    │       ├── column / aliasColumn / formulaColumn / subQueryColumn /
    │       │   pyColumn / compositeColumn
    │       │   └── relation          (column and compositeColumn only)
    │       ├── constraint
    │       └── index
    └── extension

Two planes. The **physical** plane projects into the genro-sqlmigration
JSON (``structure-1.0``): ``db``/``schema``/``table``, physical ``column``
attributes, ``foreign_key`` relations, ``constraint``, ``index``. The
**semantic** plane (``name_*``, ``group``, ``caption_field``, …) travels as
node attributes the migration projection ignores; the compiler and the GUI
read it.

Signatures are **semi-closed**: every element declares its physical AND its
enumerated semantic parameters, typed, and accepts ``**extra`` on top. The
grammar takes any extra key; the domain validator requires it to start with
``x_``, so a typo (``dtypo=``) is a loud error naming the declared set
instead of a silently stored attribute.

``db``, ``schema`` and ``table`` are name-keyed collections
(``collection_key="name"``): a node is addressed by its own name
(``db.public.recipe.id``) — a 1:1 map onto the name-keyed dicts of the
migration JSON.

Projection flags ride on each element's ``_meta`` and are read from the node
(``node._get_meta("projects_column")``): the renderer and the validators
dispatch on them, never on tag strings.
"""

from __future__ import annotations

from typing import Literal

from genro_builders.builder import element

#: Genro normalized type codes. Mirrors
#: ``genro_sqlmigration.structures.DTYPE_CODES`` — declared locally because
#: the grammar must not import the migration package (the dependency is
#: one-way). The renderer's golden test asserts the two stay in step.
DTYPE = Literal[
    "A", "B", "C", "D", "DH", "DHZ", "DT", "H", "HZ", "I", "L", "M", "N",
    "O", "P", "R", "T", "TSV", "VEC", "X", "Z", "jsonb", "serial",
]

#: Referential actions a foreign key may declare. ``NO ACTION`` is absent on
#: purpose: it is the SQL default and the migration structure strips it.
FK_ACTION = Literal["CASCADE", "SET NULL", "SET DEFAULT", "RESTRICT"]

#: Table constraint kinds. Single-column uniqueness is the ``unique`` column
#: attribute, not a constraint entity.
CONSTRAINT_TYPE = Literal["UNIQUE", "CHECK"]

# Column-family tags. Only ``column`` and ``compositeColumn`` project
# physically, but every kind is a table child.
_COLUMN_TAGS = (
    "column, aliasColumn, formulaColumn, subQueryColumn, "
    "pyColumn, compositeColumn"
)


class DbElements:
    """Database-level grammar: the root and its extensions."""

    @element(sub_tags="schema, extension", collection_key="name",
             node_label="db")
    def db(self, name: str):
        """Database root, one per model.

        Args:
            name: the database name — the JSON ``entity_name``.
        """
        ...

    @element(sub_tags="")
    def extension(self, name: str, **extra):
        """A PostgreSQL extension.

        Rendered ``CREATE EXTENSION IF NOT EXISTS`` and never dropped.

        Args:
            name: the extension name (``pg_trgm``, ``unaccent``, …).
        """
        ...


class SchemaElements:
    """Schema-level grammar."""

    @element(sub_tags="table", collection_key="name")
    def schema(self, name: str, comment: str = None, **extra):
        """A database schema (a 'package' in the legacy vocabulary).

        Args:
            name: the schema name — physical, and this node's key.
            comment: semantic; free description.
        """
        ...


class TableElements:
    """Table-level grammar: the table and everything it holds."""

    @element(sub_tags=f"{_COLUMN_TAGS}, constraint, index",
             collection_key="name")
    def table(self, name: str, pkey: str = None, comment: str = None,
              caption_field: str = None, name_long: str = None,
              name_plural: str = None, **extra):
        """A table.

        Args:
            name: the table name — physical, and this node's key.
            pkey: comma-joined physical column names, the JSON ``pkeys``.
                Every name must exist among the table's physical columns.
            comment: semantic; free description.
            caption_field: semantic; the column that captions a row.
            name_long: semantic; human label.
            name_plural: semantic; human label, plural form.
        """
        ...

    @element(sub_tags="relation[0:1]",
             _meta={"projects_column": True, "projects_relation": True})
    def column(self, name: str, dtype: DTYPE = None, size: str = None,
               notnull: bool = False, unique: bool = False,
               indexed: bool = False, sqldefault: str = None,
               sql_type: str = None, extra_sql: str = None,
               generated_expression: str = None, comment: str = None,
               name_long: str = None, name_short: str = None,
               group: str = None, **extra):
        """A physical column — the only element that projects as a column.

        Args:
            name: the column name — physical, and this node's key.
            dtype: Genro normalized type code. Absent, the renderer
                defaults to ``'A'`` when ``size`` is given, else ``'T'``.
            size: ``'n'`` or ``'min:max'`` character size.
            notnull: NOT NULL. Pkey members get it from their pkey
                membership, not from this flag.
            unique: single-column UNIQUE. A redundant one on a
                single-column pkey is dropped by the renderer.
            indexed: sugar — the renderer materializes a real index item
                (``structure-1.0`` has no ``indexed`` column attribute).
                A column carrying a foreign key is always indexed.
            sqldefault: SQL DEFAULT expression.
            sql_type: native type, the escape hatch; wins over ``dtype``.
            extra_sql: verbatim tail of the column definition.
            generated_expression: GENERATED ALWAYS AS expression.
            comment: physical; the column comment.
            name_long: semantic; human label.
            name_short: semantic; human label, short form.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="")
    def aliasColumn(self, name: str, relation_path: str,
                    name_long: str = None, group: str = None, **extra):
        """A virtual column projecting a related column. Never physical.

        An alias reads through a relation that already exists, so it never
        carries one of its own.

        Args:
            name: the alias name.
            relation_path: ``@relation.column`` path to the source column.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="")
    def formulaColumn(self, name: str, sql_formula: str = None,
                      select: str = None, exists: str = None,
                      dtype: DTYPE = None, name_long: str = None,
                      group: str = None, **extra):
        """A virtual column defined by SQL. Never physical.

        Args:
            name: the column name.
            sql_formula: an expression over the row's own columns.
            select: a scalar sub-select.
            exists: an EXISTS predicate.
            dtype: the resulting type code.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="")
    def subQueryColumn(self, name: str, query: str, mode: str = None,
                       name_long: str = None, group: str = None, **extra):
        """A virtual column defined by a sub-query. Never physical.

        Args:
            name: the column name.
            query: the sub-query.
            mode: ``json``, ``xml`` or a scalar aggregate. Expanding it is
                the renderer's job, not grammar-time.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="")
    def pyColumn(self, name: str, py_method: str = None, dtype: DTYPE = None,
                 name_long: str = None, group: str = None, **extra):
        """A virtual column computed in Python. Never physical.

        Args:
            name: the column name.
            py_method: the method computing it; defaults to
                ``pyColumn_<name>`` on the table class.
            dtype: the resulting type code.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="relation[0:1]", _meta={"projects_relation": True})
    def compositeColumn(self, name: str, columns: str, unique: bool = False,
                        name_long: str = None, group: str = None, **extra):
        """N physical columns packed as one navigable key.

        Not a column of its own — it projects no column, only what its
        members already are. THE mechanism for a multi-column key: a
        composite FK is a ``relation`` on a compositeColumn, and a
        composite UNIQUE is ``unique=True`` here.

        Args:
            name: the composite name (legacy ``composed_of`` carried the
                members instead).
            columns: comma-joined member names, all physical columns of
                the same table.
            unique: projects a multi-column UNIQUE constraint.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(sub_tags="", collection_key="name")
    def constraint(self, name: str, constraint_type: CONSTRAINT_TYPE,
                   columns: str = None, check_clause: str = None, **extra):
        """A table constraint.

        Args:
            name: the constraint name — this node's key.
            constraint_type: ``'UNIQUE'`` (needs ``columns``) or
                ``'CHECK'`` (needs ``check_clause``).
            columns: comma-joined physical column names.
            check_clause: the CHECK expression.
        """
        ...

    @element(sub_tags="")
    def index(self, name: str = None, columns: object = None,
              unique: bool = False, method: str = None, where: str = None,
              tablespace: str = None, with_options: dict = None, **extra):
        """A table index.

        Args:
            name: the index name.
            columns: comma-joined names, or a ``{name: None | 'DESC'}``
                dict when per-column ordering matters.
            unique: a UNIQUE index.
            method: access method (``btree``, ``gin``, …).
            where: partial-index predicate.
            tablespace: target tablespace.
            with_options: storage parameters.
        """
        ...


class ColumnElements:
    """Column-level grammar: the relation."""

    @element(sub_tags="")
    def relation(self, to: str, foreign_key: bool = False,
                 on_delete: FK_ACTION = None, on_update: FK_ACTION = None,
                 deferred: bool = False, back_reference: str = None,
                 one_name: str = None, many_name: str = None,
                 one_one: bool = False, case_insensitive: bool = False,
                 **extra):
        """A relation on a column. Navigable by default, physical on demand.

        Args:
            to: the target, ``schema.table.column`` or ``schema.table``
                (target columns default to the target pkey).
            foreign_key: emit a physical FK. Only these relations project
                into the migration JSON.
            on_delete: referential action on delete.
            on_update: referential action on update.
            deferred: INITIALLY DEFERRED.
            back_reference: semantic; navigable path of the many side.
            one_name: semantic; human label of the one side.
            many_name: semantic; human label of the many side.
            one_one: semantic; the relation is 1:1.
            case_insensitive: semantic; join case-insensitively.
        """
        ...
