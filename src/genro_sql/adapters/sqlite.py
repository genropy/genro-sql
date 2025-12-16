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

"""SQLite database adapter."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """Adapter for SQLite databases."""

    @property
    def type_map(self) -> dict[type, str]:
        """Map Python types to SQLite types."""
        return {
            str: 'TEXT',
            int: 'INTEGER',
            float: 'REAL',
            bool: 'INTEGER',
            bytes: 'BLOB',
            Decimal: 'NUMERIC',
            date: 'DATE',
            datetime: 'TIMESTAMP',
            time: 'TIME',
        }

    def get_current_schema(self, cursor: Any, table_name: str) -> dict:
        """
        Get current table schema from SQLite.

        Uses PRAGMA table_info() to retrieve column information.
        """
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row['name']: dict(row) for row in cursor.fetchall()}

    def supports_drop_column(self) -> bool:
        """
        SQLite supports DROP COLUMN since version 3.35.0 (2021-03-12).

        For older versions, table rebuild is required.
        """
        # For now return False to use safe rebuild method
        # Can be enhanced to check SQLite version
        return False

    def get_autoincrement_syntax(self) -> str:
        """Get AUTOINCREMENT syntax for SQLite."""
        return 'AUTOINCREMENT'

    def _table_exists(self, cursor: Any, table_name: str) -> bool:
        """Check if table exists in SQLite database."""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def _drop_columns(self, cursor: Any, table: Any, columns: set[str]) -> list[str]:
        """
        Drop columns from SQLite table.

        SQLite doesn't support DROP COLUMN directly (pre-3.35),
        so we rebuild the table without those columns.
        """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from ..table import Table
            table: Table

        migrations = []

        # Get columns to keep
        current_schema = self.get_current_schema(cursor, table.sql_name)
        columns_to_keep = [col for col in current_schema.keys() if col not in columns]

        # Create temporary table with new schema
        temp_table = f"{table.sql_name}_temp"

        # Build temp table with only columns we want to keep
        temp_columns = {k: v for k, v in table.columns.items() if k in columns_to_keep}

        # Save original columns, temporarily replace with filtered
        original_columns = table.columns
        table.columns = temp_columns

        try:
            create_sql = self._generate_create_table_sql(table).replace(
                f"CREATE TABLE IF NOT EXISTS {table.sql_name}",
                f"CREATE TABLE {temp_table}"
            )
            cursor.execute(create_sql)
            migrations.append(create_sql)

            # Copy data
            columns_str = ', '.join(columns_to_keep)
            copy_sql = f"INSERT INTO {temp_table} ({columns_str}) SELECT {columns_str} FROM {table.sql_name}"
            cursor.execute(copy_sql)
            migrations.append(copy_sql)

            # Drop old table and rename
            drop_sql = f"DROP TABLE {table.sql_name}"
            cursor.execute(drop_sql)
            migrations.append(drop_sql)

            rename_sql = f"ALTER TABLE {temp_table} RENAME TO {table.sql_name}"
            cursor.execute(rename_sql)
            migrations.append(rename_sql)
        finally:
            # Restore original columns
            table.columns = original_columns

        return migrations
