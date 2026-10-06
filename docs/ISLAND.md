# Keeping an island in step (inbox-sync, ark-index)

An *island* is an air-gapped install of the ark: read-only mirror drives plus a writable inbox on a control node
(the reference build: pod-control, `/data/ark-inbox`, reached only from a laptop over link-local ssh).

## The loop: commit a row, it arrives

```
laptop (internet + ssh)                                  island (no internet)
  git commit manifest/...  ──post-commit hook──▶ tools/inbox-sync.py
                              (or the 2 h timer)     │ 1. ship tools/ark-index.py + ark-path to <inbox>/tools
                                                     │ 2. ark-index --want: which rows' files exist ANYWHERE ──▶ every mounted fs + inbox
                                                     │ 3. fetch only the absent rows (fetch/*.sh, ARK_ONLY) into ~/.cache/ark-inbox-stage
                                                     │ 4. rsync into <inbox>, ledger ARK-FETCHED.tsv, SYNC-STATUS.json ──▶ /data/ark-inbox
                                                     ▼
                                              ark-index.timer (island, boot + every 15 min): rebuild /data/ark view + ARK-INDEX.tsv
```

Install once on the hub: `tools/install-inbox-sync.sh` (user timer + post-commit hook). Overrides go in
`~/.config/ark-inbox-sync.env` (`ARK_ISLAND_HOST`, `ARK_INBOX`, `ARK_SYNC_MAX_GB`). Look first with `tools/inbox-sync.py --dry-run`.

**Presence is by content, not by location.** A model row is present when every file its include globs select exists
somewhere on the island with the same name and size, or the same size and extension (a renamed copy). Whole-repo rows
count once any payload file or their directory is there (mirrors keep safetensors and skip duplicate .bin files); same
names at a different size are *stale* (reported, not refetched). URL rows match by Content-Length, so a PDF renamed into a
library still counts. Repos match by checkout directory (`<host>__<owner>__<repo>[#ref]`). Hand-staged things the
matcher can't see go in `<inbox>/ARK-FETCHED.tsv` (`key<TAB>utc<TAB>note`).

**Not fetched automatically:** models over `ARK_SYNC_MAX_GB` (default 40) or of unknown size (gated) are listed as
TOO-BIG in `SYNC-STATUS.json`; fetch those on a big-disk host and copy them in. `comfy` rows live in comfy trees and
are skipped. Island agents ask for things by appending lines to `<inbox>/REQUESTS.tsv` or
`/data/pod/plans/*/fetch-requests.txt`; requests are reported, and fetched once a manifest row exists.

## Drives can move: use /data/ark, never /mnt/nvN

`ark-index` finds the ark layout on whatever is mounted (`/mnt`, `/media`, `/srv`) and builds `/data/ark`, a merged
symlink tree: `/mnt/<any drive>/X/Y` is `/data/ark/X/Y`, whichever drive holds it today, with the inbox merged under
the same names (`inbox/src` → `software/src`, `inbox/wheels` → `software/wheels`). Swapping ports, moving a drive to
another host, relabelling it, or moving content between drives needs no edits: the next index (boot, or within 15
min) re-points the view. A name found on two drives goes to a drive not marked `cold` in `<inbox>/ARK-TIERS.tsv` (label<TAB>cold, for an SMR cold tier) first, then by label, and is listed in `ARK-CONFLICTS.tsv`.

```
ark-path software/src/github.com__neuhaus__gufo     # real path now
ark-path /mnt/nv3/llm/qwen3-asr-1.7b                # an old drive path, translated (finds it on whichever drive)
ark-path openWakeWord                               # search the index
pip install --no-index --find-links /data/ark/software/wheels ...
```

Mounting by `LABEL=` in fstab keeps mountpoints stable across ports; the view keeps paths stable across everything else.
