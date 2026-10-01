#!/bin/bash
# tools/factmap-ingest-ark.sh DIR — load a gen-ark-factmap.py directory into factmap as `cached` facts (lowest authority,
# upserted by key, so re-running after a manifest change refreshes in place). Needs FACTMAP_ROLE=ingestor.
set -u; D=${1:?dir}; export FACTMAP_ROLE=ingestor; n=0
for f in "$D"/*.md; do
  k="ark-$(basename "$f" .md)"; t=$(head -1 "$f" | sed 's/^# //'); s=$(sed -n 2p "$f" | cut -c1-200); [ -n "$s" ] || s="$t"
  factmap ingest "$k" --layer cached --title "ark: $t" --summary "$s" --body "$(cat "$f")" >/dev/null 2>&1 && n=$((n+1)) || echo "FAIL $k"
done; echo "ingested $n files from $D"
