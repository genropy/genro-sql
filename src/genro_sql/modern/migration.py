# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Projection of a SQL model tree into the normalized migration JSON.

The twin of :class:`genro_sqlmigration.JsonStructureProducer`: that one
reads the ergonomic human JSON, this one reads a built
:class:`~genro_sql.modern.builder.SqlBuilder` tree, and the two converge
on the same ``structure-1.0`` dict for the same physical model. The
normalization rules are not reimplemented here — every entity is built
by the ``genro_sqlmigration.structures`` factories, which own the
structural hashes and the attribute cleaning.

Only the physical plane travels. Virtual columns project nothing, a
relation projects only with ``foreign_key=True``, and the semantic
attributes (``name_*``, ``group``, ``one_name``, ``x_*``, …) stop at this
boundary by construction: each entity is filled from an enumerated key
set, never from the node's attribute dict.

Two grammar conveniences become real entities here:

- ``indexed=True`` on a column, and every foreign-key column, materialize
  an index item (``structure-1.0`` has no ``indexed`` column attribute);
  an index over exactly the pkey columns is skipped, the primary key
  already indexes them.
- ``unique=True`` on a ``compositeColumn`` becomes a multi-column UNIQUE
  constraint; single-column uniqueness stays the column attribute.
"""

from __future__ import annotations

from genro_sqlmigration import StructureValidator
from genro_sqlmigration.structures import (
    COL_JSON_KEYS,
    new_column_item,
    new_constraint_item,
    new_extension_item,
    new_index_item,
    new_relation_item,
    new_schema_item,
    new_structure_root,
    new_table_item,
)

from .validators import SqlModelValidator

#: Relation attributes that reach the JSON, mapped to their contract key.
_RELATION_ACTIONS = ("on_delete", "on_update")

#: Index attributes that reach the JSON when truthy.
_INDEX_OPTIONS = ("unique", "method", "where", "tablespace", "with_options")


def _names(value) -> list[str]:  # wf:phase-4:new
    """Column names out of a comma-joined string, a dict or a sequence."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return [name.strip() for name in str(value).split(",") if name.strip()]


class SqlMigrationRenderer:  # wf:phase-4:new
    """Render a built SQL model as the normalized ``structure-1.0`` JSON.

    Args:
        builder: a created :class:`~genro_sql.modern.builder.SqlBuilder`.
    """

    def __init__(self, builder) -> None:  # wf:phase-4:new
        self.builder = builder

    def render(self) -> dict:  # wf:phase-4:new
        """Project the model, a fresh structure each call.

        The model is domain-validated first and the result is passed
        through :class:`genro_sqlmigration.StructureValidator` before it
        is handed out, so nothing leaves this method that the migrator
        would refuse.

        Returns:
            The normalized structure, ``{'root': {...}}``.

        Raises:
            SqlModelValidationError: the model itself is inconsistent.
            SqlValidationError: the projection breaks the contract.
        """
        SqlModelValidator().validate(self.builder)
        self._collect()
        structure = new_structure_root(self._db_name)
        root = structure["root"]
        for schema_name in self._schemas:
            root["schemas"][schema_name] = new_schema_item(schema_name)
        for (schema_name, table_name), table in self._tables.items():
            root["schemas"][schema_name]["tables"][table_name] = self._table_item(
                schema_name, table_name, table,
            )
        for extension_name in self._extensions:
            root["extensions"][extension_name] = new_extension_item(extension_name)
        return StructureValidator().validate(structure)

    # -- collection ------------------------------------------------------

    def _collect(self) -> None:  # wf:phase-4:new
        """Index the source tree by schema and table, once per render."""
        self._db_name = None
        self._schemas: list[str] = []
        self._extensions: list[str] = []
        self._tables: dict[tuple[str, str], dict] = {}
        for path, node in self.builder.source.walk():
            parts = path.split(".")
            tag = node.node_tag
            if tag == "db":
                self._db_name = node.get_attr("name")
            elif tag == "extension":
                self._extensions.append(node.get_attr("name"))
            elif tag == "schema":
                self._schemas.append(parts[1])
            elif tag == "table":
                self._tables[(parts[1], parts[2])] = {
                    "node": node, "columns": {}, "composites": {},
                    "family": {}, "constraints": [], "indexes": [],
                    "relations": [],
                }
            elif tag == "relation":
                table = self._tables.get((parts[1], parts[2]))
                if table is not None:
                    table["relations"].append((parts[3], node))
            else:
                table = self._tables.get((parts[1], parts[2]))
                if table is None:
                    continue
                if tag == "constraint":
                    table["constraints"].append(node)
                elif tag == "index":
                    table["indexes"].append(node)
                else:
                    table["family"][parts[3]] = node
                    if node._get_meta("projects_column"):
                        table["columns"][parts[3]] = node
                    elif tag == "compositeColumn":
                        table["composites"][parts[3]] = node

    # -- projection ------------------------------------------------------

    def _table_item(self, schema_name, table_name, table) -> dict:  # wf:phase-4:new
        item = new_table_item(schema_name, table_name)
        pkey = table["node"].get_attr("pkey")
        if pkey:
            item["attributes"]["pkeys"] = pkey
        comment = table["node"].get_attr("comment")
        if comment:
            item["attributes"]["comment"] = comment
        pkey_columns = _names(pkey)
        for column_name, node in table["columns"].items():
            item["columns"][column_name] = self._column_item(
                schema_name, table_name, column_name, node, pkey_columns,
            )
        auto_index_columns = self._fill_relations(schema_name, table_name, table, item)
        self._fill_constraints(schema_name, table_name, table, item)
        self._fill_indexes(schema_name, table_name, table, item)
        for column_name, node in table["columns"].items():
            if node.get_attr("indexed"):
                auto_index_columns.append([column_name])
        self._fill_auto_indexes(
            schema_name, table_name, item, auto_index_columns, pkey_columns,
        )
        return item

    def _column_item(self, schema_name, table_name, column_name, node,
                     pkey_columns) -> dict:  # wf:phase-4:new
        attributes = {
            key: node.get_attr(key) for key in COL_JSON_KEYS
            if node.get_attr(key) is not None
        }
        if "dtype" not in attributes:
            attributes["dtype"] = "A" if attributes.get("size") else "T"
        if column_name in pkey_columns:
            attributes["notnull"] = "_auto_"
            if len(pkey_columns) == 1:
                attributes.pop("unique", None)
        return new_column_item(
            schema_name, table_name, column_name, attributes=attributes,
        )

    def _fill_relations(self, schema_name, table_name, table,
                        item) -> list[list[str]]:  # wf:phase-4:new
        """Project the foreign keys; return the columns they must index."""
        indexed: list[list[str]] = []
        for owner_name, node in table["relations"]:
            if not node.get_attr("foreign_key"):
                continue
            owner = table["family"].get(owner_name)
            if owner is None or not owner._get_meta("projects_relation"):
                continue
            columns = (_names(owner.get_attr("columns"))
                       if owner.node_tag == "compositeColumn" else [owner_name])
            target_schema, target_table, target_columns = self._resolve_target(node)
            attributes = {
                "related_schema": target_schema,
                "related_table": target_table,
                "related_columns": target_columns,
                "constraint_type": "FOREIGN KEY",
            }
            for key in _RELATION_ACTIONS:
                if node.get_attr(key):
                    attributes[key] = node.get_attr(key)
            if node.get_attr("deferred"):
                attributes["deferrable"] = True
                attributes["initially_deferred"] = True
            relation = new_relation_item(
                schema_name, table_name, columns, attributes=attributes,
            )
            item["relations"][relation["entity_name"]] = relation
            indexed.append(columns)
        return indexed

    def _resolve_target(self, node) -> tuple[str, str, list[str]]:  # wf:phase-4:new
        """``relation.to`` as ``(schema, table, columns)``.

        A two-part target means the target's pkey columns; a three-part
        one names a single column. The domain validator has already
        proved both resolve.
        """
        parts = [part.strip() for part in str(node.get_attr("to")).split(".")]
        if len(parts) == 3:
            return parts[0], parts[1], [parts[2]]
        target = self._tables[(parts[0], parts[1])]
        return parts[0], parts[1], _names(target["node"].get_attr("pkey"))

    def _fill_constraints(self, schema_name, table_name, table,
                          item) -> None:  # wf:phase-4:new
        for node in table["constraints"]:
            if node.get_attr("constraint_type") == "CHECK":
                constraint = new_constraint_item(
                    schema_name, table_name, None, "CHECK",
                    constraint_name=node.get_attr("name"),
                    check_clause=node.get_attr("check_clause"),
                )
            else:
                constraint = new_constraint_item(
                    schema_name, table_name, _names(node.get_attr("columns")),
                    "UNIQUE", constraint_name=node.get_attr("name"),
                )
            item["constraints"][constraint["entity_name"]] = constraint
        for node in table["composites"].values():
            if not node.get_attr("unique"):
                continue
            constraint = new_constraint_item(
                schema_name, table_name, _names(node.get_attr("columns")), "UNIQUE",
            )
            item["constraints"].setdefault(constraint["entity_name"], constraint)

    def _fill_indexes(self, schema_name, table_name, table,
                      item) -> None:  # wf:phase-4:new
        for node in table["indexes"]:
            columns = node.get_attr("columns")
            if not isinstance(columns, dict):
                columns = dict.fromkeys(_names(columns))
            attributes = {"columns": columns}
            for key in _INDEX_OPTIONS:
                if node.get_attr(key):
                    attributes[key] = node.get_attr(key)
            index = new_index_item(
                schema_name, table_name, list(columns),
                attributes=attributes, index_name=node.get_attr("name"),
            )
            item["indexes"][index["entity_name"]] = index

    def _fill_auto_indexes(self, schema_name, table_name, item, column_sets,
                           pkey_columns) -> None:  # wf:phase-4:new
        """Materialize the indexes ``indexed=True`` and foreign keys imply.

        An explicit ``index`` over the same columns wins — it carries a
        readable name and options the sugar cannot express — and an index
        over exactly the pkey columns is dropped: the primary key is
        already one.
        """
        for columns in column_sets:
            if columns == pkey_columns:
                continue
            index = new_index_item(
                schema_name, table_name, columns,
                attributes={"columns": dict.fromkeys(columns)},
            )
            item["indexes"].setdefault(index["entity_name"], index)


__all__ = ["SqlMigrationRenderer"]
