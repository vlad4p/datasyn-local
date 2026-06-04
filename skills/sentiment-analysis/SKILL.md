---
name: sentiment-analysis
description: >-
  Perform sentiment analysis on text columns in DuckDB tables, especially news
  and articles. Use when the user asks for sentiment, tone, opinion mining,
  emotional analysis, or journalistic framing of text data.
---

# Sentiment Analysis

## Agent persona

Act as an **expert journalist**: identify tone, bias signals, emotional framing, and narrative stance — not just positive/negative scores.

## Workflow

1. Identify text column(s) in the table (`headline`, `body`, `content`, `text`)
2. Create a sentiment results table in DuckDB
3. Summarize findings with journalistic language

## Approach A: TextBlob (Python)

Add under `scripts/python/` or run inline:

```python
from textblob import TextBlob
import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts/python").resolve()))
import db
con = db.connect()
import pandas as pd

con = connect()
df = con.sql("SELECT id, body FROM articles").df()

def analyze(text):
    if not text:
        return None, 0.0, 0.0
    blob = TextBlob(str(text))
    polarity = blob.sentiment.polarity
    subjectivity = blob.sentiment.subjectivity
    if polarity > 0.1:
        label = "positive"
    elif polarity < -0.1:
        label = "negative"
    else:
        label = "neutral"
    return label, polarity, subjectivity

df[["sentiment", "polarity", "subjectivity"]] = df["body"].apply(
    lambda t: pd.Series(analyze(t))
)
con.register("sentiment_df", df)
con.sql("CREATE OR REPLACE TABLE articles_sentiment AS SELECT * FROM sentiment_df")
```

## Approach B: SQL + keyword heuristics (no extra deps)

For quick news tone scanning:

```sql
CREATE OR REPLACE TABLE articles_sentiment AS
SELECT *,
  CASE
    WHEN regexp_matches(lower(body), '(crisis|scandal|attack|fail|loss)') THEN 'negative'
    WHEN regexp_matches(lower(body), '(success|growth|win|breakthrough|hope)') THEN 'positive'
    ELSE 'neutral'
  END AS tone_heuristic
FROM articles;
```

## Journalistic summary template

```markdown
# Sentiment & Tone Analysis

## Overall tone distribution
[positive / neutral / negative counts and %]

## Dominant narratives
- [Theme 1]: predominantly [tone], example headline
- [Theme 2]: ...

## Framing signals
- Emotional language, certainty, attribution patterns

## Caveats
- Method limitations, language bias, sample size
```

## Validation

```sql
SELECT sentiment, COUNT(*) AS n, ROUND(AVG(polarity), 3) AS avg_polarity
FROM articles_sentiment GROUP BY 1 ORDER BY 2 DESC;
```
