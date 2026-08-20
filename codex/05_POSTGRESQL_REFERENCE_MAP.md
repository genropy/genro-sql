# Mappa della documentazione PostgreSQL per la grammar

**Riferimento consultato:** PostgreSQL 18, documentazione “current” al
20 agosto 2026. Prima di stabilizzare l'API, dichiarare la versione minima
supportata e verificare ogni feature anche contro quella versione.

Questa mappa non suggerisce di riprodurre tutta la sintassi SQL come parametri.
Serve a derivare un modello semantico completo, distinguendo capacità portabili
e opzioni PostgreSQL.

## 1. Fonti generali

- [Data Definition](https://www.postgresql.org/docs/current/ddl.html) — indice
  di tabelle, default, identity, generated column, constraint, schema,
  partitioning e altri oggetti.
- [SQL Commands](https://www.postgresql.org/docs/current/sql-commands.html) —
  indice normativo dei comandi.
- [Data Types](https://www.postgresql.org/docs/current/datatype.html) — tipi
  built-in e proprietà da mappare sui dtype normalizzati.

## 2. Mapping per elemento

| Grammar | Documento ufficiale | Parametri/capacità da valutare |
|---|---|---|
| `db` | [CREATE DATABASE](https://www.postgresql.org/docs/current/sql-createdatabase.html) | owner, template, encoding, strategy, locale/provider, tablespace, connection limit; esecuzione fuori transaction |
| `schema` | [CREATE SCHEMA](https://www.postgresql.org/docs/current/sql-createschema.html) | authorization/owner, IF NOT EXISTS, search path come configurazione separata |
| `table` | [CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html) | temporary/unlogged, inherits, partition, tablespace, storage parameters, ON COMMIT, access method |
| `column` | [CREATE TABLE](https://www.postgresql.org/docs/current/sql-createtable.html) | type, collation, default, nullability, compression, storage, generated, identity |
| `constraint` | [Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) | CHECK, UNIQUE, PRIMARY KEY, EXCLUDE, FK, deferrable, NULLS NOT DISTINCT, INCLUDE |
| `relation` fisica | [CREATE TABLE / REFERENCES](https://www.postgresql.org/docs/current/sql-createtable.html) | columns, target, MATCH, ON DELETE/UPDATE, deferrable, initially deferred |
| `index` | [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) | unique, concurrently, method, expression, collation, opclass, ASC/DESC, NULLS, INCLUDE, with_options, tablespace, where |
| `view` | [CREATE VIEW](https://www.postgresql.org/docs/current/sql-createview.html) | recursive, columns, options, check option; limiti di OR REPLACE |
| materialized view | [CREATE MATERIALIZED VIEW](https://www.postgresql.org/docs/current/sql-creatematerializedview.html) | method, storage, tablespace, WITH DATA; nessun OR REPLACE generale |
| `function` | [CREATE FUNCTION](https://www.postgresql.org/docs/current/sql-createfunction.html) | identity args, return, language, volatility, null input, security, parallel, cost, rows, config, body |
| procedure | [CREATE PROCEDURE](https://www.postgresql.org/docs/current/sql-createprocedure.html) | arguments, language, security, config, body; distinguere da function |
| `sequence` | [CREATE SEQUENCE](https://www.postgresql.org/docs/current/sql-createsequence.html) | data type, increment, bounds, cycle, start, cache, owned_by |
| `dbtype` enum/composite/range | [CREATE TYPE](https://www.postgresql.org/docs/current/sql-createtype.html) | kind-specific model; non ridurre tutte le forme a kwargs non validati |
| domain | [CREATE DOMAIN](https://www.postgresql.org/docs/current/sql-createdomain.html) | base type, collation, default, nullability, named CHECK |
| `trigger` | [CREATE TRIGGER](https://www.postgresql.org/docs/current/sql-createtrigger.html) | timing, events/update columns, table, transition tables, row/statement, WHEN, function, args, constraint/deferred |
| `extension` | [CREATE EXTENSION](https://www.postgresql.org/docs/current/sql-createextension.html) | schema, version, cascade; privilegi e trusted extensions |
| `eventTrigger` | [CREATE EVENT TRIGGER](https://www.postgresql.org/docs/current/sql-createeventtrigger.html) | event, TAG filters, function; oggetto database-level |

## 3. Feature che la grammar corrente non esprime completamente

### Database

- opzioni di locale/provider e template;
- owner e tablespace;
- database creation fuori transaction;
- distinzione fra creare database e allinearne gli oggetti interni.

Queste opzioni sono PostgreSQL-specifiche e possono appartenere a
`PostgresDbElements` o a un handler di bootstrap, non al core SQL comune.

### Tabelle

- temporary e unlogged;
- identity columns;
- generated stored/virtual secondo versione;
- partitioning e partition bound;
- inheritance;
- storage parameters e tablespace;
- row-level security/policy;
- exclusion constraints;
- foreign table.

Non inserire tutto nella prima slice. Registrare capability e casi reali.

### Indici

Il contratto `structure-1.0` copre già columns con ordine, method, where,
tablespace, unique e with_options. La documentazione PostgreSQL mostra ulteriori
dimensioni:

- expression key;
- collation e operator class per chiave;
- NULLS FIRST/LAST;
- INCLUDE columns;
- NULLS NOT DISTINCT;
- concurrently;
- IF NOT EXISTS e ONLY;
- limiti per metodo e versioni.

La forma `columns: {name: sort}` non basta per tutte le opzioni. Prima di
estendere il contratto, modellare una `IndexKey` tipizzata e verificare il
round-trip dei cataloghi.

### Funzioni e procedure

Non usare un'unica stringa `arguments` come contratto finale se servono GUI,
validation e round-trip. Considerare un modello strutturato degli argomenti,
con un renderer verso l'identity signature canonica richiesta dal migratore.

### Tipi

Enum, composite, range e domain hanno parametri e regole differenti. Preferire
elementi o modelli discriminati per kind, mantenendo `sql_type` come escape
hatch per tipi nativi non compresi.

## 4. Come usare la documentazione per generare la grammar

Per ogni comando:

1. estrarre la synopsis dalla versione minima supportata;
2. classificare ogni clausola come:
   - semantica portabile;
   - opzione PostgreSQL;
   - opzione operativa del renderer/migratore;
   - informazione derivabile e quindi non necessaria in authoring;
3. trasformare insiemi chiusi in enum/Literal;
4. trasformare sottostrutture ripetute in modelli Pydantic;
5. dichiarare default del database e default della grammar separatamente;
6. aggiungere vincoli fra parametri;
7. verificare cosa può essere letto dai cataloghi;
8. definire il mapping normalized JSON;
9. aggiungere un esempio positivo e almeno un errore negativo;
10. aggiungere apply + introspection + diff vuoto.

Un LLM può produrre rapidamente la prima firma e la documentazione, ma la
completezza viene dimostrata dalla matrice command → catalog → normalized JSON →
recipe → DDL, non dal numero di parametri generati.

## 5. Portabilità e capability

Ogni elemento/parametro dovrebbe esporre metadati neutrali:

```text
portable: true/false
dialects: [postgresql, sqlite, mysql, mssql]
since: versione minima del backend
migration_contract: 1.0 / futura versione
reader_support: yes/no
writer_support: yes/no
```

Il renderer deve:

- emettere un errore in modalità strict per feature non supportate;
- poter produrre warning strutturati in modalità compatibility;
- non scartare mai silenziosamente un'opzione fisica.

## 6. Regola di aggiornamento

Non usare per sempre gli URL `current` come unico riferimento di test. Nel
codice e nella CI fissare una matrice di versioni PostgreSQL supportate. Gli URL
`current` sono utili per la progettazione, mentre il comportamento deve essere
verificato sulla versione minima e su quella più recente supportata.
