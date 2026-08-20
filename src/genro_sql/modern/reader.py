# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Reverse projection: normalized migration JSON back into a model tree.

The inverse of :class:`~genro_sql.modern.migration.SqlMigrationRenderer`,
and the analogue of :func:`genro_sqlmigration.xml_producer.struct_to_xml`
for the recipe form: it de-normalizes ``structure-1.0`` into the grammar
of :class:`~genro_sql.modern.builder.SqlBuilder`, so a database that only
exists as introspected JSON becomes a source tree — and, through
:class:`~genro_sql.modern.emitter.SqlPythonEmitter`, a Python recipe.

The law it answers to is exact round-tripping::

    render(SqlModelReader(structure).to_builder()) == structure

so nothing is invented and nothing is dropped. Two consequences shape the
whole module:

- **structural hashes are not recipe names, where a name is optional**.
  A relation comes back anonymous and a hash-named UNIQUE constraint comes
  back as ``unique=True`` on a composite. An index is the exception: its
  name is the grammar's collection key AND the physical ``index_name``
  echoed into the JSON, so it travels verbatim — dropping it would rename
  the index in the database.
- **the sugar is not re-derived**. ``indexed=True`` and the automatic
  index of a foreign key (D3) are authoring conveniences of the forward
  path; here every index in the JSON is written out as a real ``index``
  element, and a foreign key whose supporting index is absent from the
  JSON carries ``indexed=False``.

A multi-column foreign key returns as a ``compositeColumn`` named
``"_".join(columns)`` (D4), on both sides of the relation when the target
columns are not the target's pkey. Anything the ``structure-1.0``
contract does not declare — an unknown attribute key, an event trigger —
is a loud error naming its JSON path: this reader conserves nothing it
cannot express.
"""

from __future__ import annotations

from genro_sqlmigration.structures import COL_JSON_KEYS

from .builder import SqlBuilder
from .common import INDEX_OPTIONS as _INDEX_OPTIONS
from .common import split_names as _names

#: Table attribute keys the grammar can express.
_TABLE_KEYS = frozenset({"pkeys", "comment"})

#: Relation attribute keys the grammar can express.
_RELATION_KEYS = frozenset({
    "columns", "constraint_name", "constraint_type", "related_schema",
    "related_table", "related_columns", "on_delete", "on_update",
    "deferrable", "initially_deferred",
})

#: Constraint attribute keys the grammar can express.
_CONSTRAINT_KEYS = frozenset({
    "columns", "constraint_name", "constraint_type", "check_clause",
})

#: Index attribute keys the grammar can express.
_INDEX_KEYS = frozenset({
    "columns", "index_name", "unique", "method", "where", "tablespace",
    "with_options",
})


class SqlModelReadError(ValueError):  # wf:phase-6:new
    """The JSON carries something the modern grammar cannot express.

    Args:
        path: the JSON path of the offending entity.
        message: what is wrong with it.
    """

    def __init__(self, path: str, message: str) -> None:  # wf:phase-6:new
        self.path = path
        super().__init__(f"{path}: {message}")


class _ImportedModel(SqlBuilder):  # wf:phase-6:new
    """Anonymous recipe whose document is built by the reader."""

    def __init__(self, populate) -> None:  # wf:phase-6:new
        self._populate = populate
        super().__init__()

    def main(self, root) -> None:  # wf:phase-6:new
        self._populate(root)


class SqlModelReader:  # wf:phase-6:new
    """Build a SQL model tree out of a normalized ``structure-1.0`` dict.

    Args:
        normalized: the migration JSON, ``{'root': {...}}``.
    """

    def __init__(self, normalized: dict) -> None:  # wf:phase-6:new
        self.normalized = normalized

    def to_builder(self) -> SqlBuilder:  # wf:phase-6:new
        """De-normalize the structure into a created, validated model.

        Returns:
            A created :class:`~genro_sql.modern.builder.SqlBuilder` whose
            source tree projects back to the structure it was read from.

        Raises:
            SqlModelReadError: the JSON declares something outside the
                modern grammar.
            SqlModelValidationError: the resulting model is inconsistent.
        """
        model = _ImportedModel(self._build)
        model.create()
        return model.validate_model()

    # -- document --------------------------------------------------------

    def _build(self, root_node) -> None:  # wf:phase-6:new
        root = self.normalized["root"]
        if root.get("event_triggers"):
            raise SqlModelReadError(
                "root.event_triggers",
                "event triggers are outside the modern grammar",
            )
        self._plan_composites(root)
        db = root_node.db(name=root.get("entity_name"))
        tables = {}
        for schema_name, schema in root.get("schemas", {}).items():
            schema_node = db.schema(name=schema_name)
            for table_name, table in schema.get("tables", {}).items():
                tables[(schema_name, table_name)] = self._add_table(
                    schema_node, schema_name, table_name, table,
                )
        for extension_name, extension in root.get("extensions", {}).items():
            self._check_keys(
                f"root.extensions.{extension_name}",
                extension.get("attributes") or {}, frozenset(),
            )
            db.extension(name=extension_name)
        for table in tables.values():
            self._fill_relations(table)
            self._fill_constraints(table)
            self._fill_indexes(table)

    def _add_table(self, schema_node, schema_name, table_name,
                   table) -> dict:  # wf:phase-6:new
        path = self._table_path(schema_name, table_name)
        attributes = table.get("attributes") or {}
        self._check_keys(path, attributes, _TABLE_KEYS)
        kwargs = {"name": table_name}
        if attributes.get("pkeys"):
            kwargs["pkey"] = attributes["pkeys"]
        if attributes.get("comment"):
            kwargs["comment"] = attributes["comment"]
        node = schema_node.table(**kwargs)
        pkey = _names(attributes.get("pkeys"))
        columns = {}
        for column_name, column in table.get("columns", {}).items():
            columns[column_name] = self._add_column(
                node, path, column_name, column, pkey,
            )
        composites = {}
        for name, members in self._composites[(schema_name, table_name)].items():
            if name in columns:
                raise SqlModelReadError(
                    f"{path}.columns.{name}",
                    f"the composite '{name}' synthesized for columns "
                    f"{', '.join(members['columns'])} collides with a column "
                    "of the same name",
                )
            composites[name] = node.compositeColumn(
                name=name, columns=",".join(members["columns"]),
                **({"unique": True} if members["unique"] else {}),
            )
        return {"node": node, "path": path, "json": table, "pkey": pkey,
                "columns": columns, "composites": composites}

    def _add_column(self, table_node, path, column_name, column,
                    pkey):  # wf:phase-6:new
        attributes = dict(column.get("attributes") or {})
        self._check_keys(
            f"{path}.columns.{column_name}", attributes, COL_JSON_KEYS,
        )
        if column_name in pkey:
            attributes.pop("notnull", None)
        return table_node.column(name=column_name, **attributes)

    # -- composites ------------------------------------------------------

    def _plan_composites(self, root) -> None:  # wf:phase-6:new
        """Collect every composite the relations and constraints need.

        Both sides of a multi-column foreign key need one, and the target
        side belongs to a table that may be built before the relation is
        read — so the whole plan is computed before the first element is
        mounted.
        """
        self._composites: dict[tuple[str, str], dict] = {}
        self._pkeys: dict[tuple[str, str], list[str]] = {}
        for schema_name, schema in root.get("schemas", {}).items():
            for table_name, table in schema.get("tables", {}).items():
                key = (schema_name, table_name)
                self._composites[key] = {}
                self._pkeys[key] = _names(
                    (table.get("attributes") or {}).get("pkeys"),
                )
        for schema_name, schema in root.get("schemas", {}).items():
            for table_name, table in schema.get("tables", {}).items():
                key = (schema_name, table_name)
                for relation in table.get("relations", {}).values():
                    self._plan_relation_composites(key, relation)
                for name, constraint in table.get("constraints", {}).items():
                    self._plan_constraint_composite(key, name, constraint)

    def _plan_relation_composites(self, key, relation) -> None:  # wf:phase-6:new
        attributes = relation["attributes"]
        columns = _names(attributes.get("columns"))
        if len(columns) > 1:
            self._need_composite(key, columns)
        target = (attributes.get("related_schema"),
                  attributes.get("related_table"))
        related = _names(attributes.get("related_columns"))
        if len(related) > 1 and related != self._pkeys.get(target):
            self._need_composite(target, related)

    def _plan_constraint_composite(self, key, name,
                                   constraint) -> None:  # wf:phase-6:new
        attributes = constraint["attributes"]
        if attributes.get("constraint_type") == "CHECK":
            return
        if attributes.get("constraint_name") != name:
            return
        self._need_composite(key, _names(attributes.get("columns")),
                             unique=True)

    def _need_composite(self, key, columns, unique=False) -> str:  # wf:phase-6:new
        """Register the deterministic composite over ``columns`` (D4)."""
        name = "_".join(columns)
        planned = self._composites[key].setdefault(
            name, {"columns": columns, "unique": False},
        )
        planned["unique"] = planned["unique"] or unique
        return name

    # -- second pass -----------------------------------------------------

    def _fill_relations(self, table) -> None:  # wf:phase-6:new
        indexed = {
            tuple(_names(index["attributes"].get("columns")))
            for index in table["json"].get("indexes", {}).values()
        }
        for name, relation in table["json"].get("relations", {}).items():
            attributes = relation["attributes"]
            self._check_keys(
                f"{table['path']}.relations.{name}", attributes,
                _RELATION_KEYS,
            )
            columns = _names(attributes.get("columns"))
            owner = (table["columns"][columns[0]] if len(columns) == 1
                     else table["composites"]["_".join(columns)])
            kwargs = {"to": self._target(attributes), "foreign_key": True}
            for action in ("on_delete", "on_update"):
                if attributes.get(action):
                    kwargs[action] = attributes[action]
            if attributes.get("deferrable"):
                kwargs["deferred"] = True
            if tuple(columns) not in indexed:
                kwargs["indexed"] = False
            owner.relation(**kwargs)

    def _target(self, attributes) -> str:  # wf:phase-6:new
        """``relation.to`` for a foreign key, in its shortest exact form."""
        schema_name = attributes.get("related_schema")
        table_name = attributes.get("related_table")
        columns = _names(attributes.get("related_columns"))
        if len(columns) == 1:
            return f"{schema_name}.{table_name}.{columns[0]}"
        if columns == self._pkeys.get((schema_name, table_name)):
            return f"{schema_name}.{table_name}"
        return f"{schema_name}.{table_name}.{'_'.join(columns)}"

    def _fill_constraints(self, table) -> None:  # wf:phase-6:new
        for name, constraint in table["json"].get("constraints", {}).items():
            attributes = constraint["attributes"]
            path = f"{table['path']}.constraints.{name}"
            self._check_keys(path, attributes, _CONSTRAINT_KEYS)
            constraint_name = attributes.get("constraint_name")
            if attributes.get("constraint_type") == "CHECK":
                table["node"].constraint(
                    name=constraint_name, constraint_type="CHECK",
                    check_clause=attributes.get("check_clause"),
                )
            elif constraint_name != name:
                table["node"].constraint(
                    name=constraint_name, constraint_type="UNIQUE",
                    columns=",".join(_names(attributes.get("columns"))),
                )

    def _fill_indexes(self, table) -> None:  # wf:phase-6:new
        for name, index in table["json"].get("indexes", {}).items():
            attributes = index["attributes"]
            self._check_keys(
                f"{table['path']}.indexes.{name}", attributes, _INDEX_KEYS,
            )
            kwargs = {"columns": attributes.get("columns"),
                      "name": attributes.get("index_name")}
            for option in _INDEX_OPTIONS:
                if attributes.get(option):
                    kwargs[option] = attributes[option]
            table["node"].index(**kwargs)

    # -- strictness ------------------------------------------------------

    @staticmethod
    def _table_path(schema_name, table_name) -> str:  # wf:phase-6:new
        return f"root.schemas.{schema_name}.tables.{table_name}"

    @staticmethod
    def _check_keys(path, attributes, declared) -> None:  # wf:phase-6:new
        """Refuse any attribute key outside the ``structure-1.0`` set."""
        for key in attributes:
            if key not in declared:
                raise SqlModelReadError(
                    f"{path}.attributes.{key}",
                    "attribute is not part of the structure-1.0 contract "
                    f"({', '.join(sorted(declared))})",
                )


__all__ = ["SqlModelReadError", "SqlModelReader"]
