#!/usr/bin/env python3
"""island_guard.py — stop inbox-sync.py from silently clobbering newer island copies of repo tools.

Why: inbox-sync.py (ark repo) runs on the ark machine; its island() step 1 rsyncs the repo's tools/ into
<inbox>/tools EVERY run. When someone on the island edits <inbox>/tools/ark-index.py or <inbox>/tools/ark-path
(that is how island-side fixes are made), the next sync wipes the change with no trace. This module makes the
sync a one-way door with a memory: a NEWER differing island copy is kept untouched and the change is logged to
<inbox>/REQUESTS.tsv so the PM/AI-0 (pod-ark-watch) carries it back into the ark repo.

Stdlib only, python3. Drop this file into the ark repo as tools/island_guard.py.

=== INTEGRATION: inbox-sync.py, island() step 1 (EXACT) =====================
Import at the top of inbox-sync.py:

    import island_guard            # tools/island_guard.py, same dir as inbox-sync.py

The argparse block of inbox-sync.py gains ONE new CLI flag (place it with the other flags, e.g. after
--force-tools if one exists already):

    ap.add_argument('--force-tools', action='store_true',
                    help="overwrite island copies of tools/ even when the island copy is newer (deliberate clobber)")

Replace the bare rsync of tools in island() step 1. The current code is the equivalent of
"rsync <repo>/tools/ <inbox>/tools/" every run. The guarded version, BEFORE the rsync, for EACH of
(tools/ark-index.py, tools/ark-path):

    GUARDED_TOOLS = ('tools/ark-index.py', 'tools/ark-path')
    keep = set()
    for rel in GUARDED_TOOLS:                                            # step 1, before the rsync
        verdict, request, diffstat = island_guard.guard_island_copy(
            os.path.join(REPO, rel), INBOX + '/' + rel, rel, force=args.force_tools)
        if verdict == 'keep':
            print(diffstat)                                              # show what the island changed
            island_guard.append_request(os.path.join(INBOX, 'REQUESTS.tsv'), request)
            print("island_guard: kept island copy of %s; logged to %s/REQUESTS.tsv" % (rel, INBOX))
            keep.add(rel)                                                # SKIP this file's rsync for this run
    # then rsync tools/ but EXCLUDE every rel kept above, e.g. build the command as:
    #   cmd = ['rsync', '-a'] + ['--exclude=' + r for r in sorted(keep)] + [REPO + '/tools/', INBOX + '/tools/']
    # (with --force-tools the guard never returns "keep", so nothing is excluded and the rsync is the old one).

Rules implemented by guard_island_copy() (see function docstring): island file missing or byte-identical ->
sync; island NEWER and differing -> keep + REQUESTS.tsv line (unless --force-tools); island older/equal and
differing -> sync. --force-tools bypasses the guard entirely (deliberate repo-side overwrite).
=============================================================================
"""
import datetime
import difflib
import os

REQUESTS_HEADER = '# REQUESTS.tsv island->ark requests, one per line'
DIFF_LINES_SHOWN = 20


def diffstat(repo_path, island_path, relname=None):
    """One-line summary '+N -M in <relname>' + up to 20 unified-diff lines (repo -> island direction, so '+'
    lines are what the island added). Binary files (a NUL byte in either side) -> 'binary differs'."""
    if relname is None:
        relname = os.path.basename(island_path)
    try:
        with open(repo_path, 'rb') as f:
            a = f.read()
        with open(island_path, 'rb') as f:
            b = f.read()
    except OSError as e:
        return 'unreadable: %s' % e
    if b'\0' in a or b'\0' in b:
        return 'binary differs'
    al = a.decode('utf-8', 'replace').splitlines()
    bl = b.decode('utf-8', 'replace').splitlines()
    diff = list(difflib.unified_diff(al, bl, fromfile='repo/' + relname, tofile='island/' + relname, lineterm=''))
    plus = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
    minus = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
    head = '+%d -%d in %s' % (plus, minus, relname)
    body = [l for l in diff if not l.startswith(('---', '+++'))]
    return '\n'.join([head] + body[:DIFF_LINES_SHOWN])


def guard_island_copy(repo_path, island_path, relname, force=False):
    """Decide whether the repo copy may be rsynced over the island copy.

    Returns (verdict, requests_line_or_None, diffstat_str):
      ('sync', None, '')      island copy missing or byte-identical — plain rsync, nothing to say
      ('keep', line, diff)    island copy is NEWER and differs and not force — do NOT overwrite; log `line`
                              (format 'UPSTREAM <relname>: island copy differs, port it') to <inbox>/REQUESTS.tsv
                              and skip this file's rsync for this run
      ('sync', None, diff)    island copy older-or-equal and differs, or force=True (deliberate --force-tools
                              overwrite); `diff` is the diffstat for the log

    'repo file unreadable/missing' is treated as a plain sync — there is nothing to compare and rsync of a
    nonexistent source is a no-op anyway."""
    if not os.path.exists(island_path):
        return ('sync', None, '')
    try:
        with open(repo_path, 'rb') as f:
            a = f.read()
        with open(island_path, 'rb') as f:
            b = f.read()
    except OSError:
        return ('sync', None, '')
    if a == b:
        return ('sync', None, '')
    ds = diffstat(repo_path, island_path, relname)
    if not force:
        try:
            if os.stat(island_path).st_mtime > os.stat(repo_path).st_mtime:
                return ('keep', 'UPSTREAM %s: island copy differs, port it' % relname, ds)
        except OSError:
            pass
    return ('sync', None, ds)


def append_request(requests_tsv_path, line):
    """Append one request line to <inbox>/REQUESTS.tsv, prefixing it with an ISO-date field:
    '<YYYY-MM-DD>\\t<line>'. Creates the file with the header comment when missing. Returns the appended line."""
    entry = '%s\t%s' % (datetime.date.today().isoformat(), line)
    if not os.path.isfile(requests_tsv_path):
        with open(requests_tsv_path, 'a') as f:
            f.write(REQUESTS_HEADER + '\n')
    with open(requests_tsv_path, 'a') as f:
        f.write(entry + '\n')
    return entry


def main(argv):
    """CLI for manual checks / shell callers: `island_guard.py check <repo> <island> <relname> [--force]`.
    Prints the diffstat, exits 0 = sync, 10 = keep."""
    if len(argv) >= 2 and argv[1] == 'check' and len(argv) >= 5:
        verdict, request, ds = guard_island_copy(argv[2], argv[3], argv[4], force='--force' in argv[5:])
        if ds:
            print(ds)
        if verdict == 'keep':
            print('KEEP %s' % request)
            return 10
        print('SYNC')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
