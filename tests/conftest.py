# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the real-database integration tests.

The recipes under test live in one application schema, ``library_public``.
Databases are handed to the migrator empty (or nonexistent): the migration
itself creates database, schemas and tables.

PostgreSQL connection parameters come from ``GNR_TEST_PG_HOST``,
``GNR_TEST_PG_PORT``, ``GNR_TEST_PG_USER`` and ``GNR_TEST_PG_PASSWORD``,
defaulting to the local trust-authenticated server on 127.0.0.1:5432.
"""
from __future__ import annotations

import os

import psycopg
import pytest

from genro_sqlmigration.adapters import PgDatabase, SqliteDatabase

APPLICATION_SCHEMAS = ["library_public"]
DB_PREFIX = "test_genro_sql_"


@pytest.fixture
def sqlite_database(tmp_path):
    """SqliteDatabase on a fresh temp path, one file per schema."""
    return SqliteDatabase(
        {"dbname": str(tmp_path / "library.db")},
        application_schemas=APPLICATION_SCHEMAS,
    )


@pytest.fixture(scope="session")
def pg_params():
    """psycopg connection kwargs for the test PostgreSQL server."""
    params = {
        "host": os.environ.get("GNR_TEST_PG_HOST", "127.0.0.1"),
        "port": os.environ.get("GNR_TEST_PG_PORT", "5432"),
        "user": os.environ.get("GNR_TEST_PG_USER", "postgres"),
    }
    password = os.environ.get("GNR_TEST_PG_PASSWORD")
    if password:
        params["password"] = password
    return params


def _drop_pg_database(pg_params, dbname):
    """Terminate leftover backends and drop the test database."""
    with psycopg.connect(dbname="postgres", autocommit=True, **pg_params) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            " WHERE datname = %s AND pid <> pg_backend_pid()",
            (dbname,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')


@pytest.fixture
def pg_database(request, pg_params):
    """PgDatabase on a dedicated test database, dropped in teardown."""
    dbname = f"{DB_PREFIX}{request.function.__name__}"[:63]
    _drop_pg_database(pg_params, dbname)
    database = PgDatabase(
        dict(pg_params, dbname=dbname),
        application_schemas=APPLICATION_SCHEMAS,
    )
    yield database
    database.closeConnection()
    _drop_pg_database(pg_params, dbname)
