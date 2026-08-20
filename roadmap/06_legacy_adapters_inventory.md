# Legacy Inventory — Adapters (gnr.sql.adapters), full API surface

**Version**: 0.1.0 · **Last Updated**: 2026-07-08 · **Status**: 🔴 DA REVISIONARE

Complete critical inventory of the legacy adapter layer. Complements
doc `03` §5, which covers only the DDL/`struct_*` surface: this
document adds the file inventory with maintenance status, the full
base-class API grouped by functional area, the duplicated
introspection paths, the age analysis, the call surface the rewrite
must respect ("rispettando le chiamate", decided 2026-07-08), and the
test map. Source of truth: Genropy worktree
`/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop` @
`83c138bb6`; every file:line reference verified on 2026-07-08.

---

## 1. File inventory and maintenance status

| File | Lines | DB target | Driver | Capabilities | Status |
|---|---|---|---|---|---|
| `__init__.py` | 20 | — | — | — | `__all__` loader (glob `gnr*.py`) |
| `_gnrbaseadapter.py` | 1655 | abstract base | — | `set()` empty (`:87`) | actively maintained |
| `_gnrbasepostgresadapter.py` | 1336 | postgres base | — | `{MIGRATIONS, VECTOR, SCHEMAS}` (`:114-118`) | actively maintained, modern (f-string dominant) |
| `gnrpostgres.py` | 1017 | postgres | `psycopg2` (`:27,:38`) | inherits PG base | maintained, **primary** |
| `gnrpostgres3.py` | 375 | postgres | `psycopg` v3 (`:28`) | inherits PG base | maintained, active (tested) |
| `gnrpostgres8000.py` | 338 | postgres | `pg8000` (`:26`) | `{SCHEMAS}` only (`:103-105`) | marginal (no MIGRATIONS) |
| `gnrsqlite.py` | 592 | sqlite | `sqlite3` stdlib (`:29`) | `{SCHEMAS}` only (`:56-58`) | maintained (used in tests) |
| `gnrmysql.py` | 455 | mysql | `MySQLdb`/`pymysql` (`:29,:34`) | `{SCHEMAS}` only (`:64-66`) | semi-abandoned |
| `gnrmssql.py` | 479 | ms sql server | `pymssql` (`:26-28`) | `{SCHEMAS}` only (`:115-117`) | semi-abandoned |
| `gnrdb2_400.py` | 447 | IBM DB2/AS400 | `pyodbc` (`:25`) | **none** (no CAPABILITIES attr) | abandoned |
| `gnrfourd.py` | 390 | 4th Dimension | `fourd` (`:25`, dead driver) | **none** | dead |

Notes:

- The identical last-commit date 2026-02-26 on 5 adapters (`db2_400`,
  `fourd`, `mssql`, `mysql`, `pg8000`) is a mass reformatting commit,
  not functional maintenance.
- `gnrfourd.py` and `gnrdb2_400.py` define no `CAPABILITIES`, so they
  never appear in `ADAPTERS_BY_CAPABILITY` (`sql/__init__.py:24-33`);
  their drivers are not installed. Effectively dead code.
- Adapter loading: `sql/__init__.py:21-33` glob-discovers `gnr*.py`,
  imports each in `try/except` — a missing driver silently discards
  the adapter. `gnrmysql.py:34` has a **bare** `import MySQLdb`
  outside the try block: if `pymysql` does not install the alias, the
  whole module import fails.
- `TODO`/`NotImplementedError` markers: the vacuum comment "TEST IT,
  SEEMS TO LOCK…" is copy-pasted verbatim in `gnrmssql.py:216`,
  `gnrpostgres3.py:65`, `gnrpostgres8000.py:164`; `gnrmysql.py:156`
  vacuum is entirely commented out; `gnrsqlite.py:356` "TODO:
  implement getTableConstraints". In the base, ~35 `struct_*` methods
  plus `importRemoteDb`/`listRemoteDatabases`/`relations`/`restore`/
  `lockTable`/`listen` raise `AdapterMethodNotImplemented` — the base
  is almost entirely abstract.

## 2. Base-class API surface (`SqlDbAdapter`, `_gnrbaseadapter.py:75`) by functional area

"Override" lists the concrete adapters redefining the method
(`PG base` = `_gnrbasepostgresadapter.py`).

### 2.1 Connection / cursors

| Method | Line | Base impl | Override |
|---|---|---|---|
| `get_connection_params(storename=None)` | 234 | concrete (delegates to dbroot) | — |
| `connect(storename=None, autoCommit=False, **kw)` | 240 | abstract | all 8 concrete adapters |
| `connection(manager=False, storename=None)` | 247 | concrete | — |
| `cursor(connection, cursorname=None)` | 254 | abstract | pg, pg3, pg8000, sqlite, mysql |
| `defaultMainSchema()` | 270 | abstract | PG base, pg8000, sqlite, mysql, mssql, fourd, db2 |

### 2.2 Name adaptation / SQL text

| Method | Line | Base impl | Override |
|---|---|---|---|
| `adaptSqlName(name)` | 196 | identity | PG base(`:237`), sqlite(`:131`), mysql(`:88`), mssql(`:143`), fourd(`:150`), db2(`:144`) |
| `adaptSqlSchema(name)` | 202 | → `schemaName` | mssql(`:152`), db2(`:147`) |
| `schemaName(name)` | 467 | concrete (`fixed_schema or name`) | — |
| `asTranslator(as_)` | 221 | `'"%s"'` | fourd(`:154`) |
| `adaptTupleListSet(sql, sqlargs)` | 208 | concrete (IN-list regex) | pg(`:147`), pg3(`:74`), fourd(`:128`) |
| `prepareSqlText(sql, kwargs)` | 442 | concrete | all 8 concrete adapters |

### 2.3 Query execution / DML

| Method | Line | Base impl | Override |
|---|---|---|---|
| `execute(sql, sqlargs=None, manager=False, autoCommit=False)` | 762 | concrete | sqlite(`:150`) |
| `raw_fetch(sql, sqlargs=None, ...)` | 780 | concrete | sqlite(`:172`) |
| `insert(dbtable, record_data, **kw)` | 797 | concrete | — |
| `insertMany(dbtable, records, **kw)` | 821 | concrete | — |
| `update(dbtable, record_data, pkey=None, old_record=None, **kw)` | 843 | concrete | — |
| `delete(dbtable, record_data, **kw)` | 879 | concrete | — |
| `sql_deleteSelection(dbtable, pkeyList)` | 894 | concrete | — |
| `emptyTable(dbtable, truncate=None, cascade=None)` | 905 | concrete | — |
| `fillFromSqlTable(dbtable, sqltablename)` | 917 | concrete | — |
| `existsRecord(dbtable, record_data)` | 291 | concrete | — |
| `prepareRecordData(record_data, tblobj=None, ...)` | 728 | concrete | — |
| `changePrimaryKeyValue(dbtable, pkey=None, newpkey=None, **kw)` | 225 | concrete | — |
| `compileSql(maintable, columns, distinct='', joins=None, where=None, …)` | 695 | concrete | pg(`:169`), pg3(`:121`), mssql(`:445`), db2(`:413`), fourd |
| `_selectForUpdate(maintable_as=None, mode=None)` | 721 | concrete | sqlite(`:140` → `''`), mysql(`:195`) |

### 2.4 Transactions

**There is no transaction abstraction in the adapter.** commit/rollback
live on the driver connection and are orchestrated in
`gnrsql/transactions.py`. The only transaction-adjacent adapter
surface is postgres-cursor-level: `setConstraintsDeferred`
(`gnrpostgres.py:405`, `gnrpostgres3.py:356`) and `callproc`
(`gnrpostgres.py:408`, `gnrpostgres3.py:359`). A rewrite should make
transactions an explicit abstraction.

### 2.5 DDL / `struct_*`

Inventoried in doc `03` §5.3. Additional finding: the non-`_sql`
variants `struct_add_table_pkey` / `struct_drop_table_pkey` (base
`:477`, `:502`; pg `:1059`, `:1065`) have **no callers** anywhere in
`gnr/` — dead code; the command builder uses only the `_sql` variants.
The pre-migration DDL helpers still in base (`addForeignKeySql:971`,
`addUniqueConstraint:989`, `addColumn:1035`, `alterColumnSql:1134` —
with the `ALTER TABLE %s ALTER TABLE %s TYPE %s` bug, fixed only in
the pg override `gnrpostgres.py:294` — `createIndex:1169`, etc.) are
the DDL API of the OLD `checkDb` engine (§3).

### 2.6 Introspection — two parallel families

See §3 below.

### 2.7 Listen / notify

| Method | Line | Base impl | Override |
|---|---|---|---|
| `listen(msg, timeout=None, onNotify=None, onTimeout=None)` | 381 | abstract | pg(`:231`), pg3(`:164`), pg8000(`:171`), sqlite(`:299` no-op), mssql(`:220` no-op) |
| `notify(msg, payload=None, autocommit=False)` | 429 | no-op | pg(`:265`), pg3(`:189`), pg8000(`:191`), sqlite(`:315`), mssql(`:231`) |
| `listen_connection(channels)` | 393 | returns `None` | PG base(`:1297`) |
| `poll_notifications(conn)` | 404 | returns `[]` | PG base(`:1313`) |

### 2.8 Lock / maintenance / dump-restore

`lockTable` (base `:423` abstract; PG base `:319`, sqlite `:390`
no-op). `analyze()` (`:929`), `vacuum(table='', full=False)` (`:933`,
overrides all carrying the same untested TODO). `dump` (`:284`; PG
base `:335`), `restore` (`:460`; pg `:224`, pg3 `:155`),
`importRemoteDb` (`:356`; PG base `:439`), `listRemoteDatabases`
(`:415`; PG base `:464`), `createDb`/`dropDb`/`createDbSql`/`dbExists`
(`:1197`/`:277`/`:1192`/`:1238`; PG base, pg8000, mysql, mssql, db2).

### 2.9 Localization / misc SQL helpers

`setLocale` (`:675`; PG base `:241`, sqlite `:134`), `mask_field_sql`
(`:948`; PG base `:248`, sqlite `:397`), `unaccentFormula` (`:1205`;
PG base `:1293`), `string_agg` (`:942`; sqlite `:394`), `ageAtDate`
(`:681`), `rangeToSql` (`:650`).

### 2.10 Capabilities / macros / where translator

`has_capability`/`not_capable` classmethods (`:343`/`:350`);
`registerMacros(db)` (`:182`, no-op; PG base `:222`); `macroExpander`
property (`:191`; PG base `:228`); `whereTranslator` lazy property
(`:1212`) → `GnrWhereTranslator` (`:1265`): ~25 `op_*` methods
(`op_equal`, `op_contains`, `op_between`, `op_in`, `op_regex`,
`op_fulltext`, … `:1504-1581`) plus `toText`/`toHtml`/
`prepareCondition`/`decodeDates`; overridden in PG base(`:667`),
mssql(`:442`), fourd(`:360`), db2(`:410`). **This is query-engine
surface, not DDL** — a scope decision for the rewrite (plan Fase 2.3).
Also in PG base: `get_primary_key_sql`/`get_unique_constraint_sql`/
`get_foreign_key_sql`/`get_check_constraint_sql` (`:1164-:1291`).

## 3. Model-from-DB: the duplicated introspection paths

Two complete, independent, both-live paths read the same information
from the database:

**NEW path (migration)** — `DbExtractor.get_info_from_db`
(`gnrsqlmigration/db_extractor.py:196-201`) calls exactly five adapter
methods: `struct_get_schema_info` (PG base `:711`),
`struct_get_constraints` (`:768`), `struct_get_indexes` (`:867`),
`struct_get_extensions` (`:1095`), `struct_get_event_triggers`
(`:1144`). They emit the normalized JSON directly.

**OLD path (checkDb)** — `SqlModelChecker` (`gnrsqlutils.py:123`) and
`ModelExtractor` (`gnrsqlutils.py:14`) call the legacy introspection:
`getColInfo` (`gnrsqlutils.py:57,281` → `gnrpostgres.py:302`),
`getPkey` (`:72` → PG base `:605`), `getIndexesForTable` (`:90,275` →
PG base `:623`), `relations()` (`:99,168` → PG base `:556`),
`getTableConstraints` (`:173` → PG base `:641`).

| Information | OLD (checkDb) | NEW (migration) | Duplicated |
|---|---|---|---|
| Columns + types | `getColInfo` | `struct_get_schema_info` | yes — two SELECTs on `information_schema.columns` |
| Primary key | `getPkey` | `struct_get_constraints` PK branch | yes |
| Indexes | `getIndexesForTable` (`pg_index`) | `struct_get_indexes` (`pg_index`/`pg_class`/`pg_am`) | yes |
| UNIQUE constraints | `getTableConstraints` (Bag) | `struct_get_constraints` UNIQUE branch | yes |
| Foreign keys | `relations()` (`information_schema.referential_constraints`) | `struct_get_constraints` FK branch (`pg_constraint` + `LATERAL UNNEST`) | yes — different strategies |
| Extensions | `_list_enabled_extensions` (`:518`) | `struct_get_extensions` (`:1095`) | yes |

Both are reachable in production: the OLD path via
`web/_gnrbasewebpage.py:787,796` (`self.db.checkDb()`) and
`gnrsqlmodel/model.py:450,463`; the NEW one via
`db/cli/gnrmigrate.py:218`. The OLD path is superseded for diff
purposes but was never removed. Rewrite decision (plan Fase 2.4): only
`struct_get_*` is ported; `checkDb` consumers move to the new path.

## 4. Code-age analysis

1. **No Python 2 residue** anywhere in `adapters/` (verified: no
   `has_key`/`iteritems`/print-statement/`basestring`/`xrange`).
2. **%-style formatting pervasive** in the older adapters
   (`_gnrbaseadapter.py` 94 occurrences; mysql 27, mssql/db2 22) vs
   f-string-dominant modern PG base (59 f-strings). DDL builds SQL by
   `%`/f-string interpolation of identifiers without systematic
   quoting (e.g. `struct_drop_table_pkey_sql:678`) — the rewrite must
   centralize identifier quoting.
3. **Three parallel postgres adapters** (psycopg2 primary, psycopg3
   active, pg8000 marginal). Consolidation target: one adapter
   (candidate psycopg3 — open question in the plan).
4. **Dead code**: `gnrfourd`/`gnrdb2_400` entirely; non-`_sql`
   pkey struct methods; commented vacuum (mysql), "seems unused"
   method (`gnrmssql.py:146`).
5. **Signature incoherences**: `getColInfo` has `column` required in
   base (`:305`) but `column=None` in all 8 overrides;
   `columnSqlType`/`columnSqlDefinition` overridden only in
   mysql/mssql/db2 with diverging logic.
6. **Class-level mutable `CAPABILITIES`**: `__init__` does
   `self.CAPABILITIES.add(ADMINISTER)` (`:165`) on the class-level
   set — fragile pattern.

## 5. Call surface (the compatibility contract — "rispettando")

Callers of `.adapter` grouped by subsystem (the surface the rewrite
preserves as much as possible, decision of 2026-07-08):

- **Core SQL runtime** (`gnrsql/`: `db.py`, `execute.py`, `query.py`,
  `write.py`, `transactions.py`, `connections.py`, `schema.py`,
  `env.py`): `execute`, `raw_fetch`, `insert(Many)`, `update`,
  `delete`, `cursor`, `connect`, `prepareSqlText`, `compileSql`,
  `whereTranslator`, `notify`, `listen`, `dump`, `restore`, `vacuum`,
  `analyze`, `createDb`/`dropDb`, `createSchema`/`dropSchema`,
  `dropTable`, `dropColumn`, `setLocale`, `registerMacros`,
  `emptyTable`, `fillFromSqlTable`. Adapter construction:
  `db.py:156` (`importModule(...).SqlDbAdapter(self)`), property
  `adapter` `db.py:266`.
- **ORM/model** (`gnrsqldata/compiler.py`, `record.py`;
  `gnrsqlmodel/*`; `gnrsqltable/*`): `adaptSqlName`, `asTranslator`,
  `columnSqlType`, `columnSqlDefinition`, `compileSql`,
  `changePrimaryKeyValue`.
- **Migration NEW** (`gnrsqlmigration/`): the five `struct_get_*`
  (db_extractor), ~15 `struct_*_sql` + `columnSqlType` +
  `TYPE_CONVERSIONS` (command_builder), `struct_auto_extension_attributes`,
  `createDbSql`, `createSchemaSql`, `has_capability`
  (orm_extractor/executor/migrator).
- **Migration OLD** (`gnrsqlutils.py`): the five legacy introspection
  methods (§3) — not to be ported.
- **App/infra** (`app/gnrapp.py`, `gnrdbo.py`, `gnrlistener.py`):
  `listen`, `listen_connection`, `poll_notifications`, `notify`.

Most-called methods (call sites outside `adapters/`): `adaptSqlName`
(12), `listElements` (8), `execute` (7), `asTranslator` (6),
`columnSqlType` (5), `struct_constraint_sql`/`notify`/`connect` (4).

## 6. Test map

All in `gnrpy/tests/sql/`:

| File | Lines | Tests | Pins |
|---|---|---|---|
| `test_gnrsqlmigration.py` | 1657 | 79 | whole migration engine on live postgres+postgres3 (skip unless `MIGRATIONS`); force/backup/extension/exception classes; exact-SQL oracles |
| `test_gnrbaseadapter.py` | 431 | 32 | base unit tests with `FakeDbRoot`: `__all__` == 8 adapters, `adaptSqlName`/`adaptSqlSchema`/`asTranslator`, extension no-ops |
| `test_adapterinheritance.py` | 53 | 2 | **structural contract**: all public base methods have docstrings; no concrete adapter exposes public methods absent from base |
| `test_macro_registration.py` | 250 | 26 | macro registry (TSQUERY/TSRANK/VECQUERY…) |
| `test_db_notify.py` | 264 | 12 | LISTEN/NOTIFY surface |
| `test_vecquery_macro.py` | 125 | 13 | pgvector macros — pure-compile (FakeQueryCompiler, no DB) |
| `test_connection_error.py` | 145 | 6 | connection-error taxonomy (psycopg2/psycopg3/migrator) |
| `test_gnrsql.py` | 138 | 7 | high-level `GnrSqlDb` API |
| `test_sqlite_boolean_rewrite.py` | 188 | 4 | sqlite `prepareSqlText` rewrites (ILIKE→LIKE, `IS [NOT] TRUE`) |
| `test_gnrsqlutils.py` | 22 | 1 | OLD checkDb path — effectively untested |

Implementations actually exercised (grep `implementation=`): postgres
(15 sites), sqlite (11), postgres3 (7), mysql (1). **mssql, fourd,
db2, pg8000 have zero tests.** Fixtures in `tests/sql/conftest.py`
(`db_sqlite:110`, `postgres:126`, `postgres3:146`) and
`tests/sql/common.py` (`testing.postgresql` ephemeral server).

## 7. Critical observations for the rewrite

1. Migration is de-facto **postgres-only** (`struct_*` only in the PG
   base; migration tests skip everything else). Postgres-first matches
   real usage (95%).
2. Consolidate the three postgres adapters into one; pg8000 has no
   migration support and near-zero maintenance.
3. Unify introspection on `struct_get_*`; the OLD `checkDb` path is
   still wired but superseded — do not port it.
4. The call surface is wide but known (~60 methods); the
   `test_adapterinheritance` contract (no public method outside the
   base interface) is worth keeping in the new design.
5. Transactions need an explicit abstraction (absent in the legacy).
6. `GnrWhereTranslator` is a query sub-engine living inside the
   adapter — scope decision required (new query engine vs out of
   scope).
7. Do not port dead code: `fourd`, `db2_400`, non-`_sql` pkey struct
   methods, commented vacuum.
8. Centralize DDL identifier quoting (legacy interpolates raw names).
9. Normalize incoherent signatures (`getColInfo`); the base
   `alterColumnSql` bug shows base implementations were not exercised.
10. `test_gnrsqlmigration.py` is the de-facto DDL/migration spec —
    regression oracle for the rewrite. The OLD path has 1 test: if
    ever kept, it must be covered first.

---

## Riferimenti

- Exploration session: 2026-07-08.
- Legacy source: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/adapters/` @ `83c138bb6`.
- Complementary: doc `03` §5 (DDL/`struct_*` surface, dtype tables, capabilities).
