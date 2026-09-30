#!/usr/bin/env python3
"""fetch/assets.py DESTDIR — CC0 assets per manifest/assets.tsv: all Poly Haven 2k HDRIs, top-400 Poly Haven textures (2k jpg maps), top-400 ambientCG materials (2K-JPG). Needs aria2c."""
import sys,json,urllib.request,os,subprocess,time
AS=sys.argv[1]; A=os.path.expanduser('~/.local/bin/aria2c'); UA={'User-Agent':'Mozilla/5.0'}
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60))
def dl(u,d,o=None):
    cmd=[A,'-c','-x4','--file-allocation=none','--auto-file-renaming=false','--console-log-level=error','--summary-interval=0','-d',d,u]+(['-o',o] if o else [])
    return subprocess.run(cmd,capture_output=True).returncode==0
ok=fail=0
h=get('https://api.polyhaven.com/assets?t=hdris')
for i,(k,v) in enumerate(sorted(h.items(),key=lambda kv:-kv[1].get('download_count',0))):
    try: f=get(f'https://api.polyhaven.com/files/{k}')['hdri']['2k']['hdr']['url']
    except Exception: fail+=1; continue
    if os.path.exists(f'{AS}/polyhaven/hdris/{os.path.basename(f)}'): ok+=1; continue
    ok+=dl(f,f'{AS}/polyhaven/hdris'); time.sleep(0.2)
print(f'polyhaven hdris: {ok} ok {fail} fail',flush=True)
ok=fail=0; t=get('https://api.polyhaven.com/assets?t=textures')
for k,v in sorted(t.items(),key=lambda kv:-kv[1].get('download_count',0))[:400]:
    try: files=get(f'https://api.polyhaven.com/files/{k}')
    except Exception: fail+=1; continue
    d=f'{AS}/polyhaven/textures/{k}'; os.makedirs(d,exist_ok=True); got=0
    for m in ('Diffuse','nor_gl','Rough','AO','Displacement','arm','Metal'):
        try: u=files[m]['2k']['jpg']['url']
        except Exception: continue
        if os.path.exists(f'{d}/{os.path.basename(u)}') or dl(u,d): got+=1
    ok+=got>0; time.sleep(0.2)
print(f'polyhaven textures (top 400, 2k jpg): {ok} ok {fail} fail',flush=True)
ok=fail=0; off=0
while off<400:
    r=get(f'https://ambientcg.com/api/v2/full_json?type=Material&sort=Popular&limit=100&offset={off}'); items=r.get('foundAssets',[])
    if not items: break
    for a in items:
        try: dls=a['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']; u=next(x['downloadLink'] for x in dls if x['attribute']=='2K-JPG')
        except Exception: fail+=1; continue
        fn=f"{a['assetId']}_2K-JPG.zip"
        if os.path.exists(f'{AS}/ambientcg/{fn}') or dl(u,f'{AS}/ambientcg',fn): ok+=1
        else: fail+=1
        time.sleep(0.3)
    off+=100
print(f'ambientcg materials (top 400, 2K-JPG): {ok} ok {fail} fail',flush=True)
