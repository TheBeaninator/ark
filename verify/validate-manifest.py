#!/usr/bin/env python3
"""verify/validate-manifest.py [--online] — check every manifest row is well-formed and (with --online) that the reference resolves.
Runs in CI on every pull request, so a contribution is just a line in a TSV that this script accepts. Exit 1 on any problem."""
import csv,re,sys,os,json,urllib.request,concurrent.futures as cf
ON='--online' in sys.argv; M=os.path.join(os.path.dirname(__file__),'..','manifest'); bad=[]
def rows(f):
    with open(os.path.join(M,f)) as fh:
        r=csv.reader(fh,delimiter='\t'); h=next(r)
        for i,row in enumerate(r,2):
            if not row or row[0].startswith('#'): continue
            yield i,dict(zip(h,row+['']*(len(h)-len(row))))
def head(u,timeout=20):
    try:
        req=urllib.request.Request(u,method='HEAD',headers={'User-Agent':'ark-validate/1'}); return urllib.request.urlopen(req,timeout=timeout).status
    except urllib.error.HTTPError as e: return e.code
    except Exception: return 0
def hf(id,kind='models'):
    try: return urllib.request.urlopen(urllib.request.Request(f'https://huggingface.co/api/{kind}/{id}',headers={'User-Agent':'ark-validate/1'}),timeout=20).status==200
    except urllib.error.HTTPError as e: return e.code in (401,403)   # gated repos answer 401/403 but exist
    except Exception: return False
CATS=set(); checks=[]
for i,r in rows('repos.tsv'):
    if not re.match(r'^https://[a-z0-9.-]+/[\w.-]+(/[\w.-]+)+/?$',r['url']): bad.append(f'repos.tsv:{i}: url must be https://host/owner/repo: {r["url"]}')
    if not re.match(r'^[a-z0-9-]+$',r['category']): bad.append(f'repos.tsv:{i}: category must be kebab-case: {r["category"]}')
    if 'civitai' in r['url'].lower(): bad.append(f'repos.tsv:{i}: not accepted')
    CATS.add(r['category']); checks.append(('repo',i,r['url']))
for i,r in rows('models.tsv'):
    if not re.match(r'^[\w.-]+/[\w.-]+$',r['hf_id']): bad.append(f'models.tsv:{i}: hf_id must be org/name: {r["hf_id"]}')
    if r['kind'] not in ('raw','gguf','hf-asset','comfy'): bad.append(f'models.tsv:{i}: kind must be raw|gguf|hf-asset|comfy')
    checks.append(('hf-model',i,r['hf_id']))
for i,r in rows('datasets.tsv'):
    if not re.match(r'^[\w.-]+/[\w.-]+$',r['hf_id']): bad.append(f'datasets.tsv:{i}: hf_id must be org/name')
    checks.append(('hf-dataset',i,r['hf_id']))
for i,r in rows('reference.tsv'):
    if r['kind'] not in ('zim','zim-set','url'): bad.append(f'reference.tsv:{i}: kind must be zim|zim-set|url')
    if not r['source'].startswith('https://'): bad.append(f'reference.tsv:{i}: source must be https')
    if r['kind']=='url' and '{REL}' not in r['source']: checks.append(('url',i,r['source']))
    if r['kind'] in ('zim','zim-set'): checks.append(('url',i,r['source']))
for i,r in rows('containers.tsv'):
    if not re.match(r'^[\w./-]+:[\w.-]+$',r['image']): bad.append(f'containers.tsv:{i}: image must be name:tag')
for i,r in rows('assets.tsv'):
    if r['source'] not in ('polyhaven','ambientcg','url'): bad.append(f'assets.tsv:{i}: unknown source {r["source"]}')
    if r['license'].upper() not in ('CC0','CC-BY','CC-BY-4.0','PUBLIC-DOMAIN','MIT'): bad.append(f'assets.tsv:{i}: license must be stated and permissive')
dups=[u for u in [c[2] for c in checks if c[0]=='repo']]; 
for u in set(dups):
    if dups.count(u)>1: bad.append(f'repos.tsv: duplicate {u}')
if ON:
    def run(c):
        k,i,x=c
        if k=='repo': return None if head(x) in (200,301,302) else f'repos.tsv:{i}: unreachable {x}'
        if k=='hf-model': return None if hf(x) else f'models.tsv:{i}: not on Hugging Face: {x}'
        if k=='hf-dataset': return None if hf(x,'datasets') else f'datasets.tsv:{i}: not on Hugging Face: {x}'
        if k=='url': return None if head(x) in (200,301,302,403) else f'reference.tsv:{i}: unreachable {x}'
    with cf.ThreadPoolExecutor(12) as ex:
        for r in ex.map(run,checks):
            if r: bad.append(r)
print(f'{len(checks)} references checked{" online" if ON else ""}; categories: {", ".join(sorted(CATS))}')
if bad: print('\n'.join(bad)); sys.exit(1)
print('manifest OK')
