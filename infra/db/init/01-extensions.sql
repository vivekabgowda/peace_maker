-- Enable required Postgres extensions on database creation.
-- (Alembic migration 0001 also enables these idempotently; doing it here
--  guarantees they exist before the app first connects.)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS timescaledb;
