# POC-001: IRONMAN Relational Data Simulator (Snowflake)

## Run order
1. `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in your Snowflake trial account details
   (account identifier looks like `orgname-accountname`)
3. `python seed.py --dry-run`  (optional: offline test, writes CSVs to `seed_output/`)
4. `python seed.py`            (creates warehouse/database/schema/tables and loads data)
5. `python validate.py`        (integration checks + CSV/JSON export to `export/`)

## Files
- `schema.sql` — warehouse, database, schema, 6 tables with PK/FK
- `seed.py` — deterministic generator + Snowflake loader (repeatable: fixed seed)
- `validate.py` — acceptance-criteria and integrity checks, fingerprints, export
- `data_dictionary.md` — table/column documentation

## Acceptance criteria coverage
- 500+ athletes (520), 30+ events (34): checked in `validate.py`
- Valid foreign keys: orphan checks on every FK
- Repeatable seed: rerun `seed.py`, then `validate.py`; fingerprints show MATCH
