#!/usr/bin/env python3
"""tools/ark-index.py — run ON the island. Finds the ark on whatever is mounted, by content, and publishes where things are.

Every mounted data filesystem (/mnt, /media, /srv) plus the inbox is scanned; drive names, labels and ports don't matter.
Outputs (all rebuilt every run, so physically moving, relabelling or reshuffling drives needs no edits anywhere):
  <view> (default /data/ark)  a merged symlink tree: <view>/<top>/<child> -> <drive>/<top>/<child> for every drive, and one
                              level deeper under software/ (software/src/<repo>, software/wheels/<whl>, ...). So a path
                              written as /mnt/nvN/X/Y works as <view>/X/Y no matter which drive holds it today. The inbox
                              joins the same names (inbox/src -> software/src, inbox/wheels -> software/wheels, inbox/models
                              -> models, ...). Drives win over the inbox; a name on two drives goes to non-cold drives first (ARK-TIERS.tsv),
                              then by label, and is listed in <inbox>/ARK-CONFLICTS.tsv. The swap is atomic (<view> is a symlink to a fresh tree).
  <inbox>/ARK-INDEX.tsv       kind, key, path for repos, models, hf-assets, wheels, binaries (tools/ark-path reads it)
  <inbox>/ARK-DRIVES.tsv      label, uuid, mountpoint, device of every filesystem seen
With --want (used by tools/inbox-sync.py over ssh), stdin carries {names, sizes, exts, list_exts} and stdout gets a JSON
report of which of those files exist anywhere (name+size, size+extension, size) plus the index, ledger and agent requests.
Usage: ark-index.py [--inbox /data/ark-inbox] [--view /data/ark] [--want] [--no-view]
"""
import argparse, json, os, re, shutil, sys, time

JUNK = {'lost+found', '.Trash-1000', 'System Volume Information', '$RECYCLE.BIN'}
PRUNE = {'.git', 'src', 'ubuntu-mirror', 'cargo-home', 'npm-cache', 'pnpm-store', 'gomodcache', 'bun-cache', 'debs', 'rocm',
         'node_modules', '__pycache__', 'containers', '.cache'} | JUNK
INBOX_AS = {'src': 'software/src', 'wheels': 'software/wheels', 'binaries': 'software/binaries', 'hf-assets': 'hf-assets',
            'models': 'models', 'reference': 'reference', 'data': 'data'}

def ls(d):
    try: return sorted(os.listdir(d))
    except OSError: return []

def tiers(inbox):
    """<inbox>/ARK-TIERS.tsv: label<TAB>cold — slow bulk drives (an SMR HDD) that lose ties in the view and are walked
    file-by-file at most once a day. Labels travel with the physical drive, so this survives port and host moves.
    (Kernel 'rotational' flags can't be used: USB NVMe enclosures report themselves as rotational.)"""
    try: return {l.split('\t')[0]: l.split('\t')[1].strip() for l in open(os.path.join(inbox, 'ARK-TIERS.tsv')) if '\t' in l and not l.startswith('#')}
    except OSError: return {}

def mounts(inbox):
    T = tiers(inbox)
    out = []
    for l in open('/proc/mounts'):
        dev, mp, fs = l.split()[:3]
        mp = mp.replace('\\040', ' ')
        if fs in ('ext4', 'xfs', 'btrfs', 'ntfs', 'ntfs3', 'fuseblk', 'exfat', 'vfat', 'f2fs') and mp.startswith(('/mnt/', '/media/', '/srv/')):
            out.append((dev, mp))
    by = {k: {os.path.realpath(os.path.join('/dev/disk/by-' + k, n)): n for n in ls('/dev/disk/by-' + k)} for k in ('label', 'uuid')}
    drives = sorted([(by['label'].get(os.path.realpath(d), ''), by['uuid'].get(os.path.realpath(d), ''), mp, d) for d, mp in out],
                    key=lambda x: (T.get(x[0]) == 'cold', x[0] or '~', x[2]))
    if os.path.isdir(inbox): drives.append(('', '', inbox, 'inbox'))
    return drives

LEAFY = {'src', 'models', 'llm', 'hf', 'wheels'}   # children of these are whole items: never merged file-by-file

def build_view(drives, inbox, view):
    """Merge every drive (then the inbox) into one tree. A name present on one source is a symlink; a directory present on
    several is merged one level down until it is an item (a repo, a model, a depth-3 path); then the first source wins."""
    conflicts, n = [], [0]
    roots = []
    for lab, uuid, mp, dev in drives:
        if mp == inbox: roots.append({as_: os.path.join(mp, top) for top, as_ in INBOX_AS.items() if os.path.isdir(os.path.join(mp, top))})
        else: roots.append({top: os.path.join(mp, top) for top in ls(mp) if top not in JUNK and os.path.isdir(os.path.join(mp, top))})   # isdir follows llm -> models
    def merge(dst, rel, cands):   # cands: [(name-path-in-view, real path)] in priority order
        cands = [c for i, c in enumerate(cands) if os.path.realpath(c) not in {os.path.realpath(x) for x in cands[:i]}]
        depth = rel.count('/') + 1 if rel else 0
        leaf = depth >= 3 or os.path.basename(os.path.dirname(rel)) in LEAFY or os.path.isdir(os.path.join(cands[0], '.git'))
        if rel and (len(cands) == 1 and depth >= 2 or leaf or not all(os.path.isdir(c) for c in cands)):
            os.symlink(cands[0], dst); n[0] += 1
            for c in cands[1:]: conflicts.append((rel, cands[0], c))
            return
        os.makedirs(dst, exist_ok=True)
        kids = {}
        for c in cands:
            for k in ls(c):
                if k not in JUNK: kids.setdefault(k, []).append(os.path.join(c, k))
        for k, cs in kids.items(): merge(os.path.join(dst, k), f'{rel}/{k}' if rel else k, cs)
    tops = {}
    for r in roots:
        for top, p in r.items():
            if '/' in top:   # inbox names like software/src land one level down
                t, sub = top.split('/', 1); tops.setdefault(t, [])
                tops.setdefault(f'{t}/{sub}', []).append(p)
            else: tops.setdefault(top, []).append(p)
    root = os.path.join(os.path.dirname(view), '.ark-views'); os.makedirs(root, exist_ok=True)
    new = os.path.join(root, time.strftime('%Y%m%dT%H%M%S')); os.makedirs(new)
    for top in sorted(t for t in tops if '/' not in t):
        cs = list(tops[top])
        extra = {t.split('/', 1)[1]: ps for t, ps in tops.items() if t.startswith(top + '/')}
        if extra:   # e.g. software on drives + inbox/src as software/src: merge the inbox dir in under its sub-name
            d = os.path.join(new, top); os.makedirs(d)
            kids = {}
            for c in cs:
                for k in ls(c):
                    if k not in JUNK: kids.setdefault(k, []).append(os.path.join(c, k))
            for sub, ps in extra.items(): kids.setdefault(sub, []).extend(ps)
            for k, ks in kids.items(): merge(os.path.join(d, k), f'{top}/{k}', ks)
        else: merge(os.path.join(new, top), top, cs)
    tmp = view + '.new'
    if os.path.lexists(tmp): os.unlink(tmp)
    os.symlink(new, tmp); os.replace(tmp, view)
    for old in ls(root)[:-2]: shutil.rmtree(os.path.join(root, old), ignore_errors=True)   # keep the live tree and one before it
    with open(os.path.join(inbox, 'ARK-CONFLICTS.tsv'), 'w') as f:
        f.write('view_path\tused\tshadowed\n')
        for c in conflicts: f.write('\t'.join(c) + '\n')
    return n[0], len(conflicts)

HDD_CACHE_S = 86400   # a spinning disk is walked file-by-file at most once a day; its file list is cached in the inbox

def walk_files(mp, rot, inbox, uuid):
    """{name: [sizes]} and dir names for every file outside PRUNE; cached per filesystem uuid when its label is cold in ARK-TIERS.tsv."""
    cache = os.path.join(inbox, '.ark-scan', (uuid or mp.strip('/').replace('/', '_')) + '.json')
    if rot and os.path.isfile(cache) and time.time() - os.path.getmtime(cache) < HDD_CACHE_S:
        try: d = json.load(open(cache)); return d['files'], set(d['dirs'])
        except (OSError, ValueError): pass
    files, dirs = {}, set()
    for root, ds, fs in os.walk(mp):
        if os.path.basename(root).startswith('wheels'): ds[:] = []; continue
        dirs.update(ds)
        ds[:] = [d for d in ds if d not in PRUNE and not os.path.islink(os.path.join(root, d))]
        for f in fs:
            try: files.setdefault(f, []).append(os.lstat(os.path.join(root, f)).st_size)
            except OSError: pass
    if rot and os.access(inbox, os.W_OK):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache + '.tmp', 'w') as fh: json.dump({'files': files, 'dirs': sorted(dirs)}, fh)
        os.replace(cache + '.tmp', cache)
    return files, dirs

def scan(drives, inbox, W, deep):
    names, sizes, exts, lexts = set(W.get('names', [])), set(W.get('sizes', [])), set(W.get('exts', [])), set(W.get('list_exts', []))
    idx = {k: {} for k in ('repos', 'models', 'hf', 'wheels', 'binaries')}
    found = {'ns': set(), 'se': set(), 'sz': set(), 'names': set(), 'dirs': set(), 'whence': set()}
    for lab, uuid, mp, dev in drives:
        base = mp.rstrip('/').count('/')
        for root, ds, fs in os.walk(mp):   # layout only: a few levels, cheap even on a busy HDD
            here = os.path.basename(root); parent = os.path.basename(os.path.dirname(root))
            if 'src' in ds:   # checkouts: list them, never walk into them
                for r in ls(os.path.join(root, 'src')):
                    if r.count('__') >= 2: idx['repos'].setdefault(r, os.path.join(root, 'src', r))
            if here in ('models', 'llm') and root.count('/') <= base + 1:
                for m in ds: idx['models'].setdefault(m, os.path.join(root, m))
            if parent in ('hf-assets', 'hf'):
                for r in ds: idx['hf'].setdefault(here + '/' + r, os.path.join(root, r))
            if parent == 'binaries': idx['binaries'].setdefault(here, root)
            if '.whence_commit' in fs: found['whence'].add(here)
            if here.startswith('wheels'):
                for f in fs:
                    if f.endswith('.whl'): idx['wheels'].setdefault(f, os.path.join(root, f))
                ds[:] = []; continue
            ds[:] = [d for d in ds if d not in PRUNE and not os.path.islink(os.path.join(root, d))] if root.count('/') < base + 3 else []
        if not deep: continue
        files, dirs = walk_files(mp, tiers(inbox).get(lab) == 'cold', inbox, uuid)
        found['dirs'] |= dirs
        for f, szs in files.items():
            e = os.path.splitext(f)[1].lower()
            if f in names or e in lexts: found['names'].add(f)
            if f in names or e in exts:
                for sz in szs:
                    if sz in sizes: found['ns'].add(f'{f}|{sz}'); found['se'].add(f'{sz}|{e}'); found['sz'].add(sz)
    if os.access(inbox, os.W_OK):
        with open(inbox + '/ARK-INDEX.tsv.tmp', 'w') as f:
            f.write('kind\tkey\tpath\n')
            for k, d in idx.items():
                for key, path in sorted(d.items()): f.write(f'{k}\t{key}\t{path}\n')
        os.replace(inbox + '/ARK-INDEX.tsv.tmp', inbox + '/ARK-INDEX.tsv')
        with open(inbox + '/ARK-DRIVES.tsv', 'w') as f:
            f.write('label\tuuid\tmountpoint\tdevice\n')
            for d in drives: f.write('\t'.join(d) + '\n')
    return idx, found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inbox', default='/data/ark-inbox'); ap.add_argument('--view', default='/data/ark')
    ap.add_argument('--want', action='store_true'); ap.add_argument('--no-view', action='store_true')
    a = ap.parse_args()
    W = json.load(sys.stdin) if a.want else {}
    drives = mounts(a.inbox)
    idx, found = scan(drives, a.inbox, W, deep=a.want)
    nv = (0, 0) if a.no_view else build_view(drives, a.inbox, a.view)
    if not a.want:
        print(f"ark-index: {len(drives)} filesystems, {len(idx['repos'])} repos, {len(idx['models'])} model dirs, "
              f"{len(idx['wheels'])} wheels; view {a.view}: {nv[0]} links, {nv[1]} conflicts"); return
    led = a.inbox + '/ARK-FETCHED.tsv'
    req = []
    for p in [a.inbox + '/REQUESTS.tsv'] + [os.path.join('/data/pod/plans', d, 'fetch-requests.txt') for d in ls('/data/pod/plans')]:
        if os.path.isfile(p): req += [(p, l.rstrip('\n')) for l in open(p, errors='replace') if l.strip() and not l.startswith('#')]
    print(json.dumps({'found': {k: sorted(v) for k, v in found.items()}, 'repos': sorted(idx['repos']), 'wheels': sorted(idx['wheels']),
                      'models': sorted(idx['models']), 'hf': sorted(idx['hf']), 'drives': drives, 'requests': req,
                      'ledger': [l.split('\t')[0] for l in open(led)] if os.path.isfile(led) else [],
                      'writable': os.access(a.inbox, os.W_OK), 'view': nv}))

if __name__ == '__main__': main()
