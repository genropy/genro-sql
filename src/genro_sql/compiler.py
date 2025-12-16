# Copyright (c) 2025 Softwell Srl, Milano, Italy
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Genropy-style SQL query compiler."""

import re
from typing import Any


class GenroMicroCompiler:
    """
    Compiler for Genropy-style query syntax.

    Syntax:
    - $field_name: References a table field (e.g., $title → title)
    - :param_name: References a parameter (e.g., :code → ? placeholder)

    Example:
        compiler = GenroMicroCompiler('books')
        sql, params = compiler.compile_select(
            columns='$title,$author',
            where='$genre = :g AND $pages > :min_pages',
            order_by='$title DESC',
            g='fiction',
            min_pages=200
        )
    """

    def __init__(self, table_name: str):
        """Initialize compiler for a specific table."""
        self.table_name = table_name
        self.templates = {
            'order_by': 'ORDER BY {}',
            'group_by': 'GROUP BY {}',
            'limit': 'LIMIT {}',
            'offset': 'OFFSET {}'
        }

    def _extract_fields(self, text: str) -> str:
        """Replace $field_name with field_name."""
        if not text:
            return text
        return re.sub(r'\$(\w+)', r'\1', text)

    def compile_columns(self, columns: str | None) -> str:
        """Compile SELECT columns clause."""
        if columns is None or columns == '*':
            return 'SELECT *'

        col_list = [self._extract_fields(col.strip()) for col in columns.split(',')]
        return f"SELECT {', '.join(col_list)}"

    def compile_where(self, where: str, sql_params: dict) -> str:
        """Compile WHERE clause."""
        if not where:
            return ''

        # Extract fields: $field → field
        # Leave :param references as-is for named parameters
        where_sql = self._extract_fields(where)

        return f'WHERE {where_sql}'

    def compile_select(self, **kwargs) -> tuple[str, dict]:
        """
        Compile a SELECT query from Genropy-style syntax.

        Args:
            columns: Column list (e.g., '$title,$author' or '*')
            where: WHERE clause with $fields and :params
            order_by: ORDER BY clause with $fields
            group_by: GROUP BY clause with $fields
            limit: LIMIT value
            offset: OFFSET value
            **kwargs: SQL parameters for :param_name references

        Returns:
            Tuple of (sql_string, params_dict)

        Example:
            sql, params = compiler.compile_select(
                columns='$id, COALESCE($title, :notitle) as Title',
                where='$shelf_code = :sc AND $available = :avail',
                order_by='$title ASC',
                sc='A1',
                avail=True,
                notitle='Untitled Book'
            )
            # Returns:
            # sql = "SELECT id, COALESCE(title, :notitle) as Title FROM books WHERE shelf_code = :sc AND available = :avail ORDER BY title ASC"
            # params = {'sc': 'A1', 'avail': True, 'notitle': 'Untitled Book'}
        """
        clauses = []
        sql_params = {}

        # Separate SQL clauses from parameters
        clause_data = {}
        for name, value in kwargs.items():
            if name in self.templates or hasattr(self, f'compile_{name}'):
                clause_data[name] = value
            else:
                sql_params[name] = value

        # Build SELECT clause (always first)
        columns = clause_data.get('columns')
        clauses.append(self.compile_columns(columns))

        # Build FROM clause (always second)
        clauses.append(f'FROM {self.table_name}')

        # Build other clauses in SQL order
        clause_order = ['where', 'group_by', 'order_by', 'limit', 'offset']

        for name in clause_order:
            value = clause_data.get(name)
            if value is None:
                continue

            # Check if it's a template
            if name in self.templates:
                processed_value = self._extract_fields(str(value))
                clause = self.templates[name].format(processed_value)
                clauses.append(clause)
            else:
                # Use handler method
                handler = getattr(self, f'compile_{name}', None)
                if handler:
                    clause = handler(value, sql_params)
                    if clause:
                        clauses.append(clause)

        # Combine SQL
        sql = ' '.join(clauses)

        return sql, sql_params

    def compile_insert(self, table: Any, record: dict) -> tuple[str, tuple]:
        """
        Compile an INSERT statement.

        Args:
            table: Table instance
            record: Dictionary of field values

        Returns:
            Tuple of (sql_string, values_tuple)

        Example:
            sql, values = compiler.compile_insert(table, {'title': 'Book', 'author': 'Author'})
            # Returns: ("INSERT INTO books (title, author) VALUES (?, ?)", ('Book', 'Author'))
        """
        field_names = list(record.keys())
        placeholders = ','.join(['?'] * len(field_names))
        fields_str = ','.join(field_names)

        sql = f"INSERT INTO {self.table_name} ({fields_str}) VALUES ({placeholders})"
        values = tuple(record.values())

        return sql, values

    def compile_update(self, table: Any, record: dict, pk_field: str, pk_value: Any) -> tuple[str, tuple]:
        """
        Compile an UPDATE statement.

        Args:
            table: Table instance
            record: Dictionary of field values (including pk)
            pk_field: Primary key field name
            pk_value: Primary key value

        Returns:
            Tuple of (sql_string, values_tuple)

        Example:
            sql, values = compiler.compile_update(table, {'id': 1, 'title': 'New Title'}, 'id', 1)
            # Returns: ("UPDATE books SET title = ? WHERE id = ?", ('New Title', 1))
        """
        # Build SET clause (exclude pk)
        set_parts = []
        values = []
        for field, value in record.items():
            if field != pk_field:
                set_parts.append(f"{field} = ?")
                values.append(value)

        if not set_parts:
            # Nothing to update
            return None, None

        set_clause = ", ".join(set_parts)
        values.append(pk_value)

        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {pk_field} = ?"

        return sql, tuple(values)

    def compile_delete(self, table: Any, pk_field: str, pk_value: Any) -> tuple[str, tuple]:
        """
        Compile a DELETE statement.

        Args:
            table: Table instance
            pk_field: Primary key field name
            pk_value: Primary key value

        Returns:
            Tuple of (sql_string, values_tuple)

        Example:
            sql, values = compiler.compile_delete(table, 'id', 1)
            # Returns: ("DELETE FROM books WHERE id = ?", (1,))
        """
        sql = f"DELETE FROM {self.table_name} WHERE {pk_field} = ?"
        values = (pk_value,)

        return sql, values
