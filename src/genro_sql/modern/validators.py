# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Domain validation of a complete SQL model tree.

The grammar (:mod:`genro_sql.modern.elements`) enforces containment and
types at build time; it cannot know whether a name refers to something.
This module walks the finished tree and checks the referential rules —
pkey members, relation targets, composite members, constraint and index
columns, the ``x_`` rule of the semi-closed signatures (D2).

Every violation is accumulated and reported together, prefixed by the
node's readable path (``d.public.recipe.author_id``), so one run tells
the whole story instead of stopping at the first offence.
"""

from __future__ import annotations

_META_KEY = "_meta"


class SqlModelValidationError(ValueError):  # wf:phase-3:new
    """Every domain violation found in one model, one per line.

    Args:
        errors: the violation messages, already path-prefixed.
    """

    def __init__(self, errors: list[str]) -> None:  # wf:phase-3:new
        self.errors = list(errors)
        super().__init__(
            "invalid SQL model:\n" + "\n".join(f"  {e}" for e in self.errors),
        )


class SqlModelValidator:  # wf:phase-3:new
    """Referential validation of a built :class:`SqlBuilder` tree."""

    def validate(self, builder):  # wf:phase-3:new
        """Validate ``builder``'s source tree.

        Args:
            builder: a created :class:`~genro_sql.modern.builder.SqlBuilder`.

        Returns:
            The same builder, so the call chains.

        Raises:
            SqlModelValidationError: with every violation found.
        """
        self.errors: list[str] = []
        self._db_name = None
        self._tables: dict[tuple[str, str], dict] = {}
        self._relations: list[tuple[str, object]] = []
        self._resolved: dict[str, tuple] = {}
        self._collect(builder)
        self._check_attributes(builder)
        for table in self._tables.values():
            self._check_pkey(table)
            self._check_composites(table)
            self._check_constraints(table)
            self._check_indexes(table)
        for path, node in self._relations:
            self._check_relation(path, node)
        self._check_back_references()
        if self.errors:
            raise SqlModelValidationError(self.errors)
        return builder

    # -- collection ------------------------------------------------------

    def _collect(self, builder) -> None:  # wf:phase-3:new
        for path, node in builder.source.walk():
            parts = path.split(".")
            tag = node.node_tag
            if tag == "db":
                self._db_name = node.get_attr("name")
            elif tag == "table":
                self._tables[(parts[1], parts[2])] = {
                    "node": node, "path": path, "columns": {},
                    "composites": {}, "family": {}, "constraints": [],
                    "indexes": [],
                }
            elif tag == "relation":
                self._relations.append((path, node))
            elif len(parts) == 4:
                table = self._tables.get((parts[1], parts[2]))
                if table is None:
                    continue
                if tag == "constraint":
                    table["constraints"].append((path, node))
                elif tag == "index":
                    table["indexes"].append((path, node))
                else:
                    table["family"][parts[3]] = node
                    if node._get_meta("projects_column"):
                        table["columns"][parts[3]] = node
                    elif tag == "compositeColumn":
                        table["composites"][parts[3]] = node

    # -- helpers ---------------------------------------------------------

    def _readable(self, path: str) -> str:  # wf:phase-3:new
        """Path with the ``db`` root label replaced by the database name."""
        parts = path.split(".")
        if parts and self._db_name:
            parts[0] = self._db_name
        return ".".join(parts)

    def _error(self, path: str, message: str) -> None:  # wf:phase-3:new
        self.errors.append(f"{self._readable(path)}: {message}")

    @staticmethod
    def _names(value) -> list[str]:  # wf:phase-3:new
        """Column names out of a comma-joined string or an ordering dict."""
        if value is None:
            return []
        if isinstance(value, dict):
            return list(value)
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value]
        return [n.strip() for n in str(value).split(",") if n.strip()]

    def _pkey_names(self, table: dict) -> list[str]:  # wf:phase-3:new
        return self._names(table["node"].get_attr("pkey"))

    # -- checks ----------------------------------------------------------

    def _check_attributes(self, builder) -> None:  # wf:phase-3:new
        """D2: any attribute outside the signature must start with ``x_``."""
        schema = type(builder)._class_schema
        for path, node in builder.source.walk():
            element = schema.get_node(node.node_tag)
            if element is None:
                continue
            declared = element.get_attr("declared_names") or set()
            for key in node.attr:
                if key == _META_KEY or key in declared or key.startswith("x_"):
                    continue
                self._error(
                    path,
                    f"unknown attribute '{key}' on <{node.node_tag}>: extras "
                    f"must start with 'x_'; declared attributes are "
                    f"{', '.join(sorted(declared))}",
                )

    def _check_pkey(self, table: dict) -> None:  # wf:phase-3:new
        for name in self._pkey_names(table):
            if name not in table["columns"]:
                self._error(
                    table["path"],
                    f"pkey column '{name}' is not a physical column of the table",
                )

    def _check_composites(self, table: dict) -> None:  # wf:phase-3:new
        for name, node in table["composites"].items():
            members = self._names(node.get_attr("columns"))
            if not members:
                self._error(
                    f"{table['path']}.{name}",
                    "compositeColumn requires 'columns'",
                )
            for member in members:
                if member not in table["columns"]:
                    self._error(
                        f"{table['path']}.{name}",
                        f"composite member '{member}' is not a physical "
                        "column of the table",
                    )

    def _check_constraints(self, table: dict) -> None:  # wf:phase-3:new
        for path, node in table["constraints"]:
            kind = node.get_attr("constraint_type")
            name = node.get_attr("name")
            if kind == "CHECK" and not node.get_attr("check_clause"):
                self._error(
                    path, f"constraint '{name}': CHECK requires a check_clause",
                )
            if kind == "UNIQUE" and not node.get_attr("columns"):
                self._error(
                    path, f"constraint '{name}': UNIQUE requires columns",
                )
            for column in self._names(node.get_attr("columns")):
                if column not in table["columns"]:
                    self._error(
                        path,
                        f"constraint column '{column}' is not a physical "
                        "column of the table",
                    )

    def _check_indexes(self, table: dict) -> None:  # wf:phase-3:new
        for path, node in table["indexes"]:
            for column in self._names(node.get_attr("columns")):
                if column not in table["columns"]:
                    self._error(
                        path,
                        f"index column '{column}' is not a physical column "
                        "of the table",
                    )

    def _resolve_target(self, path: str, node):  # wf:phase-3:new
        """Target table and columns of ``relation.to``, errors reported.

        A three-part target names a physical column, or the
        compositeColumn packing the target key.

        Returns:
            ``(table_key, column_names)`` or ``None`` when unresolvable.
        """
        to = node.get_attr("to")
        if not to:
            self._error(path, "relation requires 'to'")
            return None
        parts = [p.strip() for p in str(to).split(".")]
        if len(parts) not in (2, 3):
            self._error(
                path,
                f"relation target '{to}' must be 'schema.table' or "
                "'schema.table.column'",
            )
            return None
        table_key = (parts[0], parts[1])
        target = self._tables.get(table_key)
        if target is None:
            self._error(path, f"relation target table '{to}' does not exist")
            return None
        if len(parts) == 3:
            composite = target["composites"].get(parts[2])
            columns = (self._names(composite.get_attr("columns"))
                       if composite is not None else [parts[2]])
        else:
            columns = self._pkey_names(target)
        if not columns:
            self._error(
                path,
                f"relation target '{to}' resolves to no column: the target "
                "table declares no pkey",
            )
            return None
        for column in columns:
            if column not in target["columns"]:
                self._error(
                    path,
                    f"relation target column '{to}': '{column}' is not a "
                    "physical column of the target table",
                )
                return None
        return table_key, columns

    def _check_relation(self, path: str, node) -> None:  # wf:phase-3:new
        parts = path.split(".")
        owner = self._tables.get((parts[1], parts[2]), {}).get(
            "family", {}).get(parts[3]) if len(parts) == 5 else None
        if owner is None or not owner._get_meta("projects_relation"):
            if node.get_attr("foreign_key"):
                self._error(
                    path,
                    "foreign_key is allowed only on a relation under a "
                    "column or a compositeColumn",
                )
            return
        resolved = self._resolve_target(path, node)
        if resolved is None:
            return
        self._resolved[path] = resolved
        _target_key, target_columns = resolved
        if owner.node_tag == "compositeColumn":
            local = self._names(owner.get_attr("columns"))
        else:
            local = [owner.get_attr("name")]
        if len(local) != len(target_columns):
            self._error(
                path,
                f"composite relation column counts differ: {len(local)} local "
                f"({', '.join(local)}) vs {len(target_columns)} target "
                f"({', '.join(target_columns)})",
            )

    def _check_back_references(self) -> None:  # wf:phase-3:new
        seen: dict[tuple, str] = {}
        for path, node in self._relations:
            back_reference = node.get_attr("back_reference")
            if not back_reference:
                continue
            resolved = self._resolved.get(path)
            if resolved is None:
                continue
            key = (resolved[0], back_reference)
            if key in seen:
                self._error(
                    path,
                    f"back_reference '{back_reference}' on "
                    f"'{'.'.join(resolved[0])}' is already used by "
                    f"{self._readable(seen[key])}",
                )
            else:
                seen[key] = path


__all__ = ["SqlModelValidationError", "SqlModelValidator"]
