# Coherence review — wf/sql-recipe-pipeline (Phase 9)

Scope: the 24 files written by Phases 1..8, read against each other and
against the plan's global decisions (D1..D12). Two convergence cycles; a
third was not run — nothing auto-fixable was left.

## Auto-fixed

| File | What | How |
| --- | --- | --- |
| `src/genro_sql/modern/validators.py` | `_check_pkey`, `_check_composites`, `_check_constraints`, `_check_indexes` each took a `key` argument none of them read; the caller now iterates `self._tables.values()` | manual, found by an AST unused-parameter scan; suite re-run green |
| `src/genro_sql/modern/reader.py` | same dead `key` argument on `_fill_relations`, `_fill_constraints`, `_fill_indexes`; caller iterates `tables.values()` | idem |
| `src/genro_sql/modern/grammar_doc.py` | `_plane(name, description)` never read `name` — now `_plane(description)` | idem |
| `src/genro_sql/modern/grammar_doc.py` | its ten new functions carried no `# wf:phase-8:new` markers, unlike every other module of the run; markers added so the naming review sees them | manual, contract check (`contracts.md` → new-method markers) |
| `pyproject.toml` | `ruff check .` failed on `.phased/**/tests/phase-3/test_wf_phase3_validators.py` (F841) while `ruff check src tests` was clean: the plan-directory contract copies are the same read-only files as their `tests/` twins, but the existing `per-file-ignores` glob only covered the twins. Glob extended with `".phased/**/test_wf_phase*.py"` | manual, existing documented policy applied to the same files |

No lint fix was needed on the reviewed set itself: `ruff check` was already
clean on it before this phase.

## Flagged for human

1. **`grammar_doc.py` imports a genro-builders private symbol.**
   `from genro_builders.builder._grammar_export import _class_schema_to_grammar_document`.
   The plan's Phase 8 pattern reference points at the public
   `BuilderBase.to_grammar()`, but that method takes a `path`, writes a JSON
   file and returns `None` — there is no public in-memory route to the
   document dict, and round-tripping through a temp file to avoid a private
   import would be worse. Suggested action: open a genro-builders issue for a
   public dict-returning accessor (e.g. `to_grammar_document()`), switch when
   it lands. Cross-package coupling, not auto-fixable here.

2. **`_names()` exists three times, and the copies diverge.**
   `migration._names`, `validators.SqlModelValidator._names`,
   `reader._names` — same contract (comma-joined string / dict / sequence ->
   list of names) but the reader's list branch does not `.strip()` its items
   while the other two do. Harmless today (JSON lists arrive clean), a real
   trap the day the reader is fed a hand-written structure. Suggested action:
   one shared helper in `genro_sql.modern` and three call sites. Where it
   should live is a design call, so it is not auto-fixed.

3. **`_INDEX_OPTIONS` is duplicated verbatim** in `migration.py` and
   `reader.py` (`unique, method, where, tablespace, with_options`). The two
   must stay in step by construction — the reverse path reads back exactly
   what the forward path writes. Same suggested action as (2).

4. **D7's `# TODO` clause is dead code that was never written.** D7 asks the
   emitter for a `# TODO` comment on "preserved but unrepresentable
   features"; the emitter has no such path, and by construction cannot need
   one: `SqlModelReader._check_keys` raises `SqlModelReadError` on anything
   outside `structure-1.0`, so nothing unrepresentable ever reaches a tree the
   emitter sees. Suggested action: retire the clause from D7 (or record the
   strictness decision in the emitter docstring), rather than implement an
   unreachable branch.

5. **`print()` in the `__main__` demo blocks** of `modern/builder.py` and
   `legacy/builder.py` (pre-existing idiom, both dialects, touched by Phase 1).
   Harmless in a `python -m` demo, but it is the one `print()` in the package.
   Suggested action: a repo-wide call — keep as demo output or drop the demo
   blocks entirely.

6. **`modern/renderer.py` is still an empty placeholder** while
   `SqlBuilder._default_render_mode = "sql"` and the `renderer_sql` property
   advertise a DDL renderer. Deliberate (D8 puts DDL out of scope), but the
   builder's public surface promises something that renders nothing.
   Suggested action: say so in the `renderer_sql` docstring, or drop the
   property until the DDL slice lands.

Checked and found consistent (no action): the physical/semantic split holds
end to end — `COL_JSON_KEYS` carries no `indexed` and no `name_*`, so the
semantic plane cannot leak into the JSON (plan header rule); D3's "a foreign
key is always indexed" and `relation(indexed=False)` agree across grammar,
renderer and reader; the index-name-travels-verbatim rule of the reader
matches the emitter's hash-name docstring; every module of the reverse path
derives its ordering from the tree, never from a set.

## Final state

- `ruff check .` → **All checks passed** (whole repo, including the plan's
  contract-test copies).
- `python -m pytest tests/ -q` → **80 passed**, exit 0.
- `python -m pytest tests/ -q -m postgresql` → **4 passed** against the local
  PostgreSQL 16 (D10: the PG tests run, they do not skip).
- Convergence: cycle 1 (dead parameters, `_plane`) green, cycle 2 (markers,
  ruff glob) green, cycle 3 not needed.
- Files reviewed (24): `docs/grammar.md`, `pyproject.toml`,
  `src/genro_sql/__init__.py`, `src/genro_sql/legacy/builder.py`,
  `src/genro_sql/legacy/elements.py`, `src/genro_sql/modern/__init__.py`,
  `src/genro_sql/modern/builder.py`, `src/genro_sql/modern/elements.py`,
  `src/genro_sql/modern/emitter.py`, `src/genro_sql/modern/grammar_doc.py`,
  `src/genro_sql/modern/migration.py`, `src/genro_sql/modern/reader.py`,
  `src/genro_sql/modern/validators.py`, `tests/conftest.py`,
  `tests/test_grammar.py`, `tests/test_legacy_grammar.py`,
  `tests/test_skeleton.py`, `tests/test_wf_phase2_grammar.py`,
  `tests/test_wf_phase3_validators.py`, `tests/test_wf_phase4_renderer.py`,
  `tests/test_wf_phase5_integration.py`, `tests/test_wf_phase6_reader.py`,
  `tests/test_wf_phase7_emitter.py`, `tests/test_wf_phase8_doc.py`.
