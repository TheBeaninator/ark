#!/bin/bash
. "$(dirname "$0")/../ark.env"
# catalog2.sh — size/mtime/path of every file >= 1 MB on every store (post-reorg roots) + per-dir summary. Output /mnt/nv2/CATALOG-<date>.tsv
OUT=/mnt/nv2/CATALOG-$(date +%F).tsv; TMP=$OUT.tmp; : > $TMP
for root in /mnt/nv1 /mnt/nv2 /mnt/nv3 /mnt/nv4 /mnt/nv5 /mnt/nv6 /mnt/scratch1t /media/dad/flatbed /media/dad/Train /media/dad/SlowStorage /home/dad/.cache/huggingface/hub; do
  [ -d "$root" ] && find "$root" -xdev -type f -size +1M -not -path "*/software/src/*" -not -path "*/software/pnpm-store/*" -not -path "*/software/bun-cache/*" -not -path "*/software/gomodcache/*" -not -path "*/software/npm-cache/*" -not -path "*/node_modules/*" -not -path "*/ubuntu-mirror/*" -not -path "*/lost+found/*" -printf "%s\t%TY-%Tm-%Td\t%p\n" 2>/dev/null >> $TMP
done
sort -t$'\t' -k3 $TMP > $OUT; rm -f $TMP
awk -F"\t" '{n=split($3,a,"/"); d=a[2]"/"a[3]"/"a[4]; if(a[2]=="mnt"||a[2]=="media") d=d"/"a[5]; s[d]+=$1; c[d]++} END {for(k in s) printf "%.1f\t%d\t%s\n", s[k]/1e9, c[k], k}' $OUT | sort -rn > ${OUT%.tsv}-dirs.tsv
ln -sfn $(basename $OUT) /mnt/nv2/CATALOG-latest.tsv; ln -sfn $(basename ${OUT%.tsv})-dirs.tsv /mnt/nv2/CATALOG-latest-dirs.tsv
echo "CATALOG-DONE $(wc -l < $OUT) files $(awk -F"\t" '{s+=$1} END {printf "%.2f TB", s/1e12}' $OUT)"
