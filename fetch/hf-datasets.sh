#!/bin/bash
# fetch/hf-datasets.sh — manifest/datasets.tsv -> $ARK_DATA/datasets/<org__name>/ (parquet as published).
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; mkdir -p "$ARK_DATA/datasets"
{ tail -n +2 manifest/datasets.tsv; [ -f manifest-private/datasets.tsv ] && tail -n +2 manifest-private/datasets.tsv; } | tr -d '\r' | tr '\t' '\037' | while IFS=$'\037' read -r id inc note; do d="$ARK_DATA/datasets/${id//\//__}"; mkdir -p "$d"; args=(); [ -n "$inc" ] && args=(--include "$inc")
  timeout 14400 hf download "$id" --repo-type dataset --local-dir "$d" "${args[@]}" >/dev/null 2>"$d.err" && echo "OK $id" || echo "FAIL $id: $(tail -1 "$d.err" | cut -c1-120)"; rm -f "$d.err"; done
