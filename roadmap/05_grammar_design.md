# genro-sql — SQL Model Grammar Design

**Version**: 0.1.0 · **Last Updated**: 2026-07-06 · **Status**: 🔴 DA REVISIONARE

The design document for the new SQL model grammar, built as a
genro-builders dialect in the `genro-sql` package. It is grounded in
the legacy inventories `01`–`04` (see `00_INDEX.md`): every legacy
behavior referenced here has a file:line source in those documents.

---

## 1. Vision

Describe an entire database in Python through a builder grammar. The
**source tree is the single pivot**; every other representation is a
projection from/to the tree:

```
                       ┌────────────────────────────┐
   .py idiomatic  ◀────┤        source tree         ├────▶  DDL (CREATE/ALTER)
   (emitter)           │   (SqlBuilder grammar)     │       (SqlRenderer, partial or total)
                       │                            │
   live DB        ────▶│                            ├────▶  normalized JSON
   (reader,            └────────────────────────────┘       (genro-sqlmigration)
    introspection)                    │
                                      ▼
                            query compiler (later phase)
```

- **Renderer** (tree → DDL): partial (one table → its CREATE TABLE) or
  total; one renderer per SQL dialect.
- **Migration**: the tree projects into the normalized JSON of
  genro-sqlmigration (doc `03` §1), replacing the legacy
  `orm_extractor`; diff engine and command builder are reused as-is.
- **Round-trip** (like the XSD dialect): a reader (introspection → tree,
  the `db_extractor` queries already exist) and an emitter (tree →
  idiomatic .py — what the legacy package editor does).
- **Compiler** (later): `$col` / `@rel.col` / `:param` / `#macros`
  query compilation reading the same tree (contract in doc `02`).

Scope is **wider than the legacy**: the grammar reserves slots for the
entities the legacy migrate planned but never implemented (doc `03`
§6): views, functions, sequences, custom types, table triggers, CHECK
constraints, comments — plus extensions and event triggers which the
legacy handles only on the migrate side.

## 2. Agreed decisions

### 2.1 Hierarchy (base)

```
db                          # root of the model
├── schema                  # collection by name (legacy "package")
│   ├── table               # collection by name
│   │   ├── column          # physical
│   │   ├── aliasColumn     # relation_path
│   │   ├── formulaColumn   # sql_formula | select | exists
│   │   ├── subQueryColumn  # query + mode json|xml|aggr
│   │   ├── pyColumn        # py_method
│   │   ├── compositeColumn # composed_of (second slice)
│   │   ├── relation        # table-level FK: from_columns/to_columns
│   │   ├── constraint      # UNIQUE / CHECK multi-column
│   │   ├── index
│   │   └── trigger         # [beyond legacy]
│   ├── view                # [beyond legacy]
│   ├── function            # [beyond legacy]
│   ├── sequence            # [beyond legacy]
│   └── dbtype              # ENUM/DOMAIN/COMPOSITE [beyond legacy]
├── extension               # [migrate-only in legacy]
└── eventTrigger            # [migrate-only in legacy]
```

- **Direct children of table** — no plural container nodes
  (`t.column(...)`, not `t.columns.column(...)`): the tag types the
  node; projections group by entity.
- **`collection_key="name"`** on db/schema/table: children labelled by
  their own name → natural addressing (`public.customer.bank_id`),
  grammar-enforced name uniqueness, 1:1 projection onto the
  name-keyed dicts of the migration JSON.
- **`pkey` on the table, composite allowed** (`pkey="a,b"`), mapping to
  the JSON `pkeys` string.

### 2.2 Columns are a family of distinct elements

Each column kind is its own element (tag-dispatched by every consumer),
mirroring the legacy family (doc `01` §1.6–1.15). `bagItemColumn`,
`toolColumn`, `joinColumn` come later — they are sugar over the same
bases (and partly PG-specific: doc `01` §5.23).

Column attributes: the physical plane is the migrate contract
(`dtype`, `size`, `notnull`, `sqldefault`, `unique`, `indexed`,
`extra_sql`, `generated_expression` — doc `03` §1.2) plus `sql_type`
as native escape hatch and `comment` (planned improvement in the
legacy). `dtype` uses the Genro normalized codes (doc `03` §5.1);
`sql_type`, when present, wins.

### 2.3 Open metadata everywhere

Every element accepts free kwargs stored as node attributes: the
semantic plane (`name_long`, `name_short`, `group`, validators,
trigger hooks, application extensions...) travels in the tree.
Consumers filter: the DDL renderer reads the physical plane, the
migration projection filters its keys, the future compiler reads the
semantic plane. This matches the legacy's open `**kwargs` (doc `01`
§2) without freezing the attribute inventory.

### 2.4 Relations: two declaration forms, two planes, virtual-friendly

- **Column-level** (legacy-style): `relation` as child element of ANY
  column kind — including virtual columns (formula/subquery/alias),
  which the legacy explicitly supports (doc `04` oracle #13: formula
  column with chained `.relation()`).
- **Table-level** (new, genro-proxy model): `relation` as child of
  table with `from_columns` / `to_columns` (str | csv | list —
  composite FK without needing a compositeColumn), `on_delete`, back
  naming.
- **Two planes kept separate**, as in the legacy (doc `01` §1.18, §3):
  semantic (`mode`, `one_name`/`many_name`, `eager_*`, `one_one`,
  `one_group`/`many_group`, python-level `onDelete`/`onUpdate`,
  `relation_name`, `onDuplicate`) vs physical (`onDelete_sql`/
  `onUpdate_sql`, `deferred` → the FK the migrate sees).
- **Coherence rule in the grammar**: a relation under a virtual column
  cannot be `mode="foreignkey"` (no SQL constraint from a formula);
  the migrate projects only physical FK relations (legacy behavior:
  FK emitted only if `joiner['foreignkey']`, doc `03` §2.3), the
  compiler navigates them all.

### 2.5 Style

- **kwargs only** (builders convention); no `name::dtype` positional
  shorthand (inconsistent even in the legacy — doc `01` §5.3).
- camelCase for grammar names per NAMING_CONVENTIONS.md.
- Loud errors, no silent fallbacks (contrast with legacy `addRelation`
  swallowing all exceptions — doc `01` §5.10).

## 3. Design questions raised by the inventories (to discuss)

Ordered; each is a separate decision to take one at a time.

1. **Relation mode as orthogonal flags.** Legacy `mode` multiplexes
   `relation|foreignkey|insensitive|custom` (doc `01` §5.14). Proposal:
   `foreignkey=True/False`, `case_insensitive=True/False`, and `cnd`/
   `join_on` as ordinary attributes — no mode string.
2. **Back-relation naming.** Legacy: `relation_name` (unique per
   one-table, default `pkg_table_column`), `private_relation` when
   unnamed, `one_one='*'` special-casing (doc `01` §3.3). genro-proxy:
   `back_name` + filtered `add_back(condition)`. Decide the new story.
3. **Table-header system patterns.** `sysFields` (id/ins_ts/draft/
   logical deletion/counter/hierarchical), `rowcaption`/`caption_field`,
   `partition_*`, `multi_tenant`, `lookup` (doc `04` §2c, oracle #8,
   #14, #19). These live ABOVE the pure grammar in the legacy (dbo
   mixins). Decide what is grammar, what is a downstream layer.
4. **subtable.** Two unrelated meanings in the legacy (doc `01` §5.22):
   package-level single-table inheritance (discriminator column) and
   table-level named filter. Probably two distinct elements — names to
   be chosen.
5. **colgroup.** Ordinal group labelling with side effects on the table
   node (doc `01` §1.5). Keep, redesign, or drop to downstream?
6. **Extension mechanism.** Legacy mixins (`config_db`,
   `config_db_<pkg>`, `ext_*` hooks, `custom_type_<dtype>` — doc `01`
   §5.16–17). The builders engine has components/sub-builders/
   struct_methods; map the use cases.
7. **PG leakage.** bagItem xpath formulas, json/xml aggregation SQL,
   tool HTML-in-SQL are PostgreSQL-specific text generated at grammar
   time in the legacy (doc `01` §5.23). In the new design the grammar
   stores intent (declarative attributes); the renderer/dialect emits
   SQL. This moves `subQueryColumn` mode json/xml expansion into the
   renderer.
8. **Deferred validation.** compositeColumn validates at build end
   (doc `01` §1.10); the builders engine has its own lifecycle
   (create/preprocess) — map deferral onto it.
9. **Localized / variant / encrypted columns.** Stringly-typed,
   env-dependent machinery in the legacy (doc `01` §5.20–21). Decide
   which enter the grammar now and in what shape.
10. **Naming of implicit indexes.** Three conventions in the legacy
    (doc `01` §5.11); the migrate uses structural hashed names (doc
    `03` §1.3). Proposal: adopt the hashed-name model everywhere.

## 4. Implementation plan (slices)

1. **Slice 1 — base grammar**: `db`, `schema`, `table`, `column`,
   `aliasColumn`, `formulaColumn`, `subQueryColumn`, `pyColumn`,
   `relation` (both forms), `constraint`, `index`. Tests from the
   oracle shortlist (doc `04` §6, items 1–7).
2. **Slice 2 — compositeColumn** + composite pkey/FK (oracle #10, #16).
3. **Slice 3 — DDL renderer** (CREATE TABLE first, postgres dialect),
   validated against the exact-SQL expectations of
   `test_gnrsqlmigration.py`.
4. **Slice 4 — migration projection** (tree → normalized JSON),
   plugging into genro-sqlmigration.
5. **Slice 5 — beyond-legacy entities** (view, function, sequence,
   dbtype, trigger, extension, eventTrigger, CHECK, comments).
6. **Slice 6 — round-trip** (reader + emitter).
7. **Later — query compiler** (doc `02` as contract).

---

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06)
- Inventories: `01_legacy_model_grammar.md`, `02_legacy_compiler_query.md`, `03_legacy_migration_adapters.md`, `04_legacy_tests_inventory.md`
- Relations table-level reference: `genro-proxy/src/genro_proxy/sql/relation.py` + README §Relations
