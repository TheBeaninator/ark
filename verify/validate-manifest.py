#!/usr/bin/env python3
"""verify/validate-manifest.py [--online] [--changed BASE] — check every manifest row is well-formed and (with --online) that the
reference resolves. --changed BASE limits the online checks to rows added or modified since git ref BASE (what CI does for a pull
request); a full online sweep is a scheduled job. GitHub rate-limits anonymous requests hard: set GITHUB_TOKEN (CI has one) and the
script uses the API; without it, it goes slowly and retries on 429. Exit 1 on any problem; rate-limited rows are reported, not failed."""
import csv,re,sys,os,json,time,subprocess,urllib.request,concurrent.futures as cf
ON='--online' in sys.argv; CH=sys.argv[sys.argv.index('--changed')+1] if '--changed' in sys.argv else None
TOK=os.environ.get('GITHUB_TOKEN'); limited=[]
changed=set()
if CH:
    diff=subprocess.run(['git','diff','--unified=0',CH,'--','manifest/'],capture_output=True,text=True).stdout
    for l in diff.splitlines():
        if l.startswith('+') and not l.startswith('+++'): changed.update(x.strip() for x in l[1:].split('\t'))
M=os.path.join(os.path.dirname(__file__),'..','manifest'); P=os.path.join(os.path.dirname(__file__),'..','manifest-private'); bad=[]
def rows(f):
    for base in (M,P):
        if not os.path.exists(os.path.join(base,f)): continue
        with open(os.path.join(base,f)) as fh:
            r=csv.reader(fh,delimiter='\t'); h=next(r)
            for i,row in enumerate(r,2):
                if not row or row[0].startswith('#'): continue
                yield (i if base==M else f'private:{i}'),dict(zip(h,row+['']*(len(h)-len(row))))
def head(u,timeout=20):
    m=re.match(r'https://github\.com/([\w.-]+)/([\w.-]+)',u)
    if m and TOK: u=f'https://api.github.com/repos/{m.group(1)}/{m.group(2)}'
    for attempt in range(4):
        try:
            req=urllib.request.Request(u,method='HEAD' if not m else 'GET',headers={'User-Agent':'ark-validate/1',**({'Authorization':f'Bearer {TOK}'} if m and TOK else {})}); return urllib.request.urlopen(req,timeout=timeout).status
        except urllib.error.HTTPError as e:
            if e.code in (429,403) and attempt<3: time.sleep(5*(attempt+1)); continue
            return e.code
        except Exception: return 0
def hf(id,kind='models'):
    try: return urllib.request.urlopen(urllib.request.Request(f'https://huggingface.co/api/{kind}/{id}',headers={'User-Agent':'ark-validate/1'}),timeout=20).status==200
    except urllib.error.HTTPError as e: return e.code in (401,403)   # gated repos answer 401/403 but exist
    except Exception: return False
CATS=set(); checks=[]
for i,r in rows('repos.tsv'):
    if not re.match(r'^https://[a-z0-9.-]+/[\w.-]+(/[\w.-]+)+/?(#[\w./-]+)?$',r['url']): bad.append(f'repos.tsv:{i}: url must be https://host/owner/repo[#branch]: {r["url"]}')
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
    if r['kind'] not in ('zim','zim-set','url','iso','findlinks','whence'): bad.append(f'reference.tsv:{i}: kind must be zim|zim-set|url|iso|findlinks|whence')
    if not r['source'].startswith('https://'): bad.append(f'reference.tsv:{i}: source must be https')
    if r['kind']=='url' and '{REL}' not in r['source']: checks.append(('url',i,r['source']))
    if r['kind'] in ('zim','zim-set','iso','findlinks','whence'): checks.append(('url',i,r['source']))
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
        if k=='repo':
            x,_,br=x.partition('#'); m=re.match(r'https://github\.com/([\w.-]+)/([\w.-]+)',x)
            c=head(f'https://api.github.com/repos/{m.group(1)}/{m.group(2)}/{"commits" if re.fullmatch(r"[0-9a-f]{40}",br) else "branches"}/{br}' if br and m else x)
            if c in (429,403): limited.append(x); return None
            return None if c in (200,301,302) else f'repos.tsv:{i}: unreachable {x}{"#"+br if br else ""} (HTTP {c})'
        if k=='hf-model': return None if hf(x) else f'models.tsv:{i}: not on Hugging Face: {x}'
        if k=='hf-dataset': return None if hf(x,'datasets') else f'datasets.tsv:{i}: not on Hugging Face: {x}'
        if k=='url': return None if head(x) in (200,301,302,403) else f'reference.tsv:{i}: unreachable {x}'
    if CH: checks=[c for c in checks if c[2] in changed or any(c[2] in v for v in changed)]
    with cf.ThreadPoolExecutor(3 if not TOK else 8) as ex:
        for r in ex.map(run,checks):
            if r: bad.append(r)
print(f'{len(checks)} references checked{" online" if ON else ""}{f" (changed since {CH})" if CH else ""}; categories: {", ".join(sorted(CATS))}')
if limited: print(f'{len(limited)} GitHub rows rate-limited (429) and NOT verified; set GITHUB_TOKEN or rerun later')
if bad: print('\n'.join(bad)); sys.exit(1)
print('manifest OK')
