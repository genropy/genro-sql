# SQL model grammar reference

Generated from the live grammar by `genro_sql.modern.grammar_doc.generate_grammar_md()`. Do not edit by hand: regenerate with `python -m genro_sql.modern.grammar_doc`.

Every element signature is **semi-closed**: it declares its physical and its enumerated semantic parameters and accepts `**extra` on top, where each extra key must start with `x_`.

## Hierarchy

```
db
├── schema
│   └── table
│       ├── column
│       │   └── relation
│       ├── aliasColumn
│       ├── formulaColumn
│       ├── subQueryColumn
│       ├── pyColumn
│       ├── compositeColumn
│       │   └── relation
│       ├── constraint
│       └── index
└── extension
```

## Elements

### `db`

Database root, one per model.

- Contains: schema, extension
- Cardinality: name-keyed collection on `name`
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the database name — the JSON `entity_name`. |

### `extension`

A PostgreSQL extension.

Rendered `CREATE EXTENSION IF NOT EXISTS` and never dropped.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the extension name (`pg_trgm`, `unaccent`, …). |

### `schema`

A database schema (a 'package' in the legacy vocabulary).

- Contains: table
- Cardinality: name-keyed collection on `name`
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the schema name — physical, and this node's key. |
| `comment` | `str` | `None` | semantic | free description. |

### `table`

A table.

- Contains: column, aliasColumn, formulaColumn, subQueryColumn, pyColumn, compositeColumn, constraint, index
- Cardinality: name-keyed collection on `name`
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the table name — physical, and this node's key. |
| `pkey` | `str` | `None` | physical | comma-joined physical column names, the JSON `pkeys`. Every name must exist among the table's physical columns. |
| `comment` | `str` | `None` | semantic | free description. |
| `caption_field` | `str` | `None` | semantic | the column that captions a row. |
| `name_long` | `str` | `None` | semantic | human label. |
| `name_plural` | `str` | `None` | semantic | human label, plural form. |

### `column`

A physical column — the only element that projects as a column.

- Contains: relation
- Cardinality: ordered children, not name-addressable
- Projection flags: `projects_column`, `projects_relation`
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the column name — physical, and this node's key. |
| `dtype` | `DTYPE` | `None` | physical | Genro normalized type code. Absent, the renderer defaults to `'A'` when `size` is given, else `'T'`. |
| `size` | `str` | `None` | physical | `'n'` or `'min:max'` character size. |
| `notnull` | `bool` | `False` | physical | NOT NULL. Pkey members get it from their pkey membership, not from this flag. |
| `unique` | `bool` | `False` | physical | single-column UNIQUE. A redundant one on a single-column pkey is dropped by the renderer. |
| `indexed` | `bool` | `False` | physical | sugar — the renderer materializes a real index item (`structure-1.0` has no `indexed` column attribute). A column carrying a foreign key is always indexed. |
| `sqldefault` | `str` | `None` | physical | SQL DEFAULT expression. |
| `sql_type` | `str` | `None` | physical | native type, the escape hatch; wins over `dtype`. |
| `extra_sql` | `str` | `None` | physical | verbatim tail of the column definition. |
| `generated_expression` | `str` | `None` | physical | GENERATED ALWAYS AS expression. |
| `comment` | `str` | `None` | physical | the column comment. |
| `name_long` | `str` | `None` | semantic | human label. |
| `name_short` | `str` | `None` | semantic | human label, short form. |
| `group` | `str` | `None` | semantic | field-group key. |

### `aliasColumn`

A virtual column projecting a related column. Never physical.

An alias reads through a relation that already exists, so it never
carries one of its own.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the alias name. |
| `relation_path` | `str` | *required* | physical | `@relation.column` path to the source column. |
| `name_long` | `str` | `None` | semantic | human label. |
| `group` | `str` | `None` | semantic | field-group key. |

### `formulaColumn`

A virtual column defined by SQL. Never physical.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the column name. |
| `sql_formula` | `str` | `None` | physical | an expression over the row's own columns. |
| `select` | `str` | `None` | physical | a scalar sub-select. |
| `exists` | `str` | `None` | physical | an EXISTS predicate. |
| `dtype` | `DTYPE` | `None` | physical | the resulting type code. |
| `name_long` | `str` | `None` | semantic | human label. |
| `group` | `str` | `None` | semantic | field-group key. |

### `subQueryColumn`

A virtual column defined by a sub-query. Never physical.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the column name. |
| `query` | `str` | *required* | physical | the sub-query. |
| `mode` | `str` | `None` | physical | `json`, `xml` or a scalar aggregate. Expanding it is the renderer's job, not grammar-time. |
| `name_long` | `str` | `None` | semantic | human label. |
| `group` | `str` | `None` | semantic | field-group key. |

### `pyColumn`

A virtual column computed in Python. Never physical.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the column name. |
| `py_method` | `str` | `None` | physical | the method computing it; defaults to `pyColumn_<name>` on the table class. |
| `dtype` | `DTYPE` | `None` | physical | the resulting type code. |
| `name_long` | `str` | `None` | semantic | human label. |
| `group` | `str` | `None` | semantic | field-group key. |

### `compositeColumn`

N physical columns packed as one navigable key.

Not a column of its own — it projects no column, only what its
members already are. THE mechanism for a multi-column key: a
composite FK is a `relation` on a compositeColumn, and a
composite UNIQUE is `unique=True` here.

- Contains: relation
- Cardinality: ordered children, not name-addressable
- Projection flags: `projects_relation`
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the composite name (legacy `composed_of` carried the members instead). |
| `columns` | `str` | *required* | physical | comma-joined member names, all physical columns of the same table. |
| `unique` | `bool` | `False` | physical | projects a multi-column UNIQUE constraint. |
| `name_long` | `str` | `None` | semantic | human label. |
| `group` | `str` | `None` | semantic | field-group key. |

### `constraint`

A table constraint.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | *required* | physical | the constraint name — this node's key. |
| `constraint_type` | `CONSTRAINT_TYPE` | *required* | physical | `'UNIQUE'` (needs `columns`) or `'CHECK'` (needs `check_clause`). |
| `columns` | `str` | `None` | physical | comma-joined physical column names. |
| `check_clause` | `str` | `None` | physical | the CHECK expression. |

### `index`

A table index.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `name` | `str` | `None` | physical | the index name. |
| `columns` | `object` | `None` | physical | comma-joined names, or a `{name: None | 'DESC'}` dict when per-column ordering matters. |
| `unique` | `bool` | `False` | physical | a UNIQUE index. |
| `method` | `str` | `None` | physical | access method (`btree`, `gin`, …). |
| `where` | `str` | `None` | physical | partial-index predicate. |
| `tablespace` | `str` | `None` | physical | target tablespace. |
| `with_options` | `dict` | `None` | physical | storage parameters. |

### `relation`

A relation on a column. Navigable by default, physical on demand.

At most one per column: the grammar accepts the insertion so the
whole document can be built, and `SqlBuilder.validate_source`
reports every column carrying more than one.

- Contains: *nothing*
- Cardinality: ordered children, not name-addressable
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| `to` | `str` | *required* | physical | the target, `schema.table.column` or `schema.table` (target columns default to the target pkey). |
| `foreign_key` | `bool` | `False` | physical | emit a physical FK. Only these relations project into the migration JSON. |
| `on_delete` | `FK_ACTION` | `None` | physical | referential action on delete. |
| `on_update` | `FK_ACTION` | `None` | physical | referential action on update. |
| `deferred` | `bool` | `False` | physical | INITIALLY DEFERRED. |
| `indexed` | `bool` | `True` | physical | the supporting index of the foreign key. On by default (legacy parity, D3); `False` states that the columns are deliberately left unindexed. |
| `back_reference` | `str` | `None` | semantic | navigable path of the many side. |
| `one_name` | `str` | `None` | semantic | human label of the one side. |
| `many_name` | `str` | `None` | semantic | human label of the many side. |
| `one_one` | `bool` | `False` | semantic | the relation is 1:1. |
| `case_insensitive` | `bool` | `False` | semantic | join case-insensitively. |
