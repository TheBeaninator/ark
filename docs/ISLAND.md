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

## Island tools are repo-owned (AI-4 19f7dca19b)

**`<inbox>/tools/` (ark-index.py, ark-path, ...) is repo-owned.** The ark repo is the source of truth and
inbox-sync.py copies `tools/` into the inbox on every island sync. Island copies are downstream artefacts —
never edit the repo copy by editing only the island copy and expecting the change to survive.

### What inbox-sync now does (ark side, this patch)

inbox-sync's island() step 1 no longer blindly rsyncs over the inbox tools. Before the rsync it fetches the island copies over ssh and calls
`island_guard.guard_island_copy()` for each of `tools/ark-index.py` and `tools/ark-path`:

- Island copy missing or byte-identical → plain sync, as before.
- Island copy **newer** and differing → the island copy is **left untouched** (its rsync is skipped for that
  run), the diffstat is printed, and a request line is appended to `<inbox>/REQUESTS.tsv`:
  `<date>\tUPSTREAM\ttools/<name>\tisland copy newer and differs; kept, ...\tcard=19f7dca19b` (same tab fields as the island's own rows; logged once per path). REQUESTS.tsv is the
  island→ark request channel ark-index already surfaces.
- Island copy older-or-equal and differing → sync (the repo side is the fresh one).
- **`--force-tools`** bypasses the guard entirely: the repo deliberately overwrites the island copies
  (use this after you have ported or rejected the island change, so a stale island copy stops re-flagging).

### The island-side rule

Do not hot-patch `<inbox>/tools/*` and leave it there. An island change is:

1. a patch file in `/data/pod/plans/<card>/` (e.g. `ark-index.patch` or the full new file), and
2. a comment on the card saying **`UPSTREAM ark: <path>`** (e.g. `UPSTREAM ark: /data/pod/plans/ab12cd34ef/ark-index.patch`).

AI-0/pod-ark-watch or the PM carries that patch into the ark repo **within a day**. Until it lands, the
guard keeps the island copy alive and re-logs the REQUESTS.tsv line instead of clobbering it; after it
lands, the next sync (or `--force-tools`) converges the island copy and the flag clears.

### Why

The old behaviour silently destroyed island-side fixes (edited ark-index.py/ark-path reverted at the next
sync, with no trace). The guard makes the divergence visible (diffstat + REQUESTS.tsv) and lossless;
`--force-tools` keeps a deliberate, human-driven override on the repo side.

Tests: `python3 tools/test_island_guard.py` (guard rules) and `ARK_INDEX_PATH=tools/ark-index.py python3 tools/test_publish_stable.py` (publish_stable / view prune, card 71d498e061).
