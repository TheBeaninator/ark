#!/bin/bash
# verify/apt-coverage.sh [list-file] — check that every package named in a list is in the flat apt mirror AND its .deb is on disk.
# Default list: verify/apt-netboot.txt (the PXE / node-provisioning kit). Exit 1 on any miss.
set -u; . "$(dirname "$0")/../ark.env" 2>/dev/null; cd "$(dirname "$0")/.."
M=${ARK_APT:-/mnt/nv4/ubuntu-mirror}/archive.ubuntu.com/ubuntu; L=${1:-verify/apt-netboot.txt}; rc=0
[ -f "$M/Packages" ] || { echo "no index at $M/Packages"; exit 2; }
grep -vE '^\s*(#|$)' "$L" | while read -r p; do
  fn=$(awk -v p="$p" '$1=="Package:"&&$2==p{f=1} f&&$1=="Filename:"{print $2; exit}' "$M/Packages")
  if [ -z "$fn" ]; then echo "MISS  $p"; elif [ ! -f "$M/$fn" ]; then echo "NODEB $p ($fn)"; else echo "ok    $p"; fi
done | tee /dev/stderr | grep -qE '^(MISS|NODEB)' && rc=1
exit $rc
