-- Ingest Twitter/X scrap dump → bronze (raw, no transforms)
-- Source: data/landing/redes/data-tw/*.csv (excludes Diccionario de Datos y Aclaraciones.txt)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_twitter.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.tw_users AS
SELECT * FROM read_csv_auto(
    'data/landing/redes/data-tw/users.csv',
    header = true
);

CREATE OR REPLACE TABLE bronze.tw_tweets AS
SELECT * FROM read_csv_auto(
    'data/landing/redes/data-tw/tweets.csv',
    header = true
);

CREATE OR REPLACE TABLE bronze.tw_tweets_replies AS
SELECT * FROM read_csv_auto(
    'data/landing/redes/data-tw/tweets_replies.csv',
    header = true
);

CREATE OR REPLACE TABLE bronze.tw_comments_classification AS
SELECT * FROM read_csv_auto(
    'data/landing/redes/data-tw/comments_classification.csv',
    header = true
);
