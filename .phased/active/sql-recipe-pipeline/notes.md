# Notes — sql-recipe-pipeline

## Planning session (2026-08-20)

- Subbuilder spike (D1): scoped dialects db->schema->table->column on
  genro-builders 0.23.1. Containment and rendering cross the switch, but
  collection_key does not key children created inside the mounted sub-dialect
  (nodes come out `table_0`, `column_0`), so name addressing breaks. Flat mixin
  composition chosen. Spike source lived in the session scratchpad; the finding
  is what matters.
- Local PG verified: PostgreSQL 16 (Homebrew) on 127.0.0.1:5432, user
  `postgres`, no password. genro-sqlmigration's own conftest defaults match.
- genro-sqlmigration installed editable in the bench venv at commit 3819774
  with extras [postgresql,validation,dev,mysql,mssql]; its suite: 204 passed,
  88 deselected (postgresql marker) at install time.
- The `app` extra of genro-sqlmigration was deliberately NOT installed: it pins
  genro-asgi/genro-tytx from PyPI over the bench editables.
