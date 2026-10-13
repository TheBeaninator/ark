#!/bin/bash
# tools/dataset-courier.sh — land a big HF dataset on the island's cold tier one file at a time.
# For datasets far larger than the laptop's free disk and the inbox NVMe (DECIDE a4141f7018, dad 2026-10-13:
# "pull them all if we can"): fetch ONE file to a local stage, sha256-check it against the HF LFS oid, rsync it
# straight to <host>:<dest>/<org__name>/, delete the stage copy, next file. Resumable (skips files already on the
# island with the right size). Waits for a "gate" file to contain a pattern first (e.g. the CT-6 chain end) so it never
# fights another HDD job.
# Usage: tools/dataset-courier.sh <hf_id> [--host pod-control-ll] [--dest /mnt/ark/datasets] [--gate-log PATH --gate-pattern 'chain end']
set -u
ID=$1; shift; HOST=pod-control-ll; DEST=/mnt/ark/datasets; GLOG=""; GPAT=""
while [ $# -gt 0 ]; do case $1 in --host) HOST=$2; shift 2;; --dest) DEST=$2; shift 2;; --gate-log) GLOG=$2; shift 2;; --gate-pattern) GPAT=$2; shift 2;; *) echo "bad arg $1"; exit 2;; esac; done
N=${ID//\//__}; STAGE=${ARK_STAGE:-$HOME/.cache/ark-dataset-courier}/$N; mkdir -p "$STAGE"
LOG=${ARK_STAGE:-$HOME/.cache/ark-dataset-courier}/$N.log; log(){ echo "$(date -Is) $*" | tee -a "$LOG"; }
SSH="ssh -o ConnectTimeout=8 -o BatchMode=yes"
if [ -n "$GLOG" ]; then log "waiting for '$GPAT' in $HOST:$GLOG"; until $SSH $HOST "grep -q '$GPAT' $GLOG" 2>/dev/null; do sleep 300; done; log "gate open"; fi
TOK=$(cat ~/.cache/huggingface/token 2>/dev/null); H=(); [ -n "$TOK" ] && H=(-H "Authorization: Bearer $TOK")
curl -s "${H[@]}" "https://huggingface.co/api/datasets/$ID?blobs=true" > "$STAGE/.meta.json" || { log "meta fetch failed"; exit 1; }
python3 - "$STAGE/.meta.json" > "$STAGE/.files.tsv" <<'PY'
import json,sys; d=json.load(open(sys.argv[1]))
for s in sorted(d['siblings'], key=lambda s: s['rfilename']):
    l=s.get('lfs') or {}; print(s['rfilename'], s.get('size') or l.get('size') or 0, l.get('oid') or l.get('sha256') or '-', sep='\t')
PY
TOTAL=$(awk -F'\t' '{s+=$2} END{printf "%.0f", s/1e9}' "$STAGE/.files.tsv"); log "$ID: $(wc -l < "$STAGE/.files.tsv") files, $TOTAL GB -> $HOST:$DEST/$N"
$SSH $HOST "mkdir -p $DEST/$N" || { log "cannot mkdir on $HOST"; exit 1; }
ok=0; skip=0; fail=0
while IFS=$'\t' read -r f sz sha; do
  have=$($SSH $HOST "stat -c %s '$DEST/$N/$f' 2>/dev/null" || echo 0)
  if [ "$have" = "$sz" ] && [ "$sz" != 0 ]; then skip=$((skip+1)); continue; fi
  avail=$(df --output=avail -B1 "$STAGE" | tail -1); [ "$avail" -gt $((sz + 5000000000)) ] || { log "SKIP $f: laptop has $((avail/1000000000)) GB free, need $((sz/1000000000))"; fail=$((fail+1)); continue; }
  log "fetch $f ($((sz/1000000000)) GB)"
  if ! HF_HUB_ENABLE_HF_TRANSFER=0 hf download "$ID" --repo-type dataset --include "$f" --local-dir "$STAGE" >/dev/null 2>"$STAGE/.err"; then log "FETCH-FAIL $f: $(tail -1 "$STAGE/.err" | cut -c1-120)"; fail=$((fail+1)); rm -rf "$STAGE/$f" "$STAGE/.cache"; continue; fi
  if [ "$sha" != "-" ]; then got=$(sha256sum "$STAGE/$f" | cut -d' ' -f1); [ "$got" = "$sha" ] || { log "SHA-FAIL $f"; fail=$((fail+1)); rm -f "$STAGE/$f"; continue; }; fi
  if rsync -a --partial --inplace -e "$SSH" "$STAGE/$f" "$HOST:$DEST/$N/$f"; then log "LANDED $f (sha ok)"; ok=$((ok+1)); rm -f "$STAGE/$f"; rm -rf "$STAGE/.cache"; else log "PUSH-FAIL $f (stage kept)"; fail=$((fail+1)); fi
done < "$STAGE/.files.tsv"
rsync -a -e "$SSH" "$STAGE/.files.tsv" "$HOST:$DEST/$N/.files.tsv" 2>/dev/null
log "DONE $ID: landed=$ok skipped=$skip failed=$fail"
[ "$fail" = 0 ] && $SSH $HOST "printf '%s\t%s\tdataset-courier\n' '$ID' \"\$(date -u +%FT%TZ)\" >> /data/ark-inbox/ARK-FETCHED.tsv"
