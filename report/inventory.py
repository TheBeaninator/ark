#!/usr/bin/env python3
import os,json,subprocess,re,glob
def du(p): 
    try: return int(subprocess.run(['du','-sB1','-x',p],capture_output=True,text=True).stdout.split()[0])
    except: return 0
def free(p): s=os.statvfs(p); return s.f_bavail*s.f_frsize, s.f_blocks*s.f_frsize
inv={'drives':{},'models':[],'comfy':{},'hf_assets':[],'software':{},'docs':[]}
for n in range(1,7):
    d=f'/mnt/nv{n}'; fr,tot=free(d); inv['drives'][f'nv{n}']={'free':fr,'total':tot,'top':{e:du(f'{d}/{e}') for e in sorted(os.listdir(d)) if not e.startswith('lost') and not os.path.islink(f'{d}/{e}')}}
# models: <drive>/models/<name>/{raw,gguf,...}
for n in range(1,7):
    m=f'/mnt/nv{n}/models'
    if not os.path.isdir(m): continue
    for name in sorted(os.listdir(m)):
        p=f'{m}/{name}'
        if not os.path.isdir(p) or os.path.islink(p): continue
        subs=[s for s in os.listdir(p) if os.path.isdir(f'{p}/{s}')]
        formats=[]
        for root,dn,fn in os.walk(p):
            for f in fn:
                e=f.rsplit('.',1)[-1].lower()
                if e in('gguf','safetensors','pth','pt','bin','onnx','xml'): formats.append(e)
            if len(formats)>2000: break
        fm=sorted(set(formats)); quant=set(re.findall(r'(Q\d_[A-Z0-9_]+|UD-Q\d_[A-Z_]+|MXFP4|bf16|fp8|FP8|Q8_0|Q4_K_M|IQ\d_[A-Z]+|W4A16|int8)',' '.join(os.listdir(p)+sum([os.listdir(f'{p}/{s}') for s in subs],[]))))
        inv['models'].append({'drive':f'nv{n}','name':name,'size':du(p),'layout':sorted(subs) or ['flat'],'formats':fm,'quants':sorted(quant)[:6]})
# comfy on nv6: type -> base -> (count,size)
C='/mnt/nv6/comfy'
for t in sorted(os.listdir(C)):
    tp=f'{C}/{t}'; 
    if not os.path.isdir(tp): continue
    inv['comfy'][t]={}
    for b in sorted(os.listdir(tp)):
        bp=f'{tp}/{b}'
        if not os.path.isdir(bp): continue
        cnt=sum(len(fn) for _,_,fn in os.walk(bp)); inv['comfy'][t][b]={'files':cnt,'size':du(bp)}
# hf-assets on nv3: org/repo
H='/mnt/nv3/hf-assets'
for org in sorted(os.listdir(H)):
    op=f'{H}/{org}'
    if not os.path.isdir(op): continue
    for r in sorted(os.listdir(op)):
        rp=f'{op}/{r}'
        if os.path.isdir(rp): inv['hf_assets'].append({'org':org,'repo':r,'size':du(rp)})
# software mirror
S='/mnt/nv2/software'; sec=None; repos={}
for line in open(f'{S}/mirrors.txt'):
    line=line.strip()
    if line.startswith('#'): sec=line.lstrip('# ').strip(); continue
    if line.startswith('http'):
        n=re.sub(r'^https?://','',line).replace('/','__').removesuffix('.git'); p=f'{S}/src/{n}'
        repos.setdefault(sec or 'other',[]).append({'url':line,'present':os.path.isdir(p),'node_modules':os.path.isdir(f'{p}/node_modules'),'size':du(p) if os.path.isdir(p) else 0})
inv['software']['repos']=repos
inv['software']['binaries']=sorted(os.listdir(f'{S}/binaries'))
inv['software']['python']=sorted(glob.glob(f'{S}/binaries/python/*/*.tar.gz'))
w=os.listdir(f'{S}/wheels'); inv['software']['wheels']={'total':len(w),'cp312':sum('cp312' in x for x in w),'cp313':sum('cp313' in x for x in w),'cp314':sum('cp314' in x for x in w),'pure':sum('py3-none-any' in x for x in w),'sdist':sum(x.endswith('.tar.gz') for x in w),'size':du(f'{S}/wheels')}
for e in ['wheels-cuda-cu130','wheels-cuda-cu128','debs','rocm','containers','cargo-home','cmake-deps','gomodcache','npm-cache','pnpm-store','bun-cache','docs']:
    p=f'{S}/{e}'; inv['software'][e]={'size':du(p),'entries':len(os.listdir(p)) if os.path.isdir(p) else 0} if os.path.exists(p) else None
inv['software']['ubuntu_mirror']={'size':du('/mnt/nv4/ubuntu-mirror'),'repos':sorted(os.listdir('/mnt/nv4/ubuntu-mirror'))}
inv['software']['containers_list']=sorted(os.listdir(f'{S}/containers'))
inv['docs']=sorted(os.listdir(f'{S}/docs'))
for lane in ('','-cp313','-cp314'):
    try: inv['software'][f'resolve{lane or "-cp312"}']={k:sum(1 for l in open(os.path.expanduser(f'~/depaudit/{k}{lane}.log')) if l.startswith('OK')) for k in ('reqs','projects')}|{k+'_fail':sum(1 for l in open(os.path.expanduser(f'~/depaudit/{k}{lane}.log')) if l.startswith('FAIL')) for k in ('reqs','projects')}
    except Exception as e: pass
json.dump(inv,open(os.path.expanduser('~/storage-review/inventory.json'),'w'),indent=1); print('models',len(inv['models']),'hf-assets',len(inv['hf_assets']),'repos',sum(len(v) for v in repos.values()))
