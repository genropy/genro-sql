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

"""Base class for automatic CRUD operations with introspection."""

import sqlite3
from contextlib import contextmanager
from dataclasses import fields, is_dataclass, MISSING
from typing import Any, Annotated, get_type_hints, get_origin, get_args, TYPE_CHECKING

from genro_core.enablers import apiready
from .column import Column
from .trigger_stack import in_triggerstack

if TYPE_CHECKING:
    from .database import GenroMicroDb


class Table:
    """
    Base class for tables with automatic CRUD operations.

    Usage:
        class BookTable(Table):
            sql_name = "books"

            @dataclass
            class Columns:
                id: int
                title: str
                author: str
                pages: int

    The table automatically provides:
    - insert(**kwargs) -> dict
    - delete(pk) -> None
    - get(pk) -> dict
    - list() -> list[dict]

    Metadata is automatically extracted from:
    - Class name (BookTable -> book/books)
    - Columns dataclass fields and types
    """

    sql_name: str = None  # SQL table name in database
    pkey: str = "id"  # Primary key field name
    Columns: type = None

    # Metadata (can be overridden in add_table)
    name: str = None           # Singular name for registry
    name_long: str = None      # Long descriptive name
    name_plural: str = None    # Plural name for API paths
    _icon: str = ""
    _description: str = ""

    def __init__(self, db: "GenroMicroDb"):
        """
        Initialize table.

        Args:
            db: GenroMicroDb instance
        """
        self.db = db
        self.columns: dict[str, Column] = {}  # Source of truth for column definitions
        self._validate_configuration()
        self._extract_metadata()
        self._extract_columns_from_dataclass()
        self._apply_api_decorators()

    def _validate_configuration(self) -> None:
        """Validate that required class attributes are set."""
        if self.sql_name is None:
            raise ValueError(f"{self.__class__.__name__}: sql_name must be defined")

        if self.Columns is None:
            raise ValueError(f"{self.__class__.__name__}: Columns dataclass must be defined")

        if not is_dataclass(self.Columns):
            raise ValueError(f"{self.__class__.__name__}: Columns must be a dataclass")

    def _extract_metadata(self) -> None:
        """Extract metadata from class name and Columns dataclass."""
        # Extract field information
        self._fields = {}
        self._field_types = {}

        for field in fields(self.Columns):
            self._fields[field.name] = field
            self._field_types[field.name] = field.type

        # Auto-generate singular/plural from class name if not set
        if self.name is None:
            # BookTable -> book, BookManager -> book
            class_name = self.__class__.__name__
            if class_name.endswith("Manager"):
                base_name = class_name[:-7]  # Remove "Manager"
            elif class_name.endswith("Table"):
                base_name = class_name[:-5]  # Remove "Table"
            else:
                base_name = class_name
            self.name = base_name.lower()

        if self.name_plural is None:
            # Simple pluralization (can be overridden)
            if self.name.endswith('y'):
                self.name_plural = self.name[:-1] + 'ies'
            elif self.name.endswith('s'):
                self.name_plural = self.name + 'es'
            else:
                self.name_plural = self.name + 's'

    def _python_type_to_dtype(self, py_type: type) -> str:
        """
        Convert Python type to Genropy dtype.

        Args:
            py_type: Python type (str, int, float, etc.)

        Returns:
            Genropy type code ('T', 'L', 'N', 'D', etc.)
        """
        from decimal import Decimal
        from datetime import date, datetime, time

        # Handle Optional types
        origin = get_origin(py_type)
        if origin is not None:
            args = get_args(py_type)
            if len(args) > 0:
                py_type = args[0]  # Get the actual type from Optional[T]

        # Map Python types to Genropy dtypes
        type_map = {
            str: 'T',      # TEXT/VARCHAR
            int: 'L',      # Long/INTEGER
            float: 'R',    # Real/FLOAT
            Decimal: 'N',  # Numeric/DECIMAL
            date: 'D',     # Date
            datetime: 'DH', # DateTime with hour
            time: 'H',     # Hour/Time
            bool: 'B',     # Boolean
            bytes: 'BLOB', # Binary data
        }

        return type_map.get(py_type, 'T')  # Default to TEXT

    def _extract_columns_from_dataclass(self) -> None:
        """Extract column definitions from Columns dataclass into self.columns."""
        if self.Columns is None:
            return

        for field in fields(self.Columns):
            # Convert Python type to Genropy dtype
            dtype = self._python_type_to_dtype(field.type)

            # Determine if column is required (NOT NULL)
            not_null = field.default is MISSING and field.default_factory is MISSING

            # Get default value if present
            default = field.default if field.default is not MISSING else None

            # Create Column object
            self.columns[field.name] = Column(
                name=field.name,
                dtype=dtype,
                not_null=not_null,
                default=default
            )

    def add_column(
        self,
        name: str,
        dtype: str = None,
        sql_name: str = None,
        name_long: str = None,
        name_plural: str = None,
        size: Any = None,
        not_null: bool = False,
        default: Any = None,
        **metadata
    ) -> None:
        """
        Add a column definition dynamically.

        Args:
            name: Logical column name
            dtype: Genropy type code ('T', 'L', 'D', 'N', etc.). If not provided,
                   will try to infer from 'type' in metadata (for backward compatibility)
            sql_name: SQL column name in database (defaults to name if not set)
            name_long: Long descriptive name
            name_plural: Plural name
            size: Size specification (for CHAR/VARCHAR/NUMERIC)
            not_null: If True, column cannot be NULL
            default: Default value
            **metadata: Additional column metadata
        """
        # Backward compatibility: if dtype not provided but 'type' in metadata, convert it
        if dtype is None and 'type' in metadata:
            py_type = metadata.pop('type')
            dtype = self._python_type_to_dtype(py_type)

        if dtype is None:
            raise ValueError("dtype is required. Use 'T' for text, 'L' for integer, 'N' for numeric, etc.")

        # Create Column object
        self.columns[name] = Column(
            name=name,
            dtype=dtype,
            sql_name=sql_name,
            name_long=name_long,
            name_plural=name_plural,
            size=size,
            not_null=not_null,
            default=default,
            **metadata
        )

    def _apply_api_decorators(self) -> None:
        """
        Apply @apiready decorators to CRUD methods.

        This is called automatically on initialization to set up
        the API metadata based on extracted information.
        """
        # Get the path from table_name or plural
        api_path = f"/{self.name_plural}"

        # Apply @apiready to the class with additem/delitem
        # Note: This needs to be done at class definition time
        # For now, we'll set metadata attributes that Publisher can read
        if not hasattr(self.__class__, '_api_base_path'):
            self.__class__._api_base_path = api_path

        if not hasattr(self.__class__, '_api_additem'):
            self.__class__._api_additem = 'add'

        if not hasattr(self.__class__, '_api_delitem'):
            self.__class__._api_delitem = 'delete'

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to dictionary."""
        return dict(row)

    @contextmanager
    def cursor(self):
        """
        Context manager for database cursor.

        Proxies to self.db.cursor() for convenient access.

        Usage:
            with self.cursor() as cursor:
                cursor.execute("SELECT * FROM table")
        """
        with self.db.cursor() as cursor:
            yield cursor

    def _type_to_sql(self, py_type) -> str:
        """Map Python type to SQL type."""
        # Handle Optional types
        origin = get_origin(py_type)
        if origin is not None:
            args = get_args(py_type)
            if len(args) > 0:
                py_type = args[0]  # Get the actual type from Optional[T]

        type_mapping = {
            int: "INTEGER",
            str: "TEXT",
            float: "REAL",
            bool: "INTEGER",
            bytes: "BLOB",
        }
        return type_mapping.get(py_type, "TEXT")

    def _generate_create_table_sql(self) -> str:
        """Generate CREATE TABLE SQL from Columns dataclass."""
        columns = []

        for field in fields(self.Columns):
            sql_type = self._type_to_sql(field.type)
            parts = [field.name, sql_type]

            # Primary key
            if field.name == self.pkey:
                parts.append("PRIMARY KEY")
                if sql_type == "INTEGER":
                    parts.append("AUTOINCREMENT")

            # NOT NULL constraint
            if field.default is MISSING and field.default_factory is MISSING:
                if field.name != self.pkey or sql_type != "INTEGER":
                    parts.append("NOT NULL")

            columns.append(" ".join(parts))

        return f"CREATE TABLE IF NOT EXISTS {self.sql_name} ({', '.join(columns)})"

    def _get_current_schema(self) -> dict:
        """Get current table schema from SQLite."""
        with self.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({self.sql_name})")
            return {row['name']: dict(row) for row in cursor.fetchall()}

    def _get_desired_schema(self) -> dict:
        """Get desired schema from Columns dataclass."""
        schema = {}
        for field in fields(self.Columns):
            schema[field.name] = {
                'sql_type': self._type_to_sql(field.type),
                'not_null': field.default is MISSING and field.default_factory is MISSING,
                'is_pk': field.name == self.pkey
            }
        return schema

    def _rebuild_table_without_columns(self, columns_to_drop: set) -> None:
        """
        Rebuild table without specified columns.

        This is the SQLite workaround for DROP COLUMN (pre-3.35.0).
        """
        with self.cursor() as cursor:
            # Get columns to keep
            current_schema = self._get_current_schema()
            columns_to_keep = [col for col in current_schema.keys() if col not in columns_to_drop]

            # Create temporary table with new schema
            temp_table = f"{self.sql_name}_temp"
            create_sql = self._generate_create_table_sql().replace(self.sql_name, temp_table)
            cursor.execute(create_sql)

            # Copy data
            columns_str = ', '.join(columns_to_keep)
            cursor.execute(
                f"INSERT INTO {temp_table} ({columns_str}) SELECT {columns_str} FROM {self.sql_name}"
            )

            # Drop old table and rename
            cursor.execute(f"DROP TABLE {self.sql_name}")
            cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {self.sql_name}")

        self.db.connection.commit()

    def migrate(self, drop_columns: bool = False) -> list[str]:
        """
        Create table if not exists, or migrate to match columns schema.

        Delegates to database adapter for database-specific migration logic.

        Args:
            drop_columns: If True, remove columns not in schema (DESTRUCTIVE!)

        Returns:
            List of SQL statements executed
        """
        return self.db.adapter.migrate(self, drop_columns=drop_columns)

    def _validate_fields(self, data: dict) -> None:
        """
        Validate fields against Columns definition.

        Args:
            data: Dictionary of field values

        Raises:
            ValueError: If required fields are missing or invalid
        """
        for field in fields(self.Columns):
            if field.name == self.pkey:
                continue  # Skip primary key

            # Check required fields
            if field.default is MISSING and field.default_factory is MISSING:
                if field.name not in data:
                    raise ValueError(f"Required field '{field.name}' is missing")

    def trigger_onInserting(self, record=None):
        """Called before inserting a record. Override in subclass to customize."""
        pass

    def trigger_onInserted(self, record=None):
        """Called after inserting a record. Override in subclass to customize."""
        pass

    def pkeyValue(self, record=None):
        """
        Generate a unique primary key value.

        Simplified implementation for micro_db:
        - For numeric types (int, float): returns None (use database auto-increment)
        - For text types: returns UUID
        - Override in subclass for custom logic (composite keys, etc.)

        Args:
            record: The record dictionary (optional)

        Returns:
            Primary key value or None to use database auto-increment
        """
        from genro_core.utils import getUuid

        # Get primary key column
        pk_column = self.columns.get(self.pkey)
        if not pk_column:
            return None

        # For numeric types, use database auto-increment
        if pk_column.python_type in (int, float):
            return None

        # For text types, generate UUID
        if pk_column.python_type == str:
            return getUuid()

        # Default: no custom value
        return None

    def newPkeyValue(self, record=None):
        """
        Get a new unique id to use as primary key on the current database table.

        Args:
            record: The record dictionary (optional)

        Returns:
            Primary key value from pkeyValue()
        """
        return self.pkeyValue(record=record)

    def checkPkey(self, record):
        """
        Check and generate primary key if needed.

        Args:
            record: The record dictionary to check

        Returns:
            bool: True if a new key was generated, False if key already exists

        This method checks if the record has a primary key value.
        If the pk is None or empty string, it calls newPkeyValue() to generate one.
        """
        pkey_value = record.get(self.pkey)
        newkey = False
        if pkey_value in (None, ''):
            newkey = True
            pkey_value = self.newPkeyValue(record=record)
            if pkey_value is not None:
                record[self.pkey] = pkey_value
        return newkey

    def validate(self, record):
        """
        Custom validation hook.

        Override in subclass to add:
        - Business rules
        - Complex validations
        - Cross-field validation

        Args:
            record: The record dictionary to validate

        Raises:
            ValueError: If validation fails
        """
        pass

    def _validate(self, record):
        """
        Internal validation using Pydantic + custom validate().

        This method:
        1. Validates types and required fields using Pydantic
        2. Calls validate() for custom business logic

        Args:
            record: The record dictionary to validate

        Raises:
            ValueError: If validation fails
        """
        from pydantic import create_model, ValidationError
        from typing import Optional

        # Build Pydantic model from Columns dataclass
        field_definitions = {}
        for field in fields(self.Columns):
            # Skip primary key for insert validation (can be auto-generated)
            if field.name == self.pkey:
                continue

            field_type = field.type
            # Make field optional if it has a default
            if field.default is not MISSING or field.default_factory is not MISSING:
                field_type = Optional[field_type]
                default = field.default if field.default is not MISSING else None
                field_definitions[field.name] = (field_type, default)
            else:
                # Required field
                field_definitions[field.name] = (field_type, ...)

        # Create dynamic Pydantic model
        ValidatorModel = create_model('RecordValidator', **field_definitions)

        # Validate using Pydantic
        try:
            # Filter record to only include fields in the model
            record_to_validate = {k: v for k, v in record.items() if k in field_definitions}
            ValidatorModel(**record_to_validate)
        except ValidationError as e:
            raise ValueError(f"Validation error: {e}")

        # Call custom validation
        self.validate(record)

    def trigger_onUpdating(self, record=None, oldRecord=None):
        """Called before updating a record. Override in subclass to customize."""
        pass

    def trigger_onUpdated(self, record=None, oldRecord=None):
        """Called after updating a record. Override in subclass to customize."""
        pass

    def trigger_onDeleting(self, record=None):
        """Called before deleting a record. Override in subclass to customize."""
        pass

    def trigger_onDeleted(self, record=None):
        """Called after deleting a record. Override in subclass to customize."""
        pass

    @in_triggerstack
    @apiready
    def insert(self, record=None) -> dict:
        """
        Insert a new record into the table.

        This method:
        1. Checks/generates primary key
        2. Validates record (Pydantic + custom)
        3. Calls trigger_onInserting
        4. Executes INSERT via adapter
        5. Calls trigger_onInserted

        Args:
            record: Dictionary of field values

        Returns:
            Primary key value of inserted record
        """
        self.checkPkey(record)
        self._validate(record)
        self.trigger_onInserting(record)
        result = self.db.adapter.insert(self, record)
        self.trigger_onInserted(record)
        return result

    @in_triggerstack
    @apiready
    def update(self, record=None, oldRecord=None) -> dict:
        """Update a record."""
        self.trigger_onUpdating(record, oldRecord)
        result = self.db.adapter.update(self, record, oldRecord)
        self.trigger_onUpdated(record, oldRecord)
        return result

    @in_triggerstack
    @apiready
    def delete(self, record=None) -> None:
        """Delete a record from the table."""
        self.trigger_onDeleting(record)
        self.db.adapter.delete(self, record)
        self.trigger_onDeleted(record)

    @apiready
    def get(self, pk: Any) -> dict:
        """
        Get a record by primary key.

        Args:
            pk: Primary key value

        Returns:
            Dictionary representation of the record

        Raises:
            KeyError: If record not found
        """
        with self.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {self.sql_name} WHERE {self.pkey} = ?",
                (pk,)
            )
            row = cursor.fetchone()

            if not row:
                raise KeyError(f"{self.name} with {self.pkey}={pk} not found")

            return self._row_to_dict(row)

    @apiready
    def list(self, **filters) -> list[dict]:
        """
        List all records, optionally filtered.

        Args:
            **filters: Optional field=value filters

        Returns:
            List of dictionary representations
        """
        with self.cursor() as cursor:
            if filters:
                # Build WHERE clause
                where_parts = []
                values = []
                for field, value in filters.items():
                    if field not in self._fields:
                        raise ValueError(f"Unknown field: {field}")
                    where_parts.append(f"{field} = ?")
                    values.append(value)

                where_clause = " WHERE " + " AND ".join(where_parts)
                cursor.execute(f"SELECT * FROM {self.sql_name}{where_clause}", tuple(values))
            else:
                cursor.execute(f"SELECT * FROM {self.sql_name}")

            return [self._row_to_dict(row) for row in cursor.fetchall()]

    @property
    def metadata(self) -> dict:
        """
        Get metadata dictionary for this manager.

        Returns:
            Dictionary with singular, plural, icon, description, fields
        """
        return {
            "singular": self.name,
            "plural": self.name_plural,
            "icon": self._icon,
            "description": self._description,
            "fields": {
                name: {
                    "type": str(field.type),
                    "required": field.default is MISSING and field.default_factory is MISSING
                }
                for name, field in self._fields.items()
            }
        }
