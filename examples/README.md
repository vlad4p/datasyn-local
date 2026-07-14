# Examples

Sample datasets you can copy into `data/landing/` and ingest with the AI assistant.

## `data_example.csv`

Fictional tweet-style rows (`tweet_id`, `username`, `created_at`, `text`, `likes`, `retweets`) — no real accounts or PII. Use it for the README quickstart:

1. **Copy to landing** — `cp examples/data_example.csv data/landing/`
2. **Ingest** — ask the assistant (skill `ingest-data`) to load it as `bronze.tweets_example`
3. **Analyze** — ask for counts, `DESCRIBE`, sample rows, top authors by likes, tweets per day

See the guides in [README.md](../README.md) (Spanish) or [README.en.md](../README.en.md) (English): *Where to put a CSV*, *How to ingest a CSV*, and *Import another DuckDB*.
