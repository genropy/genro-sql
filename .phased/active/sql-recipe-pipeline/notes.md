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

## Phase 4

- **`deferred=True` maps to both contract keys.** The grammar has one flag,
  the normalized JSON has `deferrable` and `initially_deferred`. An
  INITIALLY DEFERRED constraint must be DEFERRABLE, so the renderer sets
  both; the reverse mapping (Phase 6) has to collapse them back into one.
- **The auto-index skip rule is exact equality with the pkey column list**,
  not "any subset of the pkey". A prefix of a composite pkey is genuinely
  worth its own index, and the plan's parity note only claims the PK
  already indexes the PK.
- **An explicit `index` wins over the `indexed=True` / FK sugar.** Both
  land on the same structural hash (it is computed from the columns), so
  the sugar is added with `setdefault` after the explicit ones: the
  readable name and the options survive.
- **`relation.to` resolution in the renderer mirrors the validator**: two
  parts means the target pkey, three parts a single column. D4's "target
  composite" case is unreachable from here — the validator rejects a `to`
  whose third part is not a physical column — so it is left to the reader
  (Phase 6), which is where composites get synthesized.
- **`sql_type` does not suppress the dtype default.** D5 says it wins at
  DDL time; at projection time the renderer stays byte-parity with
  `JsonStructureProducer`, which defaults `dtype` regardless. Diverging
  here would break the golden oracle, not fix anything.

## Phase 6

- **The round-trip law and D3 collide, and the grammar gained one knob so
  both survive.** `JsonStructureProducer` never invents an index for a
  foreign key; the renderer always does (D3, legacy parity, encoded in the
  Phase 4 golden). So `render(reader(A))` grew an index every FK fixture of
  the Phase 6 contract lacks, and no reader-only trick can suppress it —
  the sugar fires on the projection side. `relation` therefore declares
  `indexed: bool = True`: the default keeps D3 and the Phase 4 golden
  untouched, and `indexed=False` states that the columns are deliberately
  unindexed. The reader sets it exactly when the JSON carries no index over
  those columns, in that order.
- **The reader never re-derives sugar.** Every index in the JSON becomes a
  real `index` element and `column.indexed` is never set: the sugar is an
  authoring convenience of the forward path, and re-deriving it would make
  the reverse path guess.
- **Hashed index names travel verbatim, unlike the other hashes.** The plan
  wanted them dropped, but `index.name` is the table's collection key (an
  index cannot mount anonymously) AND the `index_name` the renderer echoes
  into the JSON — it is not re-derived. Dropping the hash would fail to
  mount and, worse, rename the index in the database. Relations stay
  anonymous and hash-named UNIQUE constraints still come back as
  `unique=True` on a composite, which is where the decision's intent lives.
- **D4's composite target is now reachable.** The renderer's and the
  validator's `_resolve_target` accept a three-part `to` whose last part
  names a compositeColumn, expanding it into its members; the reader
  synthesizes that target composite when `related_columns` is not the
  target pkey. Without those four lines the synthesis the plan mandates
  would emit a relation to a column that does not exist.
- **Composites are planned before the tree is built.** A target composite
  belongs to a table that may be mounted before the relation naming it is
  read, so `_plan_composites` walks the whole structure first and
  `_add_table` mounts what the plan asks for. Same pass merges the FK and
  UNIQUE needs of one column set into a single composite.

## Run inspection

- Run of 2026-08-20 (afternoon, relaunch after the host-restart reset): Phase 6
  completed uneventfully — contract tests 11/11, full suite 71 passed, ruff
  clean, commit 471c5a5.
- The run was then deliberately terminated by the user (credit budget) right
  after `EVENT: phase-done 6`, before Phase 7's session started spending.
  `log/phase-7.txt` was created empty by the launcher header and carries no
  session output. Phases 7-9 remain `[ ]`; resume is a fresh `/run-workflow`.
- Watch point for Phase 7: Phase 6 bent two plan decisions (recorded in its
  Done note and above) — `relation` gained `indexed: bool = True`, hashed
  index names now travel verbatim, and D4 composite targets expand a
  three-part `to`. The Phase 7 contract tests were authored before these
  bends; if one fails on them it is a plan-defect candidate, not a code bug.

## Phase 7

- **Emitter is literal, and takes every ordering decision from the model**:
  tree order for elements, element-signature order for keyword arguments
  (`inspect.signature(SqlBuilder.<tag>._func)`). Nothing iterates a set, so
  byte determinism is structural rather than a sorted() afterthought — and a
  reordered grammar parameter moves the emitted recipe with it instead of
  drifting from it.
- **Variables only where something reads them back**: db, schema, table, and
  a column that carries a relation. Chaining `column(...).relation(...)` was
  rejected: it forces line-wrapping inside a call chain, and the variable
  form is what a person writes by hand (Phase 4's golden recipe does exactly
  this with `author_id`).
- **SQL names are emitted as literals, Python identifiers are sanitized**
  separately, so `order-line` and `class` never meet each other's namespace.
- **`tests/conftest.py`: the pg facade now follows the recipe.** Phase 5
  hardcoded `RECIPE_DB_NAME`/`APPLICATION_SCHEMAS` in the facade, which made
  the fixture usable by exactly one recipe; Phase 7's contract migrates a
  different one (`recipes`/`wfp7`) through the same `pg_database`. The facade
  gained `adopt()` and an autouse fixture wraps `SqlMigrator.extractOrm` to
  call it with the structure being diffed — so label and introspection
  schemas come from the ORM side by construction, for any recipe. Declared
  schemas are still returned first, so Phase 5's first preparation sees
  exactly what it saw before.
- **`pg_database.get_json_struct()`** is the facade-level introspection the
  Phase 7 contract calls; upstream spells it
  `db.adapter.reader.get_json_struct(db.get_dbname(), schemas=...)`
  (migrator.py `extractSql`), and the fixture just binds those three.
- **The blocker is recorded as a plan-defect claim on the phase**, not
  worked around. Worth keeping for whoever judges it: the live-PostgreSQL
  closure (apply -> introspect -> read -> emit -> exec -> render -> diff
  empty) passes, so the reverse pipeline itself is closed end to end.

## Run inspection (second run, phases 7-9)

- Phase 7 closed [!] with a plan-defect claim, exactly the watch point recorded
  after Phase 6: the contract's `'name="idx_'` prohibition predates the ratified
  hashed-index round-trip law. The claim was correct — the first true one of the
  workflow (the Phase 2 and 5 claims were both wrong).
- Consult answered `stop` by the user (credit budget: no fable repair for a
  one-line contract edit). The foreman applied the edit to both contract copies,
  re-ran the suite (76 passed, ruff clean, PG closure live) and closed the phase
  [x] in cf6f56a. The emitter code committed by the failed session (34ac0cf)
  needed no repair.
- Ledger entry appended to ~/.phased/wf-lessons.md: contract tests authored at
  plan time can codify assertions that later ratified decisions invalidate;
  /write-workflow has no cross-check between contract assertions and the
  decisions later phases are allowed to bend.
- Phases 8-9 did not run (run stopped by the consult). Resume: fresh /run-workflow.
