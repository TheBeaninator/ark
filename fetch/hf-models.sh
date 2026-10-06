#!/bin/bash
# fetch/hf-models.sh — manifest/models.tsv rows: kind raw|gguf -> $ARK_MODELS/<Org__Repo>/<kind>/ ; kind hf-asset|comfy -> $ARK_HF_ASSETS/<org>/<repo>/
# include column = space-separated glob patterns (empty = whole repo). Needs `hf` (huggingface_hub CLI) with a token for gated repos.
# Known gotcha: `hf download` can hang on repos with thousands of files; for those use fetch/hf-file.sh (aria2c per file).
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."
{ tail -n +2 manifest/models.tsv; [ -f manifest-private/models.tsv ] && tail -n +2 manifest-private/models.tsv; } | tr -d '\r' | tr '\t' '\037' | while IFS=$'\037' read -r id kind inc note; do   # \037, not tab: bash collapses empty tab fields
  [ -n "${ARK_ONLY:-}" ] && ! grep -qxF "$id" "$ARK_ONLY" && continue
  case $kind in raw|gguf) d="$ARK_MODELS/${id//\//__}/$kind";; *) d="$ARK_HF_ASSETS/$id";; esac; mkdir -p "$d"
  args=(); for p in $inc; do args+=(--include "$p"); done
  timeout 14400 hf download "$id" --local-dir "$d" "${args[@]}" --exclude "tf_*" --exclude "flax_*" --exclude "*.h5" --exclude "*.msgpack" >/dev/null 2>"$d.err"; rc=$?
  n=$(find "$d" -type f ! -name '.*' | wc -l); [ $rc -eq 0 ] && [ "$n" -gt 0 ] && echo "OK $id ($n files)" || echo "FAIL $id rc=$rc: $(tail -1 "$d.err" | cut -c1-120)"; rm -f "$d.err"
done
