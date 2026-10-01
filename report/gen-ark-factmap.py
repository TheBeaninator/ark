#!/usr/bin/env python3
"""report/gen-ark-factmap.py OUTDIR — progressive-disclosure text directory of the manifest for agents and for factmap ingest.
OUTDIR/INDEX.md (one line per category with counts) + OUTDIR/<category>.md (one line per entry: name, kind, note).
Reads manifest/ and, with --private, manifest-private/ too. Pair with tools/factmap-ingest-ark.sh to load it as `cached` facts."""
import csv,os,sys,re,collections
PRIV='--private' in sys.argv; args=[a for a in sys.argv[1:] if not a.startswith('--')]; out=args[0] if args else 'ark-directory'
os.makedirs(out,exist_ok=True)
def rows(f):
    r=[]
    for d in ('manifest',)+(('manifest-private',) if PRIV else ()):
        p=f'{d}/{f}'
        if os.path.exists(p): r+=list(csv.DictReader(open(p),delimiter='\t'))
    return r
NAMES={'inference':'Inference engines','decision-models':'Decision models (Jev-style)','training':'Training, fine-tuning and RL','training-diffusion':'Diffusion and video LoRA trainers','quantisation':'Quantisation and merging','conversion':'Conversion and abliteration','eval-data':'Evaluation and data tooling','multi-box':'Multi-box serving and clustering','ml-frameworks':'ML frameworks and libraries','model-source':'Model source repos','comfyui':'ComfyUI and custom nodes','image-video':'Image, video and vision','realtime-diffusion':'Realtime diffusion','media-tooling':'Media tooling','audio-restoration':'Audio editing and restoration','voice':'Voice assistant stack','agents':'Agent harnesses and frameworks','multi-agent':'Multi-agent and swarm frameworks','orchestration':'Agent orchestration and workflows','agent-protocols':'Agent protocols (MCP, A2A, AG-UI)','coding-agents':'Parallel coding agents and skills','fronts-eval':'Self-hosted fronts, guardrails and eval','retrieval':'Retrieval and documents','dev-infra':'Island dev infrastructure','netboot':'Network boot and node provisioning','dev-toolchains':'Developer toolchains','offline-reference':'Offline reference tooling','embedded':'Embedded firmware','edge-vision':'Edge vision (Grove Vision AI V2)','games':'Games','3d':'3D modelling and capture','circuit-design':'Circuit design and HDL','genome':'Genome analysis','bci-biosignals':'BCI, EEG and biosignals'}
def repo_name(u): return re.sub(r'^https?://(www\.)?','',u).rstrip('/')
def src_dir(u): return re.sub(r'^https?://','',u).replace('/','__').removesuffix('.git')
cats=collections.OrderedDict()
for r in rows('repos.tsv'):
    cats.setdefault(r['category'],[]).append(f"- {repo_name(r['url'])}  →  $ARK_SOFTWARE/src/{src_dir(r['url'])}" + (f"  — {r['note']}" if r.get('note') else ''))
sections=[]
for c,lines in cats.items():
    t=NAMES.get(c,c); p=f'{out}/repos-{c}.md'
    open(p,'w').write(f"# {t} (`{c}`): {len(lines)} repos\nShallow clones under $ARK_SOFTWARE/src/ (nv2: /mnt/nv2/software/src). Node repos carry node_modules/.\n\n"+'\n'.join(lines)+'\n')
    sections.append((f'repos-{c}',t,len(lines)))
m=rows('models.tsv'); byk=collections.OrderedDict()
for r in m: byk.setdefault(r['kind'],[]).append(r)
KIND={'raw':'Raw Hugging Face releases ($ARK_MODELS/<Org__Repo>/raw/)','gguf':'GGUF quants for llama.cpp ($ARK_MODELS/<Org__Repo>/gguf/)','hf-asset':'Helper weights mirrored code downloads at first run ($ARK_HF_ASSETS/<org>/<repo>/)','comfy':'ComfyUI assets (comfy/<type>/<base>/)'}
for k,rs in byk.items():
    p=f'{out}/models-{k}.md'; cols=[c for c in rs[0].keys() if c not in ('kind',)]
    open(p,'w').write(f"# Models: {KIND.get(k,k)}: {len(rs)} entries\n\n"+'\n'.join('- '+'  '.join(f"{c}={r[c]}" for c in cols if r.get(c)) for r in rs)+'\n')
    sections.append((f'models-{k}',f'Models: {k}',len(rs)))
for f,title,hint in (('datasets.tsv','Datasets','$ARK_DATA/datasets/<org__name>/'),('reference.tsv','Reference data (Kiwix ZIMs, genome, papers, ISOs)','$ARK_DATA/reference/ ; ISOs in $ARK_SOFTWARE/binaries/iso/'),('assets.tsv','CC0 assets','$ARK_DATA/assets/'),('containers.tsv','Container images','$ARK_SOFTWARE/containers/ (docker load -i)')):
    rs=rows(f)
    if not rs: continue
    n=f.split('.')[0]; p=f'{out}/{n}.md'
    open(p,'w').write(f"# {title}: {len(rs)} entries\nOn disk: {hint}\n\n"+'\n'.join('- '+'  '.join(f"{c}={r[c]}" for c in r if r.get(c)) for r in rs)+'\n')
    sections.append((n,title,len(rs)))
for f,title in (('pypi-extra.txt','Extra PyPI packages (wheel lanes cp312/cp313/cp314 under $ARK_SOFTWARE/wheels*)'),('apt.txt','Apt mirror description (nv4: /mnt/nv4/ubuntu-mirror, flat repos, deb [trusted=yes] file:... ./)')):
    ls=[l.rstrip() for l in open(f'manifest/{f}') if l.strip()]
    n=f.split('.')[0]; open(f'{out}/{n}.md','w').write(f"# {title}\n\n"+'\n'.join(('- '+l if not l.startswith('#') else l.lstrip('# ')) for l in ls)+'\n'); sections.append((n,title.split(' (')[0],len([l for l in ls if not l.startswith('#')])))
idx=["# Ark directory (what the offline mirror holds, by category)","Each line is a file in this directory; open one to see every entry with its on-disk path. Paths use ark.env names: ARK_SOFTWARE=/mnt/nv2/software, ARK_MODELS=/mnt/nv3/llm (+nv1), ARK_HF_ASSETS=/mnt/nv3/hf-assets, ARK_DATA=/mnt/nv4/data (+nv2, nv6).",""]
idx+=[f"- {s}.md — {t} ({n})" for s,t,n in sections]
open(f'{out}/INDEX.md','w').write('\n'.join(idx)+'\n')
print(f'{out}: {len(sections)} files, {sum(n for _,_,n in sections)} entries')
