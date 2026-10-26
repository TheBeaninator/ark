#!/usr/bin/env python3
"""Hermetic test for island_guard.py (ark card AI-4, /data/pod/plans/19f7dca19b). Plain python3, exits 0/1.
Runs entirely in tmp dirs; touches nothing outside its sandbox."""
import datetime
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('island_guard', os.path.join(HERE, 'island_guard.py'))
ig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ig)

FAILS = []
TOTAL = 0


def ck(label, cond, detail=''):
    global TOTAL
    TOTAL += 1
    if cond:
        print('ok    ' + label)
    else:
        print('FAIL  ' + label + ('  | ' + detail if detail else ''))
        FAILS.append(label)


def w(path, data, mtime):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    os.utime(path, (mtime, mtime))


def sandbox():
    d = tempfile.mkdtemp(prefix='island_guard_test.')
    return d, os.path.join(d, 'repo', 'tools'), os.path.join(d, 'inbox', 'tools')


RELM = 'tools/ark-index.py'
T0 = 1600000000  # fixed epoch-ish base so mtimes are deterministic

# 1. island file missing -> sync
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b'repo content\n', T0)
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM)
ck('island missing -> sync', v == 'sync' and line is None and ds == '', repr((v, line, ds)))
shutil.rmtree(d)

# 2. identical bytes -> sync (even when island mtime is newer)
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b'same\ncontent\n', T0)
w(os.path.join(isl, 'ark-index.py'), b'same\ncontent\n', T0 + 5000)
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM)
ck('identical -> sync', v == 'sync' and line is None and ds == '', repr((v, line, ds)))
shutil.rmtree(d)

# 3. island NEWER and differs -> keep, correct requests line; REQUESTS.tsv gets header + timestamped line
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b'line1\nline2\nline3\n', T0)
w(os.path.join(isl, 'ark-index.py'), b'line1\nline2 island fix\nline3\nline4 island fix\n', T0 + 7000)
ip = os.path.join(isl, 'ark-index.py')
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), ip, RELM)
ck('island newer+differs -> keep', v == 'keep', repr((v, line, ds)))
ck('requests line is exact',
   line == 'UPSTREAM %s: island copy differs, port it' % RELM, repr(line))
ck('diffstat has +N -M header and both island lines',
   ds.splitlines()[0] == '+2 -1 in %s' % RELM and '+line2 island fix' in ds and '+line4 island fix' in ds,
   repr(ds))
tsv = os.path.join(d, 'inbox', 'REQUESTS.tsv')
entry = ig.append_request(tsv, line)
entry2 = ig.append_request(tsv, 'UPSTREAM tools/ark-path: island copy differs, port it')  # append-only check
raw = open(tsv).read()
exp = (ig.REQUESTS_HEADER + '\n' +
       '%s\t%s\n' % (datetime.date.today().isoformat(), line) +
       '%s\t%s\n' % (datetime.date.today().isoformat(), 'UPSTREAM tools/ark-path: island copy differs, port it'))
ck('REQUESTS.tsv created with header + timestamped lines, append-only', raw == exp, repr(raw))
ck('append_request returns the appended line', entry in raw and entry2 in raw)
ck('date field is ISO (YYYY-MM-DD)',
   all(len(l.split('\t')[0]) == 10 and l.split('\t')[0][:4].isdigit() and l.split('\t')[0][4] == '-'
       for l in raw.splitlines() if not l.startswith('#')))
shutil.rmtree(d)

# 4. island OLDER and differs -> sync (repo change is the fresh one), diffstat returned
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b'repo newer\n', T0 + 9000)
w(os.path.join(isl, 'ark-index.py'), b'island older\n', T0)
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM)
ck('island older+differs -> sync', v == 'sync' and line is None and '+1 -1 in %s' % RELM in ds, repr((v, line, ds)))
# 4b. SAME mtime and differs -> sync
w(os.path.join(repo, 'ark-index.py'), b'v3\n', T0 + 11000)
w(os.path.join(isl, 'ark-index.py'), b'v2\n', T0 + 11000)
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM)
ck('island same-mtime+differs -> sync', v == 'sync' and line is None, repr((v, line, ds)))
shutil.rmtree(d)

# 5. island newer but force=True -> sync (repo deliberately overwrites)
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b'repo\n', T0)
w(os.path.join(isl, 'ark-index.py'), b'island newer\n', T0 + 7000)
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM,
                                   force=True)
ck('force -> sync despite newer island', v == 'sync' and line is None, repr((v, line, ds)))
shutil.rmtree(d)

# 6. binary files -> diffstat says 'binary differs' (and the newer-island verdict is still keep)
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-path'), b'\x7fELF\x00\x01\x02binary\x00', T0)
w(os.path.join(isl, 'ark-path'), b'\x7fELF\x00\x09\x08binary\x00', T0 + 7000)
ds = ig.diffstat(os.path.join(repo, 'ark-path'), os.path.join(isl, 'ark-path'), 'tools/ark-path')
ck('binary -> "binary differs"', ds == 'binary differs', repr(ds))
v, line, ds = ig.guard_island_copy(os.path.join(repo, 'ark-path'), os.path.join(isl, 'ark-path'), 'tools/ark-path')
ck('binary newer island -> keep with binary diffstat',
   v == 'keep' and ds == 'binary differs' and line == 'UPSTREAM tools/ark-path: island copy differs, port it',
   repr((v, line, ds)))
shutil.rmtree(d)

# 7. diffstat caps at 20 diff lines
d, repo, isl = sandbox()
w(os.path.join(repo, 'ark-index.py'), b''.join(b'old %d\n' % i for i in range(50)), T0)
w(os.path.join(isl, 'ark-index.py'), b''.join(b'new %d\n' % i for i in range(50)), T0 + 7000)
ds = ig.diffstat(os.path.join(repo, 'ark-index.py'), os.path.join(isl, 'ark-index.py'), RELM)
ck('diffstat caps at %d diff lines' % ig.DIFF_LINES_SHOWN,
   ds.splitlines()[0] == '+50 -50 in %s' % RELM and len(ds.splitlines()) == 1 + ig.DIFF_LINES_SHOWN,
   repr(ds.splitlines()[1:3]))
shutil.rmtree(d)

print('PASS=%d FAIL=%d' % (TOTAL - len(FAILS), len(FAILS)))
sys.exit(1 if FAILS else 0)
