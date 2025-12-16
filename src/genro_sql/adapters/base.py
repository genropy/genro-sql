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

"""Base database adapter interface."""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..table import Table
    from ..compiler import GenroMicroCompiler


class DatabaseAdapter(ABC):
    """
    Base class for database adapters.

    Each adapter defines how Python types map to SQL types
    for a specific database engine, and handles database-specific
    migration logic.
    """

    @property
    @abstractmethod
    def type_map(self) -> dict[type, str]:
        """
        Map Python types to SQL types for this database.

        Returns:
            Dictionary mapping Python type to SQL type string

        Example:
            {
                str: 'TEXT',
                int: 'INTEGER',
                float: 'REAL',
                Decimal: 'NUMERIC',
                bool: 'INTEGER',
                bytes: 'BLOB',
                date: 'DATE',
                datetime: 'TIMESTAMP',
                time: 'TIME',
            }
        """
        pass

    def python_type_to_sql(self, py_type: type, size: Any = None) -> str:
        """
        Convert Python type to SQL type with optional size.

        Args:
            py_type: Python type class
            size: Optional size specification:
                - For str: int (CHAR(n)) or str '1:10' (VARCHAR with validation)
                - For Decimal: str '10,2' (NUMERIC(10,2))

        Returns:
            SQL type string with size if applicable

        Examples:
            python_type_to_sql(str, size=5) → 'CHAR(5)'
            python_type_to_sql(str, size='1:10') → 'VARCHAR(10)'
            python_type_to_sql(Decimal, size='10,2') → 'NUMERIC(10,2)'
        """
        base_type = self.type_map.get(py_type, 'TEXT')

        if size is None:
            return base_type

        return self._apply_size(py_type, base_type, size)

    def _apply_size(self, py_type: type, base_type: str, size: Any) -> str:
        """
        Apply size specification to SQL type.

        Args:
            py_type: Python type class
            base_type: Base SQL type string
            size: Size specification

        Returns:
            SQL type with size applied
        """
        from decimal import Decimal

        # String types
        if py_type == str:
            if isinstance(size, int):
                # Fixed length: CHAR(5)
                return f'CHAR({size})'
            elif isinstance(size, str) and ':' in size:
                # Variable length with range: '1:10' → VARCHAR(10)
                _, max_len = size.split(':')
                return f'VARCHAR({max_len})'
            else:
                # Just a number as string
                return f'CHAR({size})'

        # Decimal types
        elif py_type == Decimal:
            if isinstance(size, str) and ',' in size:
                # Precision and scale: '10,2' → NUMERIC(10,2)
                return f'NUMERIC({size})'
            else:
                return base_type

        # Other types don't use size
        return base_type

    @abstractmethod
    def get_current_schema(self, cursor: Any, table_name: str) -> dict:
        """
        Get current table schema from database.

        Args:
            cursor: Database cursor
            table_name: Name of table

        Returns:
            Dictionary mapping column name to column info
        """
        pass

    @abstractmethod
    def supports_drop_column(self) -> bool:
        """Check if database supports DROP COLUMN."""
        pass

    @abstractmethod
    def get_autoincrement_syntax(self) -> str:
        """Get AUTOINCREMENT syntax for this database."""
        pass

    def get_compiler(self, table: "Table") -> "GenroMicroCompiler":
        """
        Get a compiler instance for the table.

        Args:
            table: Table instance

        Returns:
            GenroMicroCompiler instance
        """
        from ..compiler import GenroMicroCompiler
        return GenroMicroCompiler(table.sql_name)

    def insert(self, table: "Table", data: dict) -> Any:
        """
        Insert a new record into the table.

        Args:
            table: Table instance
            data: Dictionary of field values

        Returns:
            Primary key value of the inserted record

        This method delegates SQL generation to the compiler,
        then executes and returns the primary key of the newly created record.
        """
        # Get compiler and generate SQL
        compiler = self.get_compiler(table)
        sql, values = compiler.compile_insert(table, data)

        with table.cursor() as cursor:
            cursor.execute(sql, values)

            # Get the inserted record's primary key
            # Use provided pk value if pk_field was in data, otherwise use lastrowid
            if table.pkey in data:
                pk_value = data[table.pkey]
            else:
                pk_value = cursor.lastrowid

        table.db.connection.commit()
        return pk_value

    def update(self, table: "Table", record: dict, oldRecord: dict = None) -> dict:
        """
        Update a record in the table.

        Args:
            table: Table instance
            record: New record data with primary key
            oldRecord: Optional old record data for comparison

        Returns:
            The updated record dictionary

        This method delegates SQL generation to the compiler,
        then executes the UPDATE statement.
        """
        # Get primary key value
        pk_field = table.pkey
        if pk_field not in record:
            raise ValueError(f"Primary key '{pk_field}' not found in record")

        pk_value = record[pk_field]

        # Get compiler and generate SQL
        compiler = self.get_compiler(table)
        sql, values = compiler.compile_update(table, record, pk_field, pk_value)

        if sql is None:
            return record  # Nothing to update

        with table.cursor() as cursor:
            cursor.execute(sql, values)

        table.db.connection.commit()
        return record

    def delete(self, table: "Table", record: dict) -> None:
        """
        Delete a record from the table.

        Args:
            table: Table instance
            record: Record data with primary key

        This method delegates SQL generation to the compiler,
        then executes the DELETE statement.
        """
        # Get primary key value
        pk_field = table.pkey
        if pk_field not in record:
            raise ValueError(f"Primary key '{pk_field}' not found in record")

        pk_value = record[pk_field]

        # Get compiler and generate SQL
        compiler = self.get_compiler(table)
        sql, values = compiler.compile_delete(table, pk_field, pk_value)

        with table.cursor() as cursor:
            cursor.execute(sql, values)

        table.db.connection.commit()

    def migrate(self, table: "Table", drop_columns: bool = False) -> list[str]:
        """
        Migrate table to match schema definition.

        Args:
            table: Table instance with column definitions
            drop_columns: If True, remove columns not in schema (DESTRUCTIVE!)

        Returns:
            List of SQL statements executed

        This method:
        1. Checks if table exists
        2. If not exists: CREATE TABLE
        3. If exists: compare and ALTER TABLE as needed
        """
        migrations = []

        with table.cursor() as cursor:
            # Check if table exists
            if not self._table_exists(cursor, table.sql_name):
                # CREATE TABLE
                sql = self._generate_create_table_sql(table)
                cursor.execute(sql)
                migrations.append(sql)
            else:
                # ALTER TABLE
                current_schema = self.get_current_schema(cursor, table.sql_name)
                desired_schema = self._get_desired_schema(table)

                # Add missing columns
                for col_name, col_info in desired_schema.items():
                    if col_name not in current_schema:
                        sql = self._generate_add_column_sql(table.sql_name, col_name, col_info)
                        cursor.execute(sql)
                        migrations.append(sql)

                # Remove extra columns (if requested)
                if drop_columns:
                    columns_to_drop = set(current_schema.keys()) - set(desired_schema.keys())
                    if columns_to_drop:
                        drop_migrations = self._drop_columns(cursor, table, columns_to_drop)
                        migrations.extend(drop_migrations)

        if migrations:
            table.db.connection.commit()

        return migrations

    @abstractmethod
    def _table_exists(self, cursor: Any, table_name: str) -> bool:
        """Check if table exists in database."""
        pass

    def _get_desired_schema(self, table: "Table") -> dict:
        """
        Get desired schema from table columns definition.

        Returns:
            Dictionary mapping column name to column info dict
        """
        schema = {}
        for col_name, column in table.columns.items():
            schema[col_name] = {
                'name': col_name,
                'sql_name': column.sql_name,
                'python_type': column.python_type,  # Uses lazy cached property
                'sql_type': column.sql_type,        # Uses lazy cached property with size
                'size': column.size,
                'not_null': column.not_null,
                'primary_key': col_name == table.pkey,
                'default': column.default,
            }
        return schema

    def _generate_create_table_sql(self, table: "Table") -> str:
        """
        Generate CREATE TABLE SQL statement.

        Args:
            table: Table instance

        Returns:
            SQL CREATE TABLE statement
        """
        columns = []

        for col_name, column in table.columns.items():
            # Use Column.sql_type which already has size applied
            sql_type = column.sql_type

            # Use sql_name if different from logical name
            col_sql_name = column.sql_name

            parts = [col_sql_name, sql_type]

            # Primary key
            if col_name == table.pkey:
                parts.append('PRIMARY KEY')
                if sql_type.startswith('INTEGER'):
                    parts.append(self.get_autoincrement_syntax())

            # NOT NULL constraint
            if column.not_null and col_name != table.pkey:
                parts.append('NOT NULL')

            # DEFAULT value
            if column.default is not None:
                default_val = column.default
                if isinstance(default_val, str):
                    parts.append(f"DEFAULT '{default_val}'")
                else:
                    parts.append(f"DEFAULT {default_val}")

            columns.append(' '.join(parts))

        return f"CREATE TABLE IF NOT EXISTS {table.sql_name} ({', '.join(columns)})"

    def _generate_add_column_sql(self, table_name: str, col_name: str, col_info: dict) -> str:
        """
        Generate ALTER TABLE ADD COLUMN SQL statement.

        Args:
            table_name: Name of table
            col_name: Column name
            col_info: Column information dict from _get_desired_schema()

        Returns:
            SQL ALTER TABLE ADD COLUMN statement
        """
        # col_info now has 'sql_type' already computed by Column.sql_type
        sql_type = col_info['sql_type']
        sql_name = col_info['sql_name']

        parts = [sql_name, sql_type]

        # Note: Can't add NOT NULL without default on existing tables
        # in most databases, so we skip it here
        if col_info.get('default') is not None:
            default_val = col_info['default']
            if isinstance(default_val, str):
                parts.append(f"DEFAULT '{default_val}'")
            else:
                parts.append(f"DEFAULT {default_val}")

        return f"ALTER TABLE {table_name} ADD COLUMN {' '.join(parts)}"

    @abstractmethod
    def _drop_columns(self, cursor: Any, table: "Table", columns: set[str]) -> list[str]:
        """
        Drop columns from table.

        Different databases handle this differently:
        - PostgreSQL: Direct DROP COLUMN
        - SQLite: Rebuild table (pre-3.35)

        Args:
            cursor: Database cursor
            table: Table instance
            columns: Set of column names to drop

        Returns:
            List of SQL statements executed
        """
        pass
