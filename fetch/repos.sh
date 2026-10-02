#!/bin/bash
# fetch/repos.sh — latest-only shallow clones of every row in manifest/repos.tsv into $ARK_SOFTWARE/src/<host>__<owner>__<repo>.
# Re-run to refresh (shallow fetch + reset). Usage: fetch/repos.sh [category-filter-regex]
# A row's url may end in #<branch> to track a non-default branch; it clones into <host>__<owner>__<repo>#<branch with / as __>.
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; mkdir -p "$ARK_SOFTWARE/src"; F=${1:-.}
{ tail -n +2 manifest/repos.tsv; [ -f manifest-private/repos.tsv ] && tail -n +2 manifest-private/repos.tsv; } | awk -F'\t' -v f="$F" '$1 ~ f {print $2}' | while read -r u; do
  n=$(echo "$u" | sed -E 's#https?://##; s#/#__#g; s#\.git$##'); d="$ARK_SOFTWARE/src/$n"
  r=${u%%#*}; b=; [ "$r" != "$u" ] && b=${u#*#}
  if [ -d "$d/.git" ]; then (cd "$d" && git fetch --depth 1 origin ${b:+"$b"} </dev/null >/dev/null 2>&1 && git reset -q --hard FETCH_HEAD && git submodule update --init --depth 1 --recursive >/dev/null 2>&1) && echo "UPDATED $u" || echo "UPDATE-FAIL $u"
  else timeout 1200 git clone --quiet --depth 1 --single-branch --recurse-submodules --shallow-submodules ${b:+-b "$b"} "$r" "$d" </dev/null >/dev/null 2>&1 && echo "CLONED $u" || { rm -rf "$d"; echo "CLONE-FAIL $u"; }; fi
done
