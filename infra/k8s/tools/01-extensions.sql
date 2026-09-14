-- Runs once, when Postgres initialises an empty data directory.
-- The API's "did you mean?" artist suggestions call similarity(), which comes
-- from pg_trgm (see suggest_artist_aggregates in lyricstats/db.py).
CREATE EXTENSION IF NOT EXISTS pg_trgm;
