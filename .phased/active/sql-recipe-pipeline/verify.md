# Verification checks left to the human

## Phase 7

- Verify: now — open one emitted recipe and judge its readability as code a
  person would maintain. Regenerate one without running the suite:
  ```
  python -c "from tests.test_wf_phase7_emitter import HUMAN_FIXTURE, _builder_from
  from genro_sql import SqlPythonEmitter
  print(SqlPythonEmitter(_builder_from(HUMAN_FIXTURE)[0]).emit())"
  ```
  Deferred by Phase 7 to Phase 9; nothing automatic can judge it.

## Phase 8

- Verify: now — read `docs/grammar.md` top to bottom: does it read as a
  reference a developer would consult? The anti-drift test only proves it
  matches the code, never that it is worth reading.
