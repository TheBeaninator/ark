#!/usr/bin/env python3
"""tools/mpi-session-from-har.py FILE.har [...] — save the MPI-IS login sessions in browser HARs for fetch/reference.sh `mpi` rows.

MPI-IS model/dataset sites (smpl-x, amass, smpl, mano, flame, ...) only serve downloads to a logged-in session that
has accepted the licence. Log in, open the site's download page, save the network log as a HAR, and run this on it.
For each `<site>.is.tue.mpg.de/download.php` page in the HAR it writes, under $ARK_MPI_AUTH (default
~/.config/ark/mpi, mode 0700/0600), one `<domain>.cookie` + `<domain>.referer` per `domain=` the page links to.
It prints the domains and how many download links each page lists; never the cookie values. Sessions expire, so
re-export when the fetcher reports FAIL-AUTH. --list prints the page's sfile links (for writing manifest rows).
"""
import json, os, re, sys, html
from urllib.parse import urlparse

args = [a for a in sys.argv[1:] if not a.startswith('--')]
if not args: sys.exit(__doc__)
out = os.environ.get('ARK_MPI_AUTH', os.path.expanduser('~/.config/ark/mpi'))
os.makedirs(out, mode=0o700, exist_ok=True); os.chmod(out, 0o700)

def write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f: f.write(text)

for har in args:
    for e in json.load(open(har))['log']['entries']:
        url = e['request']['url']; host = urlparse(url).hostname or ''
        if not (host.endswith('.is.tue.mpg.de') and urlparse(url).path.endswith('/download.php')): continue
        cookies = e['request'].get('cookies') or []
        if not cookies: continue
        page = e['response'].get('content', {}).get('text', '') or ''
        links = sorted(set(html.unescape(m) for m in re.findall(r"""https://[^'"\s]+?sfile=[^'"\s]+""", page)))
        doms = sorted(set(re.findall(r'domain=([\w-]+)', ' '.join(links)))) or [host.split('.')[0]]
        for d in doms:
            write(f'{out}/{d}.cookie', '; '.join(f"{c['name']}={c['value']}" for c in cookies))
            write(f'{out}/{d}.referer', url)
        print(f'{har}: {host} -> session for {", ".join(doms)} ({len(links)} download links) in {out}')
        if '--list' in sys.argv:
            for l in links: print('  ', l)
