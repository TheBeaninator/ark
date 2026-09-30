#!/bin/bash
# fetch/containers.sh — docker pull + save (gzip) every image in manifest/containers.tsv into $ARK_SOFTWARE/containers/. Load offline with: docker load -i <file>
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; CT="$ARK_SOFTWARE/containers"; mkdir -p "$CT"
tail -n +2 manifest/containers.tsv | cut -f1 | while read -r img; do f="$CT/$(echo "$img" | tr '/:' '__').tar.gz"; [ -s "$f" ] && { echo "have $img"; continue; }
  timeout 3600 docker pull -q "$img" >/dev/null 2>&1 && docker save "$img" | gzip -1 > "$f" && echo "saved $img" || { rm -f "$f"; echo "FAIL $img"; }; done
