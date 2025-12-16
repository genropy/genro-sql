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

"""GenroDb - Database management for Genro applications."""

import _thread
import sqlite3
from contextlib import contextmanager
from typing import Any, Type
from urllib.parse import urlparse

from .adapters import DatabaseAdapter, SQLiteAdapter, PostgreSQLAdapter


class TablesRegistry:
    """Registry for database tables with dict-like access using singular names."""

    def __init__(self):
        self._tables = {}

    def register(self, table_instance: Any) -> None:
        """
        Register a table instance.

        Args:
            table_instance: Instance of a Table class
        """
        name = table_instance.name
        self._tables[name] = table_instance

    def __getattr__(self, name: str) -> Any:
        """Access table by singular name as attribute."""
        if name.startswith('_'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        if name in self._tables:
            return self._tables[name]
        raise AttributeError(f"Table '{name}' not found. Available: {list(self._tables.keys())}")

    def __getitem__(self, name: str) -> Any:
        """Access table by singular name as dict key."""
        if name not in self._tables:
            raise KeyError(f"Table '{name}' not found. Available: {list(self._tables.keys())}")
        return self._tables[name]

    def __contains__(self, name: str) -> bool:
        """Check if table is registered."""
        return name in self._tables

    def keys(self):
        """Get all registered table names."""
        return self._tables.keys()

    def values(self):
        """Get all registered table instances."""
        return self._tables.values()

    def items(self):
        """Get all (name, table) pairs."""
        return self._tables.items()


class TempEnv:
    """
    Context manager for temporarily modifying database environment.

    Usage:
        with db.tempEnv(audit_user='admin', batch_mode=True):
            # Operations here can access these values via db.currentEnv
            db.tables.mytable.insert(record=data)
    """

    def __init__(self, db: "GenroMicroDb", **kwargs):
        """
        Initialize temporary environment.

        Args:
            db: Database instance
            **kwargs: Key-value pairs to temporarily set in currentEnv
        """
        self.db = db
        self.kwargs = kwargs
        self.savedValues = {}
        self.addedKeys = []

    def __enter__(self):
        """
        Enter context: save old values and set new ones.

        Returns:
            Database instance for chaining
        """
        currentEnv = self.db.currentEnv

        for k, v in self.kwargs.items():
            if k in currentEnv:
                # Save existing value
                self.savedValues[k] = currentEnv.get(k)
            else:
                # Track new key
                self.addedKeys.append((k, v))
            # Set new value
            currentEnv[k] = v

        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit context: restore old values.

        Args:
            exc_type: Exception type (if any)
            exc_value: Exception value (if any)
            traceback: Exception traceback (if any)
        """
        currentEnv = self.db.currentEnv

        # Remove keys we added (only if value unchanged)
        for k, v in self.addedKeys:
            if currentEnv.get(k) == v:
                currentEnv.pop(k, None)

        # Restore saved values
        currentEnv.update(self.savedValues)


class GenroDb:
    """
    Database abstraction for Genro applications.

    Manages database connections and table registry.
    Supports multiple database implementations (SQLite, PostgreSQL, etc.)
    """

    # Class-level thread-local environment storage
    _currentEnvByThread = {}

    def __init__(
        self,
        name: str,
        connection_string: str | None = None,
        implementation: str | None = None,
        path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        **kwargs
    ):
        """
        Initialize database connection.

        Args:
            name: Database name/identifier
            connection_string: Full connection string (e.g., "sqlite:///path/to/db.sqlite")
            implementation: Database type ("sqlite", "postgresql", etc.)
            path: Database file path (for SQLite)
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            **kwargs: Additional connection parameters
        """
        self.name = name
        self.tables = TablesRegistry()
        self._connection = None  # Lazy connection
        self._adapter = None  # Lazy adapter

        # Store connection parameters for lazy initialization
        self._connection_string = connection_string
        self._implementation = implementation
        self._path = path
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._kwargs = kwargs

        if not connection_string and not implementation:
            raise ValueError("Either connection_string or implementation must be provided")

    def _connect_from_string(self, connection_string: str) -> None:
        """Parse connection string and establish connection."""
        parsed = urlparse(connection_string)
        implementation = parsed.scheme

        if implementation == "sqlite":
            # sqlite:///path/to/db.sqlite or sqlite:///:memory:
            db_path = parsed.path.lstrip('/')
            if not db_path:
                db_path = ":memory:"
            self._connect_sqlite(db_path)
        else:
            raise NotImplementedError(f"Database implementation '{implementation}' not yet supported")

    def _connect_from_params(
        self,
        implementation: str,
        path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        **kwargs
    ) -> None:
        """Connect using individual parameters."""
        if implementation == "sqlite":
            db_path = path or ":memory:"
            self._connect_sqlite(db_path)
        elif implementation == "postgresql":
            raise NotImplementedError("PostgreSQL support coming soon")
        else:
            raise NotImplementedError(f"Database implementation '{implementation}' not yet supported")

    def _connect_sqlite(self, path: str) -> sqlite3.Connection:
        """Establish SQLite connection."""
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        """
        Lazy connection property.

        Creates and caches the database connection on first access.
        """
        if self._connection is None:
            # Create connection from stored parameters
            if self._connection_string:
                parsed = urlparse(self._connection_string)
                implementation = parsed.scheme

                if implementation == "sqlite":
                    db_path = parsed.path.lstrip('/')
                    if not db_path:
                        db_path = ":memory:"
                    self._connection = self._connect_sqlite(db_path)
                else:
                    raise NotImplementedError(f"Database implementation '{implementation}' not yet supported")

            elif self._implementation:
                if self._implementation == "sqlite":
                    db_path = self._path or ":memory:"
                    self._connection = self._connect_sqlite(db_path)
                elif self._implementation == "postgresql":
                    raise NotImplementedError("PostgreSQL support coming soon")
                else:
                    raise NotImplementedError(f"Database implementation '{self._implementation}' not yet supported")

        return self._connection

    @property
    def adapter(self) -> DatabaseAdapter:
        """
        Lazy adapter property.

        Creates and caches the database adapter on first access.
        """
        if self._adapter is None:
            # Determine implementation type
            implementation = None

            if self._connection_string:
                parsed = urlparse(self._connection_string)
                implementation = parsed.scheme
            elif self._implementation:
                implementation = self._implementation

            # Create appropriate adapter
            if implementation == "sqlite":
                self._adapter = SQLiteAdapter()
            elif implementation == "postgresql":
                self._adapter = PostgreSQLAdapter()
            else:
                raise NotImplementedError(f"Adapter for '{implementation}' not yet supported")

        return self._adapter

    @contextmanager
    def cursor(self):
        """
        Context manager for database cursor.

        Provides a cursor that is automatically closed after use.
        Does NOT handle commit/rollback - use @transaction decorator for that.

        Usage:
            with db.cursor() as cursor:
                cursor.execute("SELECT * FROM table")
        """
        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def add_table(self, table_class: Type) -> None:
        """
        Register a table class.

        Args:
            table_class: Table class (not instance)
        """
        # Instantiate the table with this database instance
        table_instance = table_class(self)
        self.tables.register(table_instance)

    def migrate(self, drop_columns: bool = False) -> dict[str, list[str]]:
        """
        Run migrations on all registered tables.

        Args:
            drop_columns: If True, remove columns not in schema (DESTRUCTIVE!)

        Returns:
            Dictionary mapping table names to list of SQL statements executed
        """
        results = {}
        for table_name, table_instance in self.tables.items():
            migrations = table_instance.migrate(drop_columns=drop_columns)
            if migrations:
                results[table_name] = migrations
        return results

    @property
    def currentEnv(self) -> dict:
        """
        Get thread-local environment dictionary.

        Each thread has its own isolated environment dictionary for storing
        contextual information during operations (e.g., audit_user, batch_mode).

        Returns:
            Dictionary for current thread
        """
        thread_id = _thread.get_ident()
        if thread_id not in self._currentEnvByThread:
            self._currentEnvByThread[thread_id] = {}
        return self._currentEnvByThread[thread_id]

    def tempEnv(self, **kwargs) -> TempEnv:
        """
        Create temporary environment context manager.

        Temporarily sets values in currentEnv for the duration of the context.

        Args:
            **kwargs: Key-value pairs to set temporarily

        Returns:
            TempEnv context manager

        Usage:
            with db.tempEnv(audit_user='admin', batch_mode=True):
                # Operations here can access these via db.currentEnv
                db.tables.mytable.insert(record=data)
        """
        return TempEnv(self, **kwargs)

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
