#!/bin/sh
# SociaVault scrape + full pipeline (bronze → silver → entities → LLM classify)
# Uso:
#   ./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
#   ./scripts/sh/scrape_sociavault.sh facebook "https://facebook.com/page" --last 5
#
# Default: --last 10 (passed to platform script unless overridden in extra args)
# Extra flags: any flag accepted by the platform scrape script.
#   --skip-classify       skip LLM classification step
#   --classify-limit N    max comments to classify (default 500)

set -e

PLATFORM="$1"
ACCOUNT="$2"
shift 2 || true

if [ -z "$PLATFORM" ] || [ -z "$ACCOUNT" ]; then
  echo "Usage: $0 <facebook|twitter|instagram|tiktok> <url-or-handle> [scrape flags...]"
  echo "       --skip-classify --classify-limit N"
  echo "Example: $0 twitter myriambregman --last 10 --fetch-replies"
  exit 1
fi

SKIP_CLASSIFY=0
CLASSIFY_LIMIT=500
SCRAPE_ARGS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-classify)
      SKIP_CLASSIFY=1
      shift
      ;;
    --classify-limit)
      CLASSIFY_LIMIT="$2"
      shift 2
      ;;
    *)
      SCRAPE_ARGS="$SCRAPE_ARGS $1"
      shift
      ;;
  esac
done

echo "================================================"
echo "SociaVault pipeline"
echo "  Platform: $PLATFORM"
echo "  Account:  $ACCOUNT"
echo "  Args:     $SCRAPE_ARGS"
echo "================================================"

echo ""
echo "Releasing DB lock for ingest (re-enable MCP in Cursor after ingest to query)..."
uv run python scripts/python/db.py mcp-stop || true

case "$PLATFORM" in
  facebook)
    uv run python scripts/python/scrape_sociavault_facebook.py \
      --url "$ACCOUNT" \
      --fetch-comments \
      --ingest \
      $SCRAPE_ARGS
    ;;
  twitter)
    uv run python scripts/python/scrape_sociavault_twitter.py \
      --handle "$ACCOUNT" \
      --fetch-replies \
      --ingest \
      $SCRAPE_ARGS
    ;;
  instagram)
    uv run python scripts/python/scrape_sociavault_instagram.py \
      --handle "$ACCOUNT" \
      --fetch-comments \
      --ingest \
      $SCRAPE_ARGS
    ;;
  tiktok)
    uv run python scripts/python/scrape_sociavault_tiktok.py \
      --handle "$ACCOUNT" \
      --fetch-comments \
      --ingest \
      $SCRAPE_ARGS
    ;;
  *)
    echo "Unknown platform: $PLATFORM"
    exit 1
    ;;
esac

echo ""
echo "Ensuring classification schema..."
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_sociavault_classification.sql

echo ""
echo "Building entities..."
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_sociavault_entities.sql

if [ "$SKIP_CLASSIFY" -eq 0 ]; then
  echo ""
  echo "Classifying comments (limit=$CLASSIFY_LIMIT)..."
  uv run python scripts/python/classify_sv_comments.py \
    --platform "$PLATFORM" \
    --limit "$CLASSIFY_LIMIT"
else
  echo ""
  echo "Skipping LLM classification (--skip-classify)"
fi

echo ""
echo "Validation:"
uv run python scripts/python/db.py run-sql "
SELECT 'sv_actor' AS tabla, COUNT(*) AS total FROM silver.sv_actor
UNION ALL
SELECT platform || '_comments', COUNT(*)
FROM (
  SELECT platform FROM silver.sv_fb_comment
  UNION ALL SELECT platform FROM silver.sv_ig_comment
  UNION ALL SELECT platform FROM silver.sv_tt_comment
  UNION ALL SELECT platform FROM silver.sv_tw_reply
) t
GROUP BY platform;
"

echo ""
echo "Done. Platform=$PLATFORM account=$ACCOUNT"
