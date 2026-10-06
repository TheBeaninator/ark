#!/usr/bin/env python3
"""tools/ark-tags.py — row tags from manifest/tags.tsv (+ manifest-private/tags.tsv).
  ark-tags.py --keys-with license-agreement[,other]   row keys carrying any of these tags, one per line (what the fetchers skip)
  ark-tags.py --list                                  tag counts
  ark-tags.py --show license-agreement                key + note for every row with the tag
Fetchers read ARK_EXCLUDE_TAGS (comma-separated) through ark.env; tools/inbox-sync.py takes --exclude-tag.
"""
import os, sys
ARK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load():
    out = []   # (key, set(tags), note, file)
    for d in ('manifest', 'manifest-private'):
        p = os.path.join(ARK, d, 'tags.tsv')
        if not os.path.isfile(p): continue
        for l in open(p, encoding='utf-8').read().replace('\r', '').split('\n'):
            if not l.strip() or l.startswith('#') or l.startswith('key\t'): continue
            f = l.split('\t') + ['', '']
            out.append((f[0], {t.strip() for t in f[1].split(',') if t.strip()}, f[2], f'{d}/tags.tsv'))
    return out

def keys_with(tags):
    want = {t.strip() for t in tags.split(',') if t.strip()}
    return sorted({k for k, ts, _, _ in load() if ts & want})

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['--keys-with'] and len(a) == 2: print('\n'.join(keys_with(a[1])))
    elif a[:1] == ['--list']:
        from collections import Counter
        for t, n in Counter(t for _, ts, _, _ in load() for t in ts).most_common(): print(f'{n:5}  {t}')
    elif a[:1] == ['--show'] and len(a) == 2:
        for k, ts, note, f in load():
            if a[1] in ts: print(f'{k}\t{note}')
    else: print(__doc__.strip()); sys.exit(2)
