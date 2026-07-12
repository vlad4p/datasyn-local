-- Ingest Facebook scrape datasets → bronze
-- Source: data/landing/redes/data-fb/*.csv (excludes Diccionario de Datos y Aclaraciones.txt)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/redes/ingest_fb_redes.sql
-- NOTE: canonical path is scripts/sql/ — move here when scripts/sql/ is writable.

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.fb_fanpage AS
SELECT * FROM read_csv_auto(
  'data/landing/redes/data-fb/fanpage.csv',
  header = true
);

CREATE OR REPLACE TABLE bronze.fb_post AS
SELECT * FROM read_csv_auto(
  'data/landing/redes/data-fb/post.csv',
  header = true
);

CREATE OR REPLACE TABLE bronze.fb_comment AS
SELECT * FROM read_csv_auto(
  'data/landing/redes/data-fb/comment.csv',
  header = true
);

-- comment_id includes non-numeric placeholders (e.g. SIN_ID_1)
CREATE OR REPLACE TABLE bronze.fb_comments_classification AS
SELECT * FROM read_csv_auto(
  'data/landing/redes/data-fb/comments_classification.csv',
  header = true,
  types = {'comment_id': 'VARCHAR'}
);
