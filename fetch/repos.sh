#!/bin/bash
# fetch/repos.sh — latest-only shallow clones of every row in manifest/repos.tsv into $ARK_SOFTWARE/src/<host>__<owner>__<repo>.
# Re-run to refresh (shallow fetch + reset). Usage: fetch/repos.sh [category-filter-regex]
# A row's url may end in #<branch> to track a non-default branch, or #<full 40-hex commit> to pin one commit (for builds that break on
# newer HEADs); it clones into <host>__<owner>__<repo>#<ref with / as __>. A pinned commit is fetched once and never moves.
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; mkdir -p "$ARK_SOFTWARE/src"; F=${1:-.}
{ tail -n +2 manifest/repos.tsv; [ -f manifest-private/repos.tsv ] && tail -n +2 manifest-private/repos.tsv; } | awk -F'\t' -v f="$F" '$1 ~ f {print $2}' | while read -r u; do
  [ -n "${ARK_ONLY:-}" ] && ! grep -qxF "$u" "$ARK_ONLY" && continue   # ARK_ONLY = file of keys (url / hf_id / source) to restrict a run to
  ark_skip "$u" && continue   # ARK_EXCLUDE_TAGS: rows tagged in manifest/tags.tsv
  n=$(echo "$u" | sed -E 's#https?://##; s#/#__#g; s#\.git$##'); d="$ARK_SOFTWARE/src/$n"
  r=${u%%#*}; b=; [ "$r" != "$u" ] && b=${u#*#}
  if [[ $b =~ ^[0-9a-f]{40}$ ]]; then
    if [ "$(git -C "$d" rev-parse HEAD 2>/dev/null)" = "$b" ]; then echo "PINNED $u"
    else rm -rf "$d"; mkdir -p "$d" && (cd "$d" && git init -q && git remote add origin "$r" && timeout 1200 git fetch -q --depth 1 origin "$b" </dev/null && git checkout -q FETCH_HEAD && git submodule update --init --depth 1 --recursive >/dev/null 2>&1) && echo "CLONED $u" || { rm -rf "$d"; echo "CLONE-FAIL $u"; }; fi
    continue
  fi
  if [ -d "$d/.git" ]; then (cd "$d" && git fetch --depth 1 origin ${b:+"$b"} </dev/null >/dev/null 2>&1 && git reset -q --hard FETCH_HEAD && git submodule update --init --depth 1 --recursive >/dev/null 2>&1) && echo "UPDATED $u" || echo "UPDATE-FAIL $u"
  else timeout 1200 git clone --quiet --depth 1 --single-branch --recurse-submodules --shallow-submodules ${b:+-b "$b"} "$r" "$d" </dev/null >/dev/null 2>&1 && echo "CLONED $u" || { rm -rf "$d"; echo "CLONE-FAIL $u"; }; fi
done
