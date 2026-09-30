#!/usr/bin/env python3
"""reorg.py — storage reorganisation for the nv drives on bigboy (Claude, 2026-09-29, rev2 after adversarial review).
Usage:  reorg.py plan                 -> writes ~/storage-review/plan/<phase>.tsv + SUMMARY.txt + devs.json (read-only)
        reorg.py apply <phase> [-n]   -> executes that phase's tsv; -n = dry run. Phases in order: A E D B C F G
Safety model: every action is journaled ONLY on success (journal.tsv); skips and failures are re-evaluated on re-run.
Before every action both drives involved must be mounted at /mnt/nvN with the same st_dev recorded at plan time
(USB dropout => refuse, never write into an unmounted mountpoint). No delete without size+sha256 against the keeper or an
explicit DELETE line. Cross-drive move = rsync -> `rsync -c` dry-run verify must be clean -> remove source. Same-drive = rename(2).
MOVE/MOVE_TREE refuse an existing destination; MOVE_TREE_MERGE merges into an existing dir."""
import os, sys, subprocess, hashlib, time, re, shutil, json, traceback
H=os.path.expanduser('~/storage-review/plan'); os.makedirs(H, exist_ok=True)
NV={n:f'/mnt/nv{n}' for n in range(1,7)}
def log(*a):
    s=time.strftime('%FT%T ')+' '.join(str(x) for x in a); print(s, flush=True); open(f'{H}/reorg.log','a').write(s+'\n')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda: f.read(1<<24), b''): h.update(b)
    return h.hexdigest()
def existing_parent(p):
    while not os.path.exists(p): p=os.path.dirname(p)
    return p
def same_fs(a,b): return os.stat(a).st_dev==os.stat(existing_parent(b)).st_dev
def du(p): return int(subprocess.run(['du','-sB1','-x',p],capture_output=True,text=True).stdout.split()[0]) if os.path.exists(p) else 0
def free(p): s=os.statvfs(p); return s.f_bavail*s.f_frsize
def drive_of(p):
    m=re.match(r'(/mnt/(nv\d|scratch1t))(/|$)',p); return m.group(1) if m else None
def rel_symlink(target,link): return os.path.relpath(target, os.path.dirname(link)) if drive_of(target)==drive_of(link) else target
# ───────────────────────── comfy classification ─────────────────────────
STD=['checkpoints','diffusion_models','text_encoders','vae','loras','clip_vision','controlnet','upscale_models','embeddings','unet','audio_encoders','clip',
 'configs','diffusers','gligen','hypernetworks','latent_upscale_models','model_patches','photomaker','style_models','vae_approx','ultralytics','detection',
 'frame_interpolation','background_removal','geometry_estimation','optical_flow','sams','rmbg','classifiers','animatediff_models','_hf']
TYPES={t:t for t in STD}; TYPES.update({'CHECKPOINTS':'checkpoints','LORAS':'loras','checkpoints-sdxl':'checkpoints','passport-controlnet':'controlnet',
 'passport-animatediff_models':'animatediff_models','trellis2-gguf':'diffusion_models','RMBG':'rmbg','unet':'diffusion_models'})
FORCED_BASE={'checkpoints-sdxl':'sdxl','trellis2-gguf':'trellis2'}
BASES=[('wan2.2','wan2.2'),('wan22','wan2.2'),('wan_2.2','wan2.2'),('wan2_1','wan2.1'),('wan2.1','wan2.1'),('wan_2.1','wan2.1'),('wan-animate','wan2.2'),('wan','wan2.1'),
 ('flux2','flux2'),('flux-2','flux2'),('flux_2','flux2'),('krea','flux-krea'),('kontext','flux1'),('flux','flux1'),('chroma','chroma'),('ltx','ltx2'),('qwen_image','qwen-image'),
 ('qwen-image','qwen-image'),('qwenimage','qwen-image'),('z_image','z-image'),('z-image','z-image'),('pixal3d','pixal3d'),('trellis','trellis2'),('firered','firered'),
 ('hidream','hidream'),('hunyuan3d','hunyuan3d'),('hunyuan_3d','hunyuan3d'),('hunyuanvideo','hunyuanvideo'),('hunyuan','hunyuanvideo'),('minimax','minimax-h3'),('pixart','pixart'),
 ('ace_step','ace-step'),('acestep','ace-step'),('sd3','sd3'),('pony','sdxl'),('illustrious','sdxl'),('sdxl','sdxl'),('xl','sdxl'),('sd15','sd1.5'),('sd_turbo','sd-turbo'),
 ('sd_1.5','sd1.5'),('v1-5','sd1.5'),('1.5','sd1.5'),('animatediff','animatediff'),('svd','svd'),('cosmos','cosmos'),('mochi','mochi'),('cogvideo','cogvideo')]
ENC=[('umt5','umt5-xxl'),('t5xxl','t5-xxl'),('t5','t5-xxl'),('qwen3vl','qwen3-vl'),('qwen_3','qwen3'),('qwen3','qwen3'),('qwen_2.5','qwen2.5-vl'),('qwen2.5','qwen2.5-vl'),
 ('clip_l','clip'),('clip_g','clip'),('clip-','clip'),('clip','clip'),('llama','llama'),('mistral','mistral'),('gemma','gemma'),('byt5','byt5'),('siglip','siglip'),('dino','dino')]
def base_of(typ, name, src):
    n=name.lower(); p=src.lower()
    if typ=='vae' and n=='ae.safetensors': return 'flux1'
    if typ in ('text_encoders','clip_vision'):
        for k,v in ENC:
            if k in n: return v
    for k,v in BASES:
        if k in n or f'/{k}/' in p: return v
    return 'unsorted'
COMFY_SRC=[('/mnt/nv1/comfy','nv1',None),('/mnt/nv3/comfy/barge','barge',None),('/mnt/nv4/crucial/comfy','crucial',None),('/mnt/nv5/comfy','nv5',None),
           ('/mnt/nv4/train/Models/Image','train','checkpoints'),('/mnt/nv4/train/Models/loras','train','loras')]
COMFY_PKG={'/mnt/nv3/comfy/minimax-h3':'/mnt/nv6/comfy/packages/minimax-h3','/mnt/nv3/comfy/barge/minimax-h3':'/mnt/nv6/comfy/packages/minimax-h3-barge-configs'}
SKIP_RE=re.compile(r'(^|/)(\.cache|put_[a-z0-9_]+_here|.*\.metadata|CACHEDIR\.TAG|\.gitignore|\.gitattributes|\.last_sync|__pycache__)$')
PKG_MARK={'config.json','pipeline.json','model_index.json','README.md','tokenizer.json'}
def plan_B():
    """comfy -> /mnt/nv6/comfy/<type>/<base>/...  Loose files move one by one; an HF-style package dir (has config/pipeline json or
    nested dirs) moves as one tree; a plain grouping dir (Wan2.2/, pony/, wan/) is descended. Unknown top dirs -> misc/<host>-<dir>/."""
    acts=[]; seen={}
    def put(kind,src,dst):
        if dst in seen:
            if kind=='MOVE' and os.path.getsize(src)==os.path.getsize(seen[dst]): acts.append(('DUPCHECK_DELETE',src,dst)); return   # keeper = the moved dst
            dst=dst.replace('/mnt/nv6/comfy/','/mnt/nv6/comfy/_collide/')
        seen[dst]=src; acts.append((kind,src,dst))
    def walk(d,typ,base):
        for e in sorted(os.listdir(d)):
            ep=os.path.join(d,e)
            if SKIP_RE.search(ep) or os.path.islink(ep): continue
            if os.path.isfile(ep):
                b=base_of(typ,e,ep); b=b if b!='unsorted' else base; put('MOVE',ep,f'/mnt/nv6/comfy/{typ}/{b}/{e}')
            else:
                names=set(os.listdir(ep)); b=base_of(typ,e,ep); b=b if b!='unsorted' else base
                is_pkg=bool(names&PKG_MARK) or any(os.path.isdir(os.path.join(ep,x)) and not SKIP_RE.search(x) for x in names) or b=='unsorted'
                if is_pkg: put('MOVE_TREE',ep,f'/mnt/nv6/comfy/{typ}/{b}/{e}')
                else: walk(ep,typ,b)
    for root,host,forced in COMFY_SRC:
        if not os.path.isdir(root): continue
        for top in sorted(os.listdir(root)):
            tp=os.path.join(root,top)
            if tp in COMFY_PKG or SKIP_RE.search(tp) or os.path.islink(tp): continue
            if forced:
                if os.path.isfile(tp): put('MOVE',tp,f'/mnt/nv6/comfy/{forced}/{base_of(forced,top,tp)}/{top}')
                else: walk(tp,forced,base_of(forced,top,tp)) if not (set(os.listdir(tp))&PKG_MARK) else put('MOVE_TREE',tp,f'/mnt/nv6/comfy/{forced}/{base_of(forced,top,tp)}/{top}')
                continue
            if os.path.isfile(tp): put('MOVE',tp,f'/mnt/nv6/comfy/misc/{host}-root/{top}'); continue
            typ=TYPES.get(top)
            if typ is None: put('MOVE_TREE',tp,f'/mnt/nv6/comfy/misc/{host}-{top}'); continue
            walk(tp,typ,FORCED_BASE.get(top,'unsorted'))
    for s,d in COMFY_PKG.items():
        if os.path.exists(s): acts.append(('MOVE_TREE',s,d))
    return acts
# ───────────────────────── other phases ─────────────────────────
def plan_A(): return [('MOVE_TREE','/mnt/nv2/llm/hy4-preview','/mnt/nv6/llm/hy4-preview')]
def plan_E():
    a=[('DELETE','/mnt/nv5/.venv-sdxl','junk venv (plan E)'),
       ('DELETE','/mnt/nv3/llm/qwen-agentworld-35b-abliterated/huihui-qwen-agentworld-35b-a3b-abliterated-q8_0.gguf','broken metadata; FIXED twin kept (plan E)'),
       ('DUPCHECK_DELETE','/mnt/nv4/train/Models/LLM/mradermacher/hammer2.1-7b/Hammer2.1-7b.Q5_K_M.gguf','/mnt/nv5/llm/studio-writers/src/Hammer2.1-7b.Q5_K_M.gguf')]
    for r in ('BAAI__bge-m3','BAAI__bge-reranker-v2-m3'):     # keeper = nv3/hf-assets (the mirror symlink points there)
        d=f'/mnt/nv5/hf/{r}'; k=f'/mnt/nv3/hf-assets/{r.replace("__","/")}'
        if os.path.isdir(d) and os.path.isdir(k):
            for dp,dn,fn in os.walk(d):
                for f in fn:
                    s=os.path.join(dp,f); kk=os.path.join(k,os.path.relpath(s,d))
                    a.append(('DUPCHECK_DELETE',s,kk) if os.path.exists(kk) else ('MOVE',s,kk))
            a.append(('RMDIR_EMPTY',d,''))
    return a
SHARED=re.compile(r'(umt5|t5|vae|clip|wav2vec|lm\.binary|flax_model|pytorch_model\.bin|tokenizer)',re.I)
def plan_D():
    """same-drive duplicates on nv5/hf: (a) flattened copies inside one repo, (b) shared assets (t5/vae/clip/wav2vec) across repos.
    Pairs differing only by high_noise/low_noise or being diffusion shards of different repos are NOT considered. sha256 decides; hardlink, no path disappears."""
    files={}
    for dp,dn,fn in os.walk('/mnt/nv5/hf'):
        for f in fn:
            p=os.path.join(dp,f); st=os.stat(p)
            if st.st_size<200_000_000: continue
            files.setdefault((f,st.st_size),[]).append((st.st_ino,p))
    acts=[]
    for (f,sz),lst in files.items():
        if len({i for i,_ in lst})<2: continue
        repo=lambda p:p.split('/')[4]
        keep=sorted(lst,key=lambda x:(x[1].count('/'),x[1]))[-1][1]
        for i,p in lst:
            if p==keep or os.stat(p).st_ino==os.stat(keep).st_ino: continue
            if re.sub(r'(high|low)_noise','X',p)==re.sub(r'(high|low)_noise','X',keep) and p!=keep: continue
            if repo(p)!=repo(keep) and not SHARED.search(f): continue
            acts.append(('HARDLINK_DUP',p,keep))
    return acts
def is_raw(d): return os.path.exists(f'{d}/config.json') or os.path.exists(f'{d}/model_index.json')
def plan_C():
    """model-clustered layout, same-drive renames only. llm/ -> models/ (+ relative compat symlink llm -> models); raw+gguf pairs get raw/ gguf/."""
    a=[]
    for n in (1,2,3,4,5,6):
        d=NV[n]
        if os.path.isdir(f'{d}/llm') and not os.path.islink(f'{d}/llm'): a+= [('MV',f'{d}/llm',f'{d}/models'),('SYMLINK',f'{d}/models',f'{d}/llm')]
    pairs={3:[('qwen3-coder-next-abliterated','qwen3-coder-next-abliterated-safetensors'),('qwen-agentworld-35b-abliterated','qwen-agentworld-35b-abliterated-safetensors'),
              ('qwen35b-agent-r2-abliterated','qwen35b-agent-r2-abliterated-safetensors')],
           4:[('deepseek-v4.1-flash-gguf-vcruz305','deepseek-v4.1-flash-safetensors')]}
    for n,ps in pairs.items():
        for g,r in ps:
            m=g.replace('-gguf-vcruz305','')
            a+=[('MV',f'{NV[n]}/models/{g}',f'{NV[n]}/models/{m}.tmp-gguf'),('MV',f'{NV[n]}/models/{r}',f'{NV[n]}/models/{m}/raw'),
                ('MV',f'{NV[n]}/models/{m}.tmp-gguf',f'{NV[n]}/models/{m}/gguf')]
    if os.path.isdir('/mnt/nv5/hf'):
        for r in sorted(os.listdir('/mnt/nv5/hf')):
            if r.startswith('BAAI__'): continue                       # phase E folds these into nv3/hf-assets
            a.append(('MV',f'/mnt/nv5/hf/{r}',f'/mnt/nv5/models/{r}/'+('gguf' if 'GGUF' in r.upper() and not is_raw(f'/mnt/nv5/hf/{r}') else 'raw')))
        a+=[('RMDIR_EMPTY','/mnt/nv5/hf',''),('SYMLINK','/mnt/nv5/models','/mnt/nv5/hf')]   # NOTE: old hf/<repo>/x paths become hf/<repo>/raw/x
    a+=[('MV','/mnt/nv5/models/studio-writers/src/Qwen__Qwen3.6-35B-A3B','/mnt/nv5/models/Qwen__Qwen3.6-35B-A3B/raw'),
        ('MV','/mnt/nv5/models/studio-writers/Qwen3.6-35B-A3B-Q8_0.gguf','/mnt/nv5/models/Qwen__Qwen3.6-35B-A3B/gguf/Qwen3.6-35B-A3B-Q8_0.gguf'),
        ('MV','/mnt/nv5/models/studio-writers/src/zai-org__GLM-4.7-Flash','/mnt/nv5/models/zai-org__GLM-4.7-Flash/raw'),
        ('MV','/mnt/nv5/models/studio-writers/src/Hammer2.1-7b.Q5_K_M.gguf','/mnt/nv5/models/Hammer2.1-7b/gguf/Hammer2.1-7b.Q5_K_M.gguf'),
        ('RMDIR_EMPTY','/mnt/nv5/models/studio-writers/src',''),('RMDIR_EMPTY','/mnt/nv5/models/studio-writers',''),
        ('MV','/mnt/nv5/models/qwen3vl/Qwen3-VL-8B-Instruct','/mnt/nv5/models/Qwen__Qwen3-VL-8B-Instruct/raw'),
        ('MV','/mnt/nv5/models/qwen3vl/qwen3vl-ov','/mnt/nv5/models/Qwen__Qwen3-VL-8B-Instruct/openvino'),('RMDIR_EMPTY','/mnt/nv5/models/qwen3vl',''),
        ('MV','/mnt/nv5/models/dev/Qwen3-32B-Q8_0.gguf','/mnt/nv5/models/Qwen__Qwen3-32B/gguf/Qwen3-32B-Q8_0.gguf'),
        ('MV','/mnt/nv5/models/dev/TheDrummer_Cydonia-24B-v4.3-Q5_K_M.gguf','/mnt/nv5/models/TheDrummer__Cydonia-24B-v4.3/gguf/TheDrummer_Cydonia-24B-v4.3-Q5_K_M.gguf'),
        ('MV','/mnt/nv5/models/dev','/mnt/nv5/data/experiments/homunculus-ggufs')]
    T='/mnt/nv4/train/Models/LLM'
    if os.path.isdir(T):
        for org in ('google','ibm-granite','mradermacher','Qwen','qwen','SherlockID365'):
            p=f'{T}/{org}'
            if not os.path.isdir(p): continue
            subs=[s for s in os.listdir(p) if os.path.isdir(f'{p}/{s}')]
            if subs and not is_raw(p):
                for s in subs:
                    sp=f'{p}/{s}'
                    if not any(f.endswith(('.safetensors','.gguf','.bin','.pt')) for dp,dn,fn in os.walk(sp) for f in fn): continue   # emptied by E (hammer) -> left for F
                    a.append(('MV',sp,f'/mnt/nv4/models/{org}__{s}/'+('raw' if is_raw(sp) else 'gguf')))
            else: a.append(('MV',p,f'/mnt/nv4/models/{org}/'+('raw' if is_raw(p) else 'gguf')))
        if os.path.isdir(f'{T}/Qwen3-VL-8B-Caption'): a.append(('MV',f'{T}/Qwen3-VL-8B-Caption','/mnt/nv4/models/Qwen3-VL-8B-Caption/raw'))
        if os.path.isdir(f'{T}/capdir'): a.append(('MV',f'{T}/capdir','/mnt/nv4/data/experiments/capdir'))
    return a
def plan_F():
    a=[]
    for host,root in (('crucial','/mnt/nv4/crucial'),('train','/mnt/nv4/train'),('m7-barge','/mnt/nv3/misc')):
        if os.path.isdir(root): a.append(('MV',root,f'{drive_of(root)}/archive/{host}-2026-09'))
    for d in ('/mnt/nv3/comfy/barge','/mnt/nv1/comfy','/mnt/nv5/comfy'): a.append(('RMDIR_EMPTY',d,''))
    return a
def plan_G(): return [('README','','')]   # catalog2.sh / migrate-manifest.py / manifest2.sh are run by reorg-run.sh
PLANS={'A':plan_A,'E':plan_E,'D':plan_D,'B':plan_B,'C':plan_C,'F':plan_F,'G':plan_G}
# ───────────────────────── executor ─────────────────────────
def journal(): return set(l.rstrip('\n') for l in open(f'{H}/journal.tsv')) if os.path.exists(f'{H}/journal.tsv') else set()
def done(key): open(f'{H}/journal.tsv','a').write(key+'\n')
def run(cmd): return subprocess.run(cmd,shell=isinstance(cmd,str),capture_output=True,text=True)
def drives_ok(*paths):
    devs=json.load(open(f'{H}/devs.json'))
    for p in paths:
        d=drive_of(p)
        if not d: continue
        if not os.path.ismount(d): return f'FAIL:{d} not mounted'
        if str(os.stat(d).st_dev)!=str(devs.get(d)): return f'FAIL:{d} st_dev changed since plan (remounted/different device)'
    return None
def has_real_files(d):
    for dp,dn,fn in os.walk(d):
        for f in fn:
            if not SKIP_RE.search(os.path.join(dp,f)): return os.path.join(dp,f)
    return None
def do(kind,src,dst,dry):
    if kind in ('MOVE','MOVE_TREE','MOVE_TREE_MERGE'):
        if not os.path.lexists(src): return 'skip:missing'
        if kind=='MOVE' and os.path.isfile(dst):        # source still here => dst is a partial copy from an interrupted run; rsync --inplace resumes it
            if os.path.getsize(dst)>os.path.getsize(src): return 'FAIL:dst exists and is larger than src'
        elif kind=='MOVE' and os.path.lexists(dst): return 'FAIL:dst exists (not a file)'
        if same_fs(src,dst) and kind!='MOVE_TREE_MERGE':
            if os.path.lexists(dst): return 'FAIL:dst exists'
            if dry: return 'would rename'
            os.makedirs(os.path.dirname(dst),exist_ok=True); os.rename(src,dst); return 'renamed'
        need=du(src)
        if free(existing_parent(dst))<need+20e9: return f'FAIL:no space for {need/1e9:.0f}G'
        if dry: return f'would rsync {need/1e9:.1f}G'
        os.makedirs(os.path.dirname(dst),exist_ok=True)
        r=run(['rsync','-aH','--partial','--inplace',src if kind=='MOVE' else src+'/',dst])
        if r.returncode: return 'FAIL:rsync '+r.stderr[-200:]
        v=run(['rsync','-aHcin',src if kind=='MOVE' else src+'/',dst])
        if v.returncode or any(l and not l.startswith('.d') for l in v.stdout.splitlines()): return 'FAIL:verify '+v.stdout[:200]
        if drives_ok(src,dst): return 'FAIL:drive state changed after copy; source kept'
        (shutil.rmtree if os.path.isdir(src) else os.remove)(src); return f'moved {need/1e9:.1f}G verified'
    if kind=='MV':
        if not os.path.lexists(src): return 'skip:missing'
        if os.path.lexists(dst): return 'FAIL:dst exists'
        if not same_fs(src,dst): return 'FAIL:MV across filesystems'
        if dry: return 'would rename'
        os.makedirs(os.path.dirname(dst),exist_ok=True); os.rename(src,dst); return 'renamed'
    if kind in ('DUPCHECK_DELETE','HARDLINK_DUP'):
        if not os.path.exists(src): return 'skip:missing'
        if not os.path.exists(dst): return 'FAIL:keeper missing'
        if os.path.getsize(src)!=os.path.getsize(dst): return 'FAIL:size differs'
        if os.stat(src).st_ino==os.stat(dst).st_ino and os.stat(src).st_dev==os.stat(dst).st_dev: return 'skip:already linked'
        if dry: return 'would sha256+'+('delete' if kind=='DUPCHECK_DELETE' else 'hardlink')
        if sha(src)!=sha(dst): return 'FAIL:sha differs (NOT a duplicate)'
        if kind=='DUPCHECK_DELETE': os.remove(src); return 'deleted (sha ok)'
        if not same_fs(src,dst): return 'FAIL:hardlink across filesystems'
        tmp=src+'.lnk'; 
        if os.path.lexists(tmp): os.remove(tmp)
        os.link(dst,tmp); os.replace(tmp,src); return 'hardlinked (sha ok)'
    if kind=='DELETE':
        if not os.path.lexists(src): return 'skip:missing'
        if dry: return f'would delete {du(src)/1e9:.1f}G'
        (shutil.rmtree if os.path.isdir(src) and not os.path.islink(src) else os.remove)(src); return 'deleted'
    if kind=='RMDIR_EMPTY':
        if not os.path.isdir(src): return 'skip:missing'
        left=has_real_files(src)
        if left: return 'skip:not empty '+left
        if dry: return 'would rmdir (only placeholders/metadata inside)'
        shutil.rmtree(src); return 'rmdir'
    if kind=='SYMLINK':
        if os.path.lexists(dst): return 'skip:exists' if os.path.islink(dst) and os.path.realpath(dst)==os.path.realpath(src) else 'FAIL:dst exists and is not the intended link'
        if dry: return 'would symlink'
        os.symlink(rel_symlink(src,dst),dst); return 'symlinked'
    if kind=='MKDIR':
        if dry: return 'would mkdir'
        os.makedirs(src,exist_ok=True); return 'mkdir'
    if kind=='RUN':
        if dry: return 'would run'
        r=run(src); return f'rc={r.returncode}'
    if kind=='README':
        if dry: return 'would write READMEs'
        for n in range(1,7):
            d=NV[n]; top=[f for f in sorted(os.listdir(d)) if not f.startswith('lost')]
            open(f'{d}/README.md','a').write(f'\n## reorg 2026-09-29\nlayout: models/<name>/{{raw,gguf}} (llm -> models symlink), comfy/<type>/<base>/ lives on nv6, archive/<host>-date. top: {" ".join(top)}\n')
        return 'READMEs appended'
    return 'FAIL:unknown kind'
BUSY="pgrep -f '[v]oice-stack.sh|[p]ython-lanes.sh|[a]gent-swarm.sh|[h]f download|[m]anifest.sh|[c]atalog.sh|[r]unqueue.sh'"
def main():
    if len(sys.argv)<2: print(__doc__); return
    if sys.argv[1]=='plan':
        json.dump({NV[n]:os.stat(NV[n]).st_dev for n in range(1,7) if os.path.ismount(NV[n])},open(f'{H}/devs.json','w'))
        tot={}
        for ph,fn in PLANS.items():
            acts=fn()
            with open(f'{H}/{ph}.tsv','w') as f:
                for k,s,d in acts: f.write(f'{k}\t{s}\t{d}\n')
            mv=sum(du(s) for k,s,d in acts if k.startswith('MOVE') and os.path.exists(s) and not same_fs(s,d))
            dl=sum(os.path.getsize(s) for k,s,d in acts if k in('DUPCHECK_DELETE','HARDLINK_DUP') and os.path.exists(s))
            de=sum(du(s) for k,s,d in acts if k=='DELETE' and os.path.exists(s))
            tot[ph]=(len(acts),mv,dl,de); log(f'phase {ph}: {len(acts)} actions; cross-drive copy {mv/1e9:.0f}G; dup-reclaim {dl/1e9:.0f}G; delete {de/1e9:.0f}G')
        B=[l.rstrip('\n').split('\t') for l in open(f'{H}/B.tsv')]; cnt={}
        for k,s,d in B:
            if k.startswith('MOVE'): key='/'.join(d.split('/')[3:6]); cnt[key]=cnt.get(key,0)+1
        with open(f'{H}/SUMMARY.txt','w') as f:
            f.write(json.dumps({k:{'actions':v[0],'copyG':round(v[1]/1e9),'dupG':round(v[2]/1e9),'delG':round(v[3]/1e9)} for k,v in tot.items()},indent=1)+'\n\ncomfy targets (type/base: entries)\n')
            for k in sorted(cnt): f.write(f'{cnt[k]:5d}  {k}\n')
            f.write('\nfree now: '+' '.join(f'nv{n}={free(NV[n])/1e9:.0f}G' for n in range(1,7))+'\n')
        print(open(f'{H}/SUMMARY.txt').read()); return
    if sys.argv[1]=='apply':
        ph=sys.argv[2]; dry='-n' in sys.argv; J=journal(); ok=fail=skip=0
        busy=subprocess.run(BUSY,shell=True,capture_output=True,text=True).stdout.split()
        if busy and ph in ('C','F','G') and '--force' not in sys.argv: log(f'REFUSED: phase {ph} renames trees the running download/index jobs write to (pids {busy}); wait for VOICE-DONE/LANES-DONE or pass --force'); return
        acts=[l.rstrip('\n').split('\t') for l in open(f'{H}/{ph}.tsv')]
        need=sum(du(s) for k,s,d in acts if k.startswith('MOVE') and os.path.exists(s) and not same_fs(s,d))
        if need and free('/mnt/nv6')<need+30e9: log(f'REFUSED: phase {ph} needs {need/1e9:.0f}G on nv6, only {free("/mnt/nv6")/1e9:.0f}G free'); return
        for k,s,d in acts:
            key=f'{ph}\t{k}\t{s}'
            if key in J: continue
            r=drives_ok(s,d) if k!='RUN' else None
            if r is None:
                try: r=do(k,s,d,dry)
                except Exception as e: r=f'FAIL:exception {type(e).__name__}: {e}'; log(traceback.format_exc().splitlines()[-1])
            log(f'[{ph}] {k} {s} -> {d}: {r}')
            if r.startswith('FAIL'): fail+=1
            elif r.startswith('skip'): skip+=1
            elif not dry: done(key); ok+=1
            else: ok+=1
            if r.startswith('FAIL') and ('not mounted' in r or 'st_dev changed' in r): log('ABORT: drive state problem; fix mounts and re-run'); break
        log(f'phase {ph} {"DRY " if dry else ""}done: {ok} ok, {skip} skipped, {fail} failed'); log(' '.join(f'nv{n}={free(NV[n])/1e9:.0f}G' for n in range(1,7)))
main()
