#!/bin/bash
# fetch/hf-file.sh REPO FILE DESTDIR [dataset] — one file via aria2c (resumable, token-aware). The fallback for repos where `hf download` hangs.
set -u; id=$1; f=$2; d=$3; kind=${4:-models}; tok=$(cat ~/.cache/huggingface/token 2>/dev/null); mkdir -p "$d/$(dirname "$f")"
base="https://huggingface.co/$( [ "$kind" = dataset ] && echo datasets/ )$id/resolve/main/$f"
aria2c -q -c -x8 -s8 --file-allocation=none --auto-file-renaming=false ${tok:+--header="Authorization: Bearer $tok"} -d "$d/$(dirname "$f")" -o "$(basename "$f")" "$base"
