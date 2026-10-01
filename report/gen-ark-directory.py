#!/usr/bin/env python3
"""report/gen-ark-directory.py [out.html] [--private] — progressive-disclosure directory of what the ark manifest references.
Built from manifest/*.tsv only (public); --private also folds in manifest-private/. Self-contained dark HTML, no network, no local paths."""
import csv,os,sys,html,re,datetime,collections
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'); OUT=next((a for a in sys.argv[1:] if not a.startswith('--')),os.path.join(R,'docs','directory.html')); PRIV='--private' in sys.argv
def esc(s): return html.escape(str(s))
def rows(f):
    out=[]
    for base in (['manifest','manifest-private'] if PRIV else ['manifest']):
        p=os.path.join(R,base,f)
        if os.path.exists(p):
            with open(p) as fh:
                for r in csv.DictReader(fh,delimiter='\t'):
                    if r and not list(r.values())[0].startswith('#'): r['_private']=(base!='manifest'); out.append(r)
    return out
def lines(f):
    p=os.path.join(R,'manifest',f); return [l.strip() for l in open(p)] if os.path.exists(p) else []
NAMES={'inference':'Inference engines','decision-models':'Decision models (Jev-style)','training':'Training, fine-tuning and RL','training-diffusion':'Diffusion and video LoRA trainers','quantisation':'Quantisation and merging','conversion':'Conversion and abliteration','eval-data':'Evaluation and data tooling','multi-box':'Multi-box serving and clustering','ml-frameworks':'ML frameworks and libraries','model-source':'Model source repos','comfyui':'ComfyUI and custom nodes','image-video':'Image, video and vision','realtime-diffusion':'Realtime diffusion','media-tooling':'Media tooling (audio, video, image)','audio-restoration':'Audio editing and restoration','voice':'Voice assistant stack','agents':'Agent harnesses and frameworks','multi-agent':'Multi-agent and swarm frameworks','orchestration':'Agent orchestration and workflows','agent-protocols':'Agent protocols (MCP, A2A, AG-UI)','coding-agents':'Parallel coding agents and skills','fronts-eval':'Self-hosted fronts, guardrails and eval','retrieval':'Retrieval and documents','dev-infra':'Island dev infrastructure','dev-toolchains':'Developer toolchains (sources)','offline-reference':'Offline reference tooling','embedded':'Embedded firmware','edge-vision':'Edge vision (Grove Vision AI V2)','games':'Games','3d':'3D modelling and capture','circuit-design':'Circuit design and HDL','genome':'Genome analysis','bci-biosignals':'BCI, EEG and biosignals','gap-analysis':'Other'}
def node(title,meta='',body='',cls=''): return f"<details class='n {cls}'><summary><span class='t'>{title}</span><span class='m'>{meta}</span></summary><div class='b'>{body}</div></details>"
def leaf(title,meta='',detail=''): return f"<div class='leaf'><span class='t'>{title}</span><span class='m'>{meta}</span>{('<div class=d>'+detail+'</div>') if detail else ''}</div>"
def kv(pairs): return ' '.join(f"<span class='kv'><b>{esc(k)}</b> {esc(v)}</span>" for k,v in pairs if v)
def plabel(r): return " <i class='tag'>private</i>" if r.get('_private') else ''
def rlabel(u): return re.sub(r'^https?://(github\.com/|gitlab\.com/|gitlab\.[a-z.]+/)?','',u)
repos=rows('repos.tsv'); bycat=collections.OrderedDict()
for r in repos: bycat.setdefault(NAMES.get(r['category'],r['category']),[]).append(r)
order=[v for v in NAMES.values()]; bycat=collections.OrderedDict(sorted(bycat.items(),key=lambda kv:(order.index(kv[0]) if kv[0] in order else 99)))
rsec=''.join(node(esc(c), f"{len(v)} repos", ''.join(leaf(f"<a href='{esc(r['url'])}'>{esc(rlabel(r['url']))}</a>"+plabel(r), '', kv([('note',r.get('note',''))])) for r in sorted(v,key=lambda r:rlabel(r['url']).lower()))) for c,v in bycat.items())
models=rows('models.tsv'); kinds=collections.OrderedDict((k,[]) for k in ('raw','gguf','hf-asset','comfy'))
for m in models: kinds.setdefault(m['kind'],[]).append(m)
KN={'raw':'Model picks: raw releases (newest of each line; re-quant source)','gguf':'Model picks: GGUF quants (llama.cpp)','hf-asset':'Dependencies: helper weights that mirrored code downloads at first run (not picks)','comfy':'Dependencies: ComfyUI assets (checkpoints, LoRAs, VAEs, ControlNets)'}
msec=''.join(node(esc(KN.get(k,k)), f"{len(v)}", ''.join(leaf(f"<a href='https://huggingface.co/{esc(m['hf_id'])}'>{esc(m['hf_id'])}</a>"+plabel(m), '', kv([('include',m.get('include','')),('note',m.get('note',''))])) for m in sorted(v,key=lambda m:m['hf_id'].lower()))) for k,v in kinds.items() if v)
ds=rows('datasets.tsv'); dsec=''.join(leaf(f"<a href='https://huggingface.co/datasets/{esc(d['hf_id'])}'>{esc(d['hf_id'])}</a>"+plabel(d), '', kv([('include',d.get('include','')),('note',d.get('note',''))])) for d in sorted(ds,key=lambda d:d['hf_id'].lower()))
ref=rows('reference.tsv')
def rtitle(r):
    name=r['pattern_or_target'] if r['kind']!='url' else re.sub(r'\{REL\}','<release>',r['source'].split('/')[-1])
    return (esc(r['note']) if r.get('note') else esc(name))
def rmeta(r):
    name=r['pattern_or_target'] if r['kind']!='url' else re.sub(r'\{REL\}','<release>',r['source'].split('/')[-1])
    return f"{esc(r['kind'])} · {esc(name)}" if r.get('note') else esc(r['kind'])
import collections as _c
def rgroup(r):
    t=r['pattern_or_target']; n=r.get('note','').lower()
    if r['kind'] in ('zim','zim-set'): return 'Offline knowledge (Kiwix ZIM)'
    if t.startswith('genome') or 'grch38' in n or 'ensembl' in n or 'ncbi' in n or 'gnomad' in n: return 'Genome reference data (GRCh38)'
    if 'leitner' in n or 'arxiv.org' in r['source']: return 'Paper shelf (Leitner Reference Library)'
    if 'agner' in n or 'manual' in n or 'instruction' in n: return 'Hardware manuals and references'
    return 'Other reference files'
rg=_c.OrderedDict()
for r in ref: rg.setdefault(rgroup(r),[]).append(r)
def rleaf(r):
    t=r.get('note','') or r['source']; t=re.sub(r';\s*Leitner Reference Library shelf','',t)
    return leaf(esc(t), rmeta(r), kv([('source',r['source']),('lands in',r['pattern_or_target'] if r['kind']=='url' else '')]))
refsec=''.join(node(esc(g), f"{len(v)}", ''.join(rleaf(r) for r in v)) for g,v in rg.items())
assets=rows('assets.tsv'); asec=''.join(leaf(f"{esc(a['source'])} · {esc(a['type'])}", esc(a['license']), kv([('selection',a['selection'])])) for a in assets)
ct=rows('containers.tsv'); ctsec=''.join(leaf(f"<span class='mono'>{esc(c['image'])}</span>", '', kv([('note',c.get('note',''))])) for c in ct)
pypi=[l for l in lines('pypi-extra.txt') if l and not l.startswith('#')]; apt=[l.lstrip('# ') for l in lines('apt.txt') if l.strip()]
psec=''.join(leaf(f"<span class='mono'>{esc(p)}</span>") for p in sorted(pypi,key=str.lower)); aptsec=''.join(leaf(esc(a)) for a in apt)
counts=dict(repos=len(repos),models=len(models),datasets=len(ds),reference=len(ref),containers=len(ct),pypi=len(pypi))
today=datetime.date.today().isoformat()
CSS="""
:root{--bg:#0f1317;--panel:#161c22;--panel2:#1c242c;--ink:#dfe6e3;--ink2:#93a19b;--rule:#2a343b;--accent:#5fd3c3;--accent2:#1c3a37;--warn:#e0955a}
*{box-sizing:border-box} html{color-scheme:dark} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px clamp(16px,3vw,32px) 64px} h1{font-size:clamp(26px,4vw,38px);margin:0 0 4px;letter-spacing:-.01em}
.eyebrow{font:500 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)} .lede{color:var(--ink2);max-width:66ch;margin:8px 0 18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin-bottom:18px} .tile{background:var(--panel);padding:12px 14px} .tile b{display:block;font-size:24px;font-variant-numeric:tabular-nums} .tile span{color:var(--ink2);font-size:12px}
.bar{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 0;border-bottom:1px solid var(--rule);margin-bottom:14px}
input[type=search]{flex:1 1 260px;font:14px system-ui;padding:8px 10px;background:var(--panel);color:var(--ink);border:1px solid var(--rule);border-radius:4px} input:focus{outline:2px solid var(--accent);outline-offset:1px}
button{font:500 12px system-ui;padding:7px 10px;background:var(--panel);color:var(--ink2);border:1px solid var(--rule);border-radius:4px;cursor:pointer} button:hover{color:var(--ink);border-color:var(--accent)} #hits{color:var(--ink2);font-size:12px}
details.n{border-left:2px solid var(--rule);margin:2px 0;padding-left:10px} details.n[open]{border-color:var(--accent2)} details.top{border-left:none;padding-left:0;margin:0 0 10px} details.top>summary{background:var(--panel);padding:10px 12px;border:1px solid var(--rule);border-radius:4px;font-size:16px}
summary{cursor:pointer;display:flex;justify-content:space-between;gap:12px;align-items:baseline;padding:4px 6px;border-radius:3px;list-style:none} summary::-webkit-details-marker{display:none} summary::before{content:"▸";color:var(--accent);margin-right:8px;display:inline-block;width:12px} details[open]>summary::before{content:"▾"} summary:hover{background:var(--panel2)}
.t{flex:1 1 auto;min-width:0;overflow-wrap:anywhere} .m{color:var(--ink2);font-size:12.5px;font-variant-numeric:tabular-nums;white-space:nowrap;font-family:ui-monospace,Menlo,monospace}
.b{padding:2px 0 6px 14px} .leaf{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;padding:3px 6px;border-radius:3px;font-size:14px} .leaf:hover{background:var(--panel2)} .leaf .t{flex:1 1 60%} .leaf .d{flex-basis:100%;color:var(--ink2);font-size:12px;padding:2px 0 2px 20px;display:none} .leaf.show .d{display:block} .leaf.has{cursor:pointer}
.kv{display:inline-block;margin-right:12px} .kv b{color:var(--ink);font-weight:500;margin-right:4px} .mono{font-family:ui-monospace,Menlo,monospace;font-size:13px} a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
.tag{font-style:normal;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--warn);border:1px solid var(--warn);padding:0 5px;border-radius:3px;margin-left:6px} .note{color:var(--ink2);font-size:13px;margin:4px 0 8px;border-left:3px solid var(--accent);padding:4px 10px}
.hit>summary .t,.leaf.hit .t{color:var(--accent)} .hide{display:none!important} footer{color:var(--ink2);font-size:12px;border-top:1px solid var(--rule);padding-top:12px;margin-top:24px}
"""
JS="""(function(){var q=document.getElementById('q'),hits=document.getElementById('hits');
document.querySelectorAll('.leaf').forEach(function(l){if(l.querySelector('.d')){l.classList.add('has');l.tabIndex=0;l.addEventListener('click',function(e){if(e.target.tagName==='A')return;l.classList.toggle('show')})}});
function all(o){document.querySelectorAll('details').forEach(function(d){d.open=o})} document.getElementById('exp').onclick=function(){all(true)};document.getElementById('col').onclick=function(){all(false)};
var timer;q.addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(run,120)});
function run(){var t=q.value.trim().toLowerCase();document.querySelectorAll('.hit').forEach(function(e){e.classList.remove('hit')});document.querySelectorAll('.hide').forEach(function(e){e.classList.remove('hide')});if(!t){hits.textContent='';return}
var n=0;document.querySelectorAll('.leaf').forEach(function(l){var ok=l.textContent.toLowerCase().indexOf(t)>-1;if(ok){n++;l.classList.add('hit');var p=l.parentElement;while(p){if(p.tagName==='DETAILS'){p.open=true;p.classList.add('hit')}p=p.parentElement}}else l.classList.add('hide')});
document.querySelectorAll('details.n').forEach(function(d){if(!d.classList.contains('hit')){if(d.querySelector('summary').textContent.toLowerCase().indexOf(t)>-1){d.classList.add('hit');d.open=true;var p=d.parentElement;while(p){if(p.tagName==='DETAILS'){p.open=true;p.classList.add('hit')}p=p.parentElement};d.querySelectorAll('.hide').forEach(function(e){e.classList.remove('hide')});n+=d.querySelectorAll('.leaf').length}else d.classList.add('hide')}});hits.textContent=n+' matches'}})();"""
page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ark directory</title><style>{CSS}</style></head><body><div class="wrap">
<span class="eyebrow">ark · manifest of references for an offline AI mirror · generated {today}{' · includes private overlay' if PRIV else ''}</span>
<h1>What ark references</h1>
<p class="lede">The full manifest as a drill-down: source repositories by purpose, model weights by kind, datasets, reference data, assets, containers and packages. Every entry links to its upstream. This page is generated from <span class="mono">manifest/*.tsv</span> by <span class="mono">report/gen-ark-directory.py</span>; nothing here is a local path.</p>
<div class="tiles"><div class="tile"><b>{counts['repos']}</b><span>source repos · {len(bycat)} categories</span></div><div class="tile"><b>{counts['models']}</b><span>weight repos</span></div><div class="tile"><b>{counts['datasets']}</b><span>datasets</span></div><div class="tile"><b>{counts['reference']}</b><span>reference sets</span></div><div class="tile"><b>{counts['containers']}</b><span>container images</span></div><div class="tile"><b>{counts['pypi']}</b><span>extra PyPI packages</span></div></div>
<div class="bar"><input type="search" id="q" placeholder="Search names, notes, categories" aria-label="Search"><button id="exp">expand all</button><button id="col">collapse all</button><span id="hits"></span></div>
{node("Source repositories", f"{counts['repos']} · {len(bycat)} categories", "<p class='note'>Latest-only shallow clones. Categories are by purpose; add a line to <span class='mono'>manifest/repos.tsv</span> to contribute.</p>"+rsec, cls='top')}
{node("Model weights", f"{counts['models']}", "<p class='note'><b>Picks</b> follow a newest-only policy: one current model per line (the Sept 2026 set: DeepSeek V4.1, GLM-5.3, Kimi K2.7, Qwen3.8, MiMo V2.6, Nemotron 3 Ultra, Ornith 1.5, Mistral Medium 3.5, Muse-Glimmer, plus decision models). <b>Dependencies</b> are not picks: they are the exact checkpoints that mirrored code loads at first run (tokenizer base models, CLIP/SigLIP encoders, whisper, bge, Comfy node weights), so some are deliberately old. <span class='mono'>include</span> = the glob patterns actually fetched.</p>"+msec, cls='top')}
{node("Datasets", f"{counts['datasets']}", dsec, cls='top')}
{node("Reference data", f"{counts['reference']}", "<p class='note'>Kiwix ZIMs (latest match of a pattern wins), DevDocs sets, GRCh38 genome references with <span class='mono'>{{REL}}</span> resolved to the current Ensembl release.</p>"+refsec, cls='top')}
{node("CC0 assets", f"{len(assets)} sources", asec, cls='top')}
{node("Container images", f"{counts['containers']}", ctsec, cls='top')}
{node("Extra PyPI packages", f"{counts['pypi']}", "<p class='note'>Pulled beyond the repos' own requirements, into every wheel lane that has a build.</p>"+psec, cls='top')}
{node("apt and interpreters", f"{len(apt)} notes", aptsec, cls='top')}
<footer>ark: <span class="mono">manifest/</span> is data, <span class="mono">fetch/</span> gets it, <span class="mono">verify/</span> proves it, <span class="mono">report/</span> renders it. Contributions: one TSV line per reference; CI checks that it resolves.</footer></div><script>{JS}</script></body></html>"""
os.makedirs(os.path.dirname(OUT),exist_ok=True); open(OUT,'w').write(page); print(f'{OUT}: {len(page)//1024} KB, {counts}')
