# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the real-database integration tests.

The migrator labels the database side of the diff with
``db.get_dbname()`` and crashes on any ``root.entity_name`` mismatch;
upstream keeps the two sides equal by producing the ORM JSON with
``OrmJsonProducer(model, db.get_dbname())``. ``SqlMigrationRenderer``
emits the recipe's ``db(name=...)`` instead, so here the *database*
facade is what carries the recipe name:

- SQLite: ``get_dbname()`` doubles as the sqlite file path, so the
  fixture uses the bare recipe name as a relative path and pins the
  working directory to ``tmp_path`` — label and file stay identical
  while every artifact lands in the temp directory.
- PostgreSQL: a facade subclass reports the recipe name as the label
  while connections stay on the dedicated D10 test database
  (``test_genro_sql_*``), created empty here and dropped in teardown.
  Pre-creating it also keeps the migrator away from CREATE DATABASE,
  which targets the label name.

``sqlite_reader`` reads an integer pkey back as ``I`` even when it was
created from ``serial`` (documented v1 limitation). The resulting dtype
diff event is absorbed by capability gating — SQLite declares no
``alter_column_type``, so the builder records a warning and emits no
SQL — and idempotence stays judged on the assembled commands.

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
RECIPE_DB_NAME = "library"


@pytest.fixture
def sqlite_database(tmp_path, monkeypatch):
    """SqliteDatabase on a temp path, labeled with the recipe name."""
    monkeypatch.chdir(tmp_path)
    database = SqliteDatabase(
        {"dbname": RECIPE_DB_NAME},
        application_schemas=APPLICATION_SCHEMAS,
    )
    yield database
    database.closeConnection()


class RecipeNamedPgDatabase(PgDatabase):
    """Label the diff with the recipe name; connect to the test database."""

    def get_dbname(self):
        return RECIPE_DB_NAME


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
    """PgDatabase on a dedicated empty test database, dropped in teardown."""
    dbname = f"{DB_PREFIX}{request.function.__name__}"[:63]
    _drop_pg_database(pg_params, dbname)
    with psycopg.connect(dbname="postgres", autocommit=True, **pg_params) as conn:
        conn.execute(f'CREATE DATABASE "{dbname}"')
    database = RecipeNamedPgDatabase(
        dict(pg_params, dbname=dbname),
        application_schemas=APPLICATION_SCHEMAS,
    )
    yield database
    database.closeConnection()
    _drop_pg_database(pg_params, dbname)
