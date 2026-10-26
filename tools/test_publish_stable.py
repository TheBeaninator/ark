#!/usr/bin/env python3
"""test_publish_stable.py — hermetic regression test for publish_stable / the name-aware view prune in
tools/ark-index.py. Extracted from section 1 of /data/pod/plans/71d498e061/verify.sh (card 71d498e061:
/data/ark dangled 2026-10-26 because the prune deleted the just-built view; workers mounting
.ark-views/stable would have gotten ESTALE if the stable dir's inode were ever replaced).

Points the ark repo at ITS OWN file with ARK_INDEX_PATH=<path> (default: /data/ark-inbox/tools/ark-index.py,
the island copy). Exits 0 iff every check passes; prints one ok/FAIL line per assertion.
Run:  python3 test_publish_stable.py"""
import importlib.machinery
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time

ARK_INDEX_PATH = os.environ.get('ARK_INDEX_PATH', '/data/ark-inbox/tools/ark-index.py')

PASS, FAIL = 0, 0


def ck(label, cond, detail=''):
    global PASS, FAIL
    if cond:
        print('ok    ' + label)
        PASS += 1
    else:
        print('FAIL  ' + label + (('  | ' + detail) if detail else ''))
        FAIL += 1
    return bool(cond)


def main():
    global FAIL
    # ---- static check: the file really is the publish_stable build with the name-aware prune filter ----------
    # section 1 of verify.sh grepped the OLD spelling 'TS_RE.match(t)][:-KEEP]'; the merged ark-index.py filter
    # may be spelled TS_RE.match(...) or as an inline re.fullmatch(r'\d{8}T\d{6}', d). The ASSERTION is the same:
    # the prune slices views[:-KEEP] over a list filtered to timestamp-NAMED dirs only.
    try:
        with open(ARK_INDEX_PATH) as f:
            src = f.read()
    except OSError as e:
        print('FAIL  ark-index.py readable at %s  | %s' % (ARK_INDEX_PATH, e))
        return 1
    ck('ark-index.py under test defines publish_stable and build_view calls it',
       re.search(r'^\s*def publish_stable\(', src, re.M) is not None
       and re.search(r'^\s*publish_stable\(root, new\)', src, re.M) is not None)
    ts_filter = (re.search(r"TS_RE\s*=\s*re\.compile\(r'\\d\{8\}T\\d\{6\}'", src) is not None
                 or re.search(r"re\.fullmatch\(r'\\d\{8\}T\\d\{6\}'", src) is not None)
    ck("prune filter is name-aware (timestamp regex \\d{8}T\\d{6} gates the pruned list, TS_RE or inline "
       "fullmatch form — the old ls()[:-2] deleted the live tree)", ts_filter)
    ck('prune slices the filtered list (views[:-2], keeps live + one before)',
       re.search(r'views\[:\-2\]', src) is not None)

    spec = importlib.util.spec_from_file_location(
        'ai', ARK_INDEX_PATH, loader=importlib.machinery.SourceFileLoader('ai', ARK_INDEX_PATH))
    if spec is None:
        print('FAIL  cannot load ark-index.py as a module from %s' % ARK_INDEX_PATH)
        return 1
    ai = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(ai)
    except Exception as e:                                    # a diverged ark-repo copy must produce a FAIL, not a traceback
        print('FAIL  loading %s as a module raised %s: %s' % (ARK_INDEX_PATH, type(e).__name__, e))
        return 1
    if not ck('publish_stable present on the imported module', hasattr(ai, 'publish_stable')):
        return 1                                              # pre-fix file: static checks already reported; skip the functional half

    # ---- functional sandbox (synthetic drives, exactly the verify.sh section-1 setup) --------------------------
    d = tempfile.mkdtemp(prefix='test_publish_stable.')
    try:
        os.makedirs(d + '/nv1/models/llama')
        os.makedirs(d + '/nv2/software/src/repoA')
        os.makedirs(d + '/inbox')
        open(d + '/nv1/models/llama/w.bin', 'w').close()
        open(d + '/nv2/software/src/repoA/f.c', 'w').close()
        V, IN, R = d + '/view', d + '/inbox', d + '/.ark-views'
        dr = [('nv1', 'u1', d + '/nv1', '/dev/x'), ('nv2', 'u2', d + '/nv2', '/dev/y')]
        os.makedirs(R)
        os.mkdir(R + '/not-a-timestamp')        # a non-timestamped dir must NEVER be pruned
        ai.build_view(dr, IN, V)
        ino = os.stat(R + '/stable').st_ino
        os.unlink(d + '/nv2/software/src/repoA/f.c')     # the view changes => new symlinks must land in stable
        time.sleep(1.1)                                   # view names are second-resolution
        ai.build_view(dr, IN, V)
        live = os.path.basename(os.readlink(V))
        rot_ok = (os.stat(R + '/stable').st_ino == ino                     # stable dir never replaced
                  and os.readlink(R + '/current') == live                  # current names the live tree
                  and os.path.isdir(R + '/' + os.readlink(R + '/current'))  # ... and it is not a dangling name
                  and not os.path.lexists(R + '/stable/software/src/repoA/f.c'))  # deletions propagate
        ck('sandbox: stable inode survives a prune, current tracks the live tree, deletions propagate',
           rot_ok, 'root entries: %s' % sorted(os.listdir(R)))
        print('sandbox rotation: %s | root entries: %s' % ('ok' if rot_ok else 'FAILED', sorted(os.listdir(R))))

        # exercise a REAL prune: a third build makes 3 timestamp trees, so build_view must delete the oldest
        # while leaving `stable`, `current` and the non-timestamped dir untouched, and `current` still resolves.
        time.sleep(1.1)
        ai.build_view(dr, IN, V)
        views = sorted(x for x in os.listdir(R) if re.fullmatch(r'\d{8}T\d{6}', x))
        live2 = os.path.basename(os.readlink(V))
        ck('prune ran (oldest of 3 timestamp trees deleted) without touching stable/current or a '
           'non-timestamped dir, and never deletes the live tree',
           len(views) == 2 and views[-1] == live2
           and os.stat(R + '/stable').st_ino == ino
           and os.readlink(R + '/current') == live2
           and os.path.isdir(R + '/' + live2)
           and os.path.isdir(R + '/not-a-timestamp'),
           'root entries: %s' % sorted(os.listdir(R)))
    except Exception as e:                                    # a diverged ark-repo copy must produce a FAIL, not a traceback
        print('FAIL  functional sandbox raised %s: %s' % (type(e).__name__, e))
        FAIL += 1
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
