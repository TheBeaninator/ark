#!/usr/bin/env python3
"""tools/inbox-sync.py — keep an air-gapped island's inbox in step with the manifests.

Runs on a machine with internet AND ssh to the island's control node (reference build: the laptop -> pod-control).
  1. want: for every manifest row (manifest/ + manifest-private/), what it looks like on disk: repos by checkout dir name,
     models by the (file name, size) of every HF file the row's include globs select, url rows by (name, Content-Length).
  2. find: tools/ark-index.py runs on the island (shipped to <inbox>/tools each run) and answers which of those exist, by
     content (name+size, or size+extension for renamed copies), never by mount name or drive label. Drives can be
     relabelled, swapped between ports or hosts, or have their contents reshuffled and the next run still sees what is there.
     The same run rebuilds the island's /data/ark view, ARK-INDEX.tsv and ARK-DRIVES.tsv (see tools/ark-index.py).
  3. fetch: only the rows found nowhere, with the normal fetch/ scripts (ARK_ONLY row filter) into a local stage that has
     the inbox layout; models over --max-gb, or of unknown size, are listed as TOO-BIG instead.
  4. push: rsync the stage into <inbox>, clear the stage, append the keys to <inbox>/ARK-FETCHED.tsv, re-index, and write
     <inbox>/SYNC-STATUS.json so island agents can see what is coming and what is stuck.
  5. requests: island agents may append lines to <inbox>/REQUESTS.tsv or any /data/pod/plans/*/fetch-requests.txt; they are
     reported, never fetched, until a manifest row exists (what enters the island is always on the list).
Exits 0 quietly when the island is unreachable, so it is safe on a timer.
Usage: tools/inbox-sync.py [--dry-run] [--max-gb 40] [--host pod-control-ll] [--inbox /data/ark-inbox] [--only repos,models,reference]
"""
import argparse, fcntl, fnmatch, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

ARK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.expanduser('~/.local/state/ark-inbox-sync')
UA = {'User-Agent': 'ark-inbox-sync/1'}
HF_EXCLUDE = ('tf_*', 'flax_*', '*.h5', '*.msgpack', '.gitattributes')   # what fetch/hf-models.sh leaves out

def sh(cmd, **kw): return subprocess.run(cmd, text=True, capture_output=True, **kw)

def island(host, inbox, want):
    """Ship tools/ark-index.py + ark-path to <inbox>/tools (the island runs the same copy on its own timer), then scan."""
    t = os.path.join(ARK, 'tools')
    r = sh(['rsync', '-a', '--mkpath', f'{t}/ark-index.py', f'{t}/ark-path', f'{host}:{inbox}/tools/'])
    if r.returncode: return None, 'rsync tools: ' + r.stderr[-200:]
    r = sh(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', host, 'ionice', '-c3', 'nice', 'python3', f'{inbox}/tools/ark-index.py', '--want', '--inbox', inbox],
           input=json.dumps(want), timeout=1800)
    if r.returncode: return None, (r.stderr.strip() or 'ssh failed')[-300:]
    return json.loads(r.stdout), ''

def rows(name):
    out = []
    for d in ('manifest', 'manifest-private'):
        p = os.path.join(ARK, d, name)
        if not os.path.isfile(p): continue
        lines = open(p, encoding='utf-8').read().replace('\r', '').split('\n')
        hdr = lines[0].split('\t')
        out += [dict(zip(hdr, l.split('\t'))) for l in lines[1:] if l.strip() and not l.startswith('#')]
    return out

def repo_dir(url): return re.sub(r'\.git$', '', re.sub(r'^https?://', '', url).replace('/', '__'))
def norm(s): return re.sub(r'[-_.]+', '_', s).lower()
def is_page(u): return u.endswith('/') or '?' in u or '.' not in os.path.basename(u)
def ext(n): e = os.path.splitext(n)[1].lower(); return '' if e[1:].isdigit() else e   # arxiv ids are not extensions

class Cache:   # HF listings and Content-Lengths change rarely; one day is fresh enough
    def __init__(s): s.p = os.path.join(STATE, 'cache.json'); s.d = json.load(open(s.p)) if os.path.isfile(s.p) else {}
    def get(s, k, fn):
        v = s.d.get(k)
        if v and time.time() - v[0] < 86400: return v[1]
        x = fn()
        if x is not None: s.d[k] = [time.time(), x]
        return x
    def save(s): json.dump(s.d, open(s.p, 'w'))

def hf_files(hid):
    h = dict(UA)
    for p in ('~/.cache/huggingface/token', '~/.huggingface/token'):
        p = os.path.expanduser(p)
        if os.path.isfile(p): h['Authorization'] = 'Bearer ' + open(p).read().strip(); break
    try: d = json.load(urllib.request.urlopen(urllib.request.Request(f'https://huggingface.co/api/models/{hid}?blobs=true', headers=h), timeout=30))
    except Exception: return None
    return [[s['rfilename'], s.get('size') or 0] for s in d.get('siblings', [])]

def head_size(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, method='HEAD', headers=UA), timeout=20)
        return int(r.headers.get('Content-Length') or 0) or None
    except Exception: return None

def wanted(only, cache):
    """-> list of (kind, key, row, checks) where checks says how to recognise the row on the island."""
    out = []
    if 'repos' in only:
        out += [('repos', r['url'], r, {'repo': repo_dir(r['url'])}) for r in rows('repos.tsv')]
    if 'models' in only:
        for r in rows('models.tsv'):
            hid, pats = r['hf_id'], r.get('include', '').split()
            if r['kind'] == 'comfy': out.append(('models', hid, r, {'skip': 'comfy rows live in comfy/ trees'})); continue
            fl = cache.get('hf:' + hid, lambda: hf_files(hid))
            sel = None if fl is None else [(os.path.basename(n), s) for n, s in fl if (not pats or any(fnmatch.fnmatch(n, p) for p in pats))
                                           and not any(fnmatch.fnmatch(n, x) for x in HF_EXCLUDE)]
            big = [f for f in sel or [] if f[1] >= 1 << 20]
            out.append(('models', hid, r, {'files': big or sel or [], 'gb': None if sel is None else sum(s for _, s in sel) / 1e9, 'whole': not pats,
                                           'dir': [hid.replace('/', '__').lower(), hid.split('/')[-1].lower()]}))
    if 'reference' in only:
        for r in rows('reference.tsv'):
            k, src, pat = r['kind'], r['source'], r.get('pattern_or_target', '')
            if k == 'url' and '{REL}' not in src:
                if is_page(src): c = {'dir': os.path.basename(src.rstrip('/').split('?')[0])}
                else:
                    sz = cache.get('len:' + src, lambda: head_size(src))
                    c = {'files': [(os.path.basename(src), sz)]} if sz else {'name': os.path.basename(src)}
            elif k in ('zim', 'iso') or (k == 'url'):
                c = {'regex': '^' + re.escape(pat if k != 'url' else os.path.basename(src)).replace(r'\*', '.*').replace(re.escape('{REL}'), r'\d+') + '$'}
            elif k == 'findlinks': c = {'wheel': norm(re.split(r'[<>=!~\[ ]', pat)[0])}
            elif k == 'whence': c = {'whence': pat}
            else: c = {'skip': f'kind {k} not tracked'}
            out.append(('reference', src, r, c))
    return out

def present(c, f, isl):
    if 'repo' in c: return c['repo'] in isl['repos']
    if 'wheel' in c: return any(norm(w.split('-')[0]) == c['wheel'] for w in isl['wheels'])
    if 'whence' in c: return c['whence'] in f['whence']
    if 'regex' in c: rx = re.compile(c['regex']); return any(rx.match(n) for n in f['names_all'])
    if 'name' in c: return c['name'] in f['names']
    if c.get('files'):   # every payload file somewhere: same name and size, or same size and extension (a renamed copy)
        gone = [n for n, s in c['files'] if not (f'{n}|{s}' in f['ns'] or (f'{s}|{ext(n)}' in f['se'] if ext(n) else s in f['sz']))]
        c['why'] = f"{len(gone)}/{len(c['files'])} files absent, e.g. {gone[0]}" if gone else ''
        if not gone: return True
        # a whole-repo row mirrored selectively (safetensors kept, duplicate .bin skipped) still counts once any payload or its dir is there
        # ...but only when the matched files hold real weight: shared tokenizers (every Gemma has the same tokenizer.model) must not count
        tot = sum(s for _, s in c['files']) or 1; have = tot - sum(s for n, s in c['files'] if n in gone)
        if c.get('whole') and have / tot >= 0.3: c['stale'] = f'partial ({have * 100 // tot}% of bytes)'; return True
        own_dir = any(x in f['dirs_l'] for x in c['dir']) if c.get('dir') else True   # url rows: the file name itself is distinctive
        if own_dir and all(n in f['names'] for n in gone): c['stale'] = 'upstream changed size'; return True   # same names in its own folder: older versions
        return False
    if 'dir' in c:
        d = c['dir'] if isinstance(c['dir'], list) else [c['dir']]
        return any(x in f['dirs_l'] for x in (y.lower() for y in d))
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default=os.environ.get('ARK_ISLAND_HOST', 'pod-control-ll'))
    ap.add_argument('--inbox', default=os.environ.get('ARK_INBOX', '/data/ark-inbox'))
    ap.add_argument('--stage', default=os.path.expanduser(os.environ.get('ARK_STAGE', '~/.cache/ark-inbox-stage')))
    ap.add_argument('--max-gb', type=float, default=float(os.environ.get('ARK_SYNC_MAX_GB', 40)))
    ap.add_argument('--only', default='repos,models,reference')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--exclude-tag', default=os.environ.get('ARK_EXCLUDE_TAGS', ''),
                    help='comma-separated manifest/tags.tsv tags to leave out, e.g. license-agreement')
    a = ap.parse_args(); only = set(a.only.split(','))
    os.makedirs(STATE, exist_ok=True)
    lock = open(os.path.join(STATE, 'lock'), 'w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: print('another inbox-sync is running'); return 0
    if sh(['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes', a.host, 'true']).returncode:
        print(f'island unreachable ({a.host})'); return 0
    cache = Cache(); W = wanted(only, cache); cache.save()
    if a.exclude_tag:
        sys.path.insert(0, os.path.join(ARK, 'tools')); import importlib; skip = set(importlib.import_module('ark-tags').keys_with(a.exclude_tag))
        n = len(W); W = [w for w in W if w[1] not in skip]
        print(f'excluding tag(s) {a.exclude_tag}: {n - len(W)} rows left out')
        os.environ['ARK_EXCLUDE_TAGS'] = a.exclude_tag   # the fetchers skip them too
    names, sizes, exts = set(), set(), set()
    for _, _, _, c in W:
        for n, s in c.get('files') or []: names.add(n); sizes.add(s); exts.add(ext(n) or '.pdf')
        if 'name' in c: names.add(c['name'])
    # regex rows (zim/iso/{REL}) need every file name; ask for names under data trees by extension instead
    isl, err = island(a.host, a.inbox, {'names': sorted(names), 'sizes': sorted(sizes), 'exts': sorted(exts), 'list_exts': ['.zim', '.iso', '.gz', '.fa', '.gtf']})
    if isl is None: print(f'island scan failed: {err}'); return 1
    f = {k: set(v) for k, v in isl['found'].items()}
    f['sz'] = {int(x) for x in f['sz']}
    f['dirs_l'] = {d.lower() for d in f['dirs']} | {m.lower() for m in isl['models']} | {h.lower() for h in isl['hf']}
    f['names_all'] = f['names'] | {x.split('|')[0] for x in f['ns']}
    ledger = set(isl['ledger'])
    print(f"island: {len(isl['drives'])} filesystems ({', '.join(d[0] or d[2] for d in isl['drives'])}); "
          f"{len(isl['repos'])} repos, {len(isl['models'])} model dirs, {len(isl['hf'])} hf-assets, {len(isl['wheels'])} wheels")
    fetch, toobig, skipped = [], [], []
    stale = []
    for kind, key, r, c in W:
        if 'skip' in c: skipped.append(f"{key} ({c['skip']})"); continue
        if key in ledger or present(c, f, isl):
            if c.get('stale'): stale.append(f"{key} ({c['stale']}: {c['why']})")
            continue
        if kind == 'models' and (c['gb'] is None or c['gb'] > a.max_gb or c['gb'] == 0):
            toobig.append((key, c['gb'])); continue
        fetch.append((kind, key, r, c))
    for kind, key, r, c in fetch: print(f"MISSING {kind:9} {key}" + (f"  ({c['gb']:.1f} GB)" if c.get('gb') else '') + (f"  [{c['why']}]" if c.get('why') else ''))
    for key, gb in toobig: print(f"TOO-BIG models    {key}  ({'size unknown (gated?)' if gb is None else 'include matches no file' if gb == 0 else f'{gb:.0f} GB'})")
    print(f"{len(stale)} rows present but partial or older than upstream (not refetched; see last.json)")
    for p, l in isl['requests']: print(f"REQUEST {p}: {l[:160]}")
    status = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'host': os.uname().nodename,
              'drives': isl['drives'], 'missing': [k for _, k, _, _ in fetch], 'stale': stale, 'too_big': [k for k, _ in toobig],
              'skipped': skipped, 'requests': [l for _, l in isl['requests']], 'fetched': [], 'failed': []}
    if a.dry_run or not fetch:
        if not fetch: print('nothing to fetch')
        return finish(a, status, push=not a.dry_run)
    if not isl['writable']: print(f'{a.inbox} is not writable on {a.host}'); return 1
    os.makedirs(a.stage, exist_ok=True)
    a.stage = tempfile.mkdtemp(prefix='run-', dir=a.stage)   # this run's own folder: never push or clear anyone else's staging
    env = dict(os.environ, ARK_SOFTWARE=a.stage, ARK_MODELS=a.stage + '/models', ARK_HF_ASSETS=a.stage + '/hf-assets', ARK_DATA=a.stage)
    with tempfile.NamedTemporaryFile('w', delete=False) as t:
        t.write('\n'.join(k for _, k, _, _ in fetch) + '\n'); env['ARK_ONLY'] = t.name
    script = {'repos': 'fetch/repos.sh', 'models': 'fetch/hf-models.sh', 'reference': 'fetch/reference.sh'}
    ok = set()
    for kind in ('repos', 'models', 'reference'):
        keys = [k for kk, k, _, _ in fetch if kk == kind]
        if not keys: continue
        r = subprocess.run(['bash', os.path.join(ARK, script[kind])], env=env, text=True, capture_output=True, cwd=ARK)
        for l in r.stdout.splitlines():
            print('  ' + l)
            if re.match(r'(\w+-)?FAIL|NO-MATCH', l): status['failed'].append(l); continue
            status['fetched'].append(l)
            ok |= {k for k in keys if l.endswith(' ' + k) or k in l.split() or (kind != 'repos' and os.path.basename(k.rstrip('/')) in l)}
    os.unlink(env['ARK_ONLY'])
    has_files = any(fs for _, _, fs in os.walk(a.stage))
    if not has_files: shutil.rmtree(a.stage, ignore_errors=True)   # nothing downloaded: push nothing (an empty dir would read as present)
    else:
        r = sh(['rsync', '-a', '--partial', '--prune-empty-dirs', a.stage + '/', f'{a.host}:{a.inbox}/'])
        if r.returncode:
            print('rsync failed: ' + r.stderr[-300:]); status['failed'].append('rsync'); return finish(a, status, push=True)
        shutil.rmtree(a.stage); print(f'pushed into {a.host}:{a.inbox}')
        sh(['ssh', '-o', 'BatchMode=yes', a.host, f'cat >> {a.inbox}/ARK-FETCHED.tsv'], input=''.join(f"{k}\t{status['utc']}\n" for k in sorted(ok)))
        island(a.host, a.inbox, {'names': [], 'sizes': [], 'exts': []})   # re-index: ARK-INDEX.tsv shows the new arrivals
    return finish(a, status, push=True)

def finish(a, status, push):
    json.dump(status, open(os.path.join(STATE, 'last.json'), 'w'), indent=1)
    if push: sh(['ssh', '-o', 'BatchMode=yes', a.host, f'cat > {a.inbox}/SYNC-STATUS.json'], input=json.dumps(status, indent=1))
    return 1 if status['failed'] else 0

if __name__ == '__main__': sys.exit(main())
