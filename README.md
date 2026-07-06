# Genro SQL

SQL model builder for the Genro framework — describe databases,
schemas, tables and columns in Python through a
[genro-builders](https://github.com/genropy/genro-builders) dialect,
and project the model tree into DDL, migrations and (later) query
compilation.

**Status**: Alpha — full rewrite in progress. The model source tree is
the single pivot: DDL rendering (partial or total), the migration
projection (genro-sqlmigration) and the round-trip (reader from a live
database, emitter to idiomatic Python) are all projections from/to the
same tree. The previous experimental ORM (GenroMicroDb) has been
removed; it remains available in git history.

## Design documentation

The rewrite is driven by the documents in [`roadmap/`](roadmap/):

- [`00_INDEX.md`](roadmap/00_INDEX.md) — documentation set index
- `01`–`04` — exhaustive inventories of the legacy engine (model
  grammar, query compiler, migration/adapters, test suite)
- [`05_grammar_design.md`](roadmap/05_grammar_design.md) — the grammar
  design document: vision, agreed decisions, open questions,
  implementation plan in slices

## Layout

```
src/genro_sql/
├── sql_builder.py    # SqlBuilder (dialect) + renderer_sql property
├── sql_elements.py   # grammar elements (under design)
├── sql_renderer.py   # DDL renderer (placeholder)
└── examples/         # numbered examples (three-view format)
```

## Development

```bash
pip install -e .[dev]
pytest tests/
ruff check src/
```

## License

Apache License 2.0 — Copyright 2025 Softwell S.r.l.
