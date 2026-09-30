#!/bin/bash
. "$(dirname "$0")/../ark.env"
# manifest2.sh — sha256+size manifest of the nv drives, incremental (hashes only paths not already listed). Output /mnt/nv2/MANIFEST.tsv
OUT=/mnt/nv2/MANIFEST.tsv; touch $OUT; TMP=$(mktemp)
for root in /mnt/nv1 /mnt/nv2 /mnt/nv3 /mnt/nv4 /mnt/nv5 /mnt/nv6; do
  find $root -xdev -type f -size +1M -not -path "*/software/*" -not -path "*/ubuntu-mirror/*" -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/site-packages/*" -not -path "*/node_modules/*" -not -path "*/lost+found/*" -not -path "*/.cache/*" -not -name "MANIFEST.tsv*" -printf "%p\n"
done | sort > $TMP.all
cut -f3 $OUT | sort > $TMP.have; comm -23 $TMP.all $TMP.have > $TMP.new
echo "manifest: $(wc -l < $TMP.new) new files to hash ($(xargs -d '\n' -a $TMP.new stat -c %s 2>/dev/null | awk '{s+=$1} END{printf "%.0f GB", s/1e9}'))"
while read -r f; do h=$(nice -n 19 ionice -c3 sha256sum "$f" | cut -d" " -f1); s=$(stat -c %s "$f"); printf "%s\t%s\t%s\n" "$h" "$s" "$f" >> $OUT; done < $TMP.new
rm -f $TMP $TMP.all $TMP.have $TMP.new; echo "MANIFEST-DONE $(wc -l < $OUT) files"
