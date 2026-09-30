#!/bin/bash
# fetch/reference.sh — manifest/reference.tsv: zim (latest match of a pattern in a Kiwix directory), zim-set (brace list of tools), url (with {REL} = latest Ensembl release).
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; A="aria2c -c -x8 -s8 --file-allocation=none --auto-file-renaming=false --console-log-level=warn --summary-interval=0 --max-tries=20 --retry-wait=30"
UA="-sL -A Mozilla/5.0"; Z="$ARK_DATA/reference/zim"; G="$ARK_DATA/reference/genome"; mkdir -p "$Z/devdocs" "$G"
REL=$(curl $UA https://ftp.ensembl.org/pub/ | grep -oE "release-[0-9]+" | sort -t- -k2 -n | tail -1 | tr -dc 0-9)
tail -n +2 manifest/reference.tsv | while IFS=$'\t' read -r kind src pat note; do case $kind in
  zim) f=$(curl $UA "$src" | grep -oE "${pat//\*/[0-9-]+}" | sort -u | tail -1); [ -n "$f" ] && { $A -d "$Z" "$src$f" >/dev/null 2>&1 && echo "OK $f" || echo "FAIL $f"; } || echo "NO-MATCH $pat";;
  zim-set) all=$(curl $UA "$src" | grep -oE "devdocs_en_[a-z0-9_.-]+\.zim" | sort -u); for k in $(echo "$pat" | grep -oE "\{[^}]+\}" | tr -d '{}' | tr ',' ' '); do f=$(echo "$all" | grep -E "^devdocs_en_${k}_[0-9-]+\.zim$" | sort | tail -1); [ -n "$f" ] && { $A -d "$Z/devdocs" "$src$f" >/dev/null 2>&1 && echo "OK $f" || echo "FAIL $f"; } || echo "NO-MATCH $k"; done;;
  url) u=${src//\{REL\}/$REL}; d="$ARK_DATA/reference/$pat"; mkdir -p "$d"; $A -d "$d" "$u" >/dev/null 2>&1 && echo "OK $(basename "$u")" || echo "FAIL $u"; [ "${u##*.}" = gz ] && { $A -d "$d" "$u.tbi" >/dev/null 2>&1 || true; };;
esac; done
