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

## Phase 2

- `db` carries `node_label="db"`. The source root has no element schema, so the
  singleton/collection label paths never run for a top-level child and the node
  would land as `db_0`; the whole plan addresses the tree as `db.<schema>.…`,
  so the label is declared on the element instead.
- `DTYPE` (23 codes), `FK_ACTION` (4) and `CONSTRAINT_TYPE` (2) are local
  `Literal` aliases in `elements.py` per D9 — no import of genro-sqlmigration
  from the grammar. `NO ACTION` is deliberately not in `FK_ACTION`: it is the
  SQL default and `structures.clean_attributes` strips it, so accepting it
  would create a value that never survives the projection. genro-sqlmigration
  exposes no FK-action constant, so Phase 4's parity test can only cover
  `DTYPE_CODES`.
- `index` keeps `name: str = None` as planned, but `table` declares
  `collection_key="name"`, which makes the key mandatory for EVERY table child:
  an anonymous `index()` raises. Phase 6 (which drops hashed index names) must
  synthesize a deterministic name rather than emit an anonymous index node.
- `aliasColumn`/`formulaColumn`/`subQueryColumn`/`pyColumn` are leaves
  (`sub_tags=""`): the plan gives `relation[0:1]` only to `column` and
  `compositeColumn`, which is also what `projects_relation` means. The
  pre-existing `test_virtual_column_accepts_relation` asserted the opposite and
  was rewritten as `test_virtual_column_rejects_relation`.
- Contract-test premises: see the `[!]` note on Phase 2 in plan.md. Four tests
  address the tree with `Bag.__getitem__` (value semantics) where they need
  `Bag.get_node`, and one expects `validate_source()` to report a
  max-cardinality violation that genro-builders raises at insertion instead.

## Phase 3

- Error paths are built from the `name` attributes, not from the node labels:
  the db node carries the fixed label `db` (it is not a name-keyed collection),
  so the readable path substitutes the database name in first position. The
  contract asserts `d.s.t`, and consumers of the message read model names, not
  grammar labels.
- Relation target resolution is memoized per relation path. Without it the
  back_reference check re-resolves and a single unresolvable `to` is reported
  twice, which breaks the "one violation, one line" contract of the message.
- The `x_` rule (D2) reads the declared parameter names from
  `SqlBuilder._class_schema`'s `declared_names` attribute rather than from
  `inspect.signature` on the element functions: the schema already carries the
  post-decoration set, and Phase 8's doc generator reads the same place.
- Ruff `per-file-ignores` for `tests/test_wf_phase*.py` (F841) instead of
  touching the read-only contract file. Rejected alternative: adding `# noqa`
  to the contract copy, which would make the in-tree copy diverge from the plan
  copy and defeat the byte-identical check.
