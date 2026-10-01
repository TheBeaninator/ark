#!/usr/bin/env python3
"""gen-directory.py inventory.json out.html [ark-dir] — progressive-disclosure directory of everything on the Pod's drives.
Self-contained dark-mode HTML: inline CSS/JS, system fonts, no network. Nested <details> tree, search that opens matching branches, sizes and counts on every node."""
import json,sys,os,csv,html,re,datetime
inv=json.load(open(sys.argv[1])); ARK=sys.argv[3] if len(sys.argv)>3 else os.path.expanduser('~/Code/ark')
def esc(s): return html.escape(str(s))
def gb(b): return f"{b/1e12:.2f} TB" if b>=1e12 else (f"{b/1e9:.1f} GB" if b>=1e9 else (f"{b/1e6:.0f} MB" if b>=1e6 else f"{b/1e3:.0f} KB"))
notes={}
for base in ('manifest','manifest-private'):
    for f,key in (('models.tsv','hf_id'),('repos.tsv','url'),('datasets.tsv','hf_id')):
        p=f'{ARK}/{base}/{f}'
        if os.path.exists(p):
            for r in csv.DictReader(open(p),delimiter='\t'): notes[r[key].rstrip('/')]=r
FAM=[('deepseek','DeepSeek'),('qwen','Qwen'),('agentworld','Qwen'),('agent-r2','Qwen'),('glm','GLM'),('kimi','Kimi'),('minimax','MiniMax'),('nemotron','Nemotron'),('mimo','MiMo'),('ornith','Ornith'),('mistral','Mistral'),('mn-grand','Mistral-Nemo'),('gemma','Gemma'),('granite','Granite'),('wan','Wan'),('hunyuan','Hunyuan'),('hy4','Hunyuan'),('llama','Llama'),('ling','Ling'),('laguna','Laguna'),('muse','Muse'),('cosyvoice','CosyVoice'),('sensevoice','SenseVoice'),('indextts','IndexTTS'),('paddle','PaddleOCR'),('whisper','Whisper'),('z-image','Z-Image'),('cydonia','Cydonia'),('hammer','Hammer'),('xlam','xLAM'),('kev','kev (decision)'),('decider','decider (decision)'),('laya','Laya (decision)'),('von','von (decision)'),('plumb','plumb (decision)'),('omni','Qwen')]
def fam(n):
    n=n.lower()
    for k,v in FAM:
        if k in n: return v
    return 'Other'
def kind(m):
    n=m['name'].lower()
    if any(k in n for k in ('kev-','decider','laya','wfzyx__von','plumb')): return 'Decision models'
    if any(k in n for k in ('tts','asr','voice','whisper','cosy','sense','indextts','omni')): return 'Speech and omni'
    if any(k in n for k in ('wan','hunyuan','hy4','z-image','image','video','scail')): return 'Image and video'
    if any(k in n for k in ('embedding','reranker','ocr','vl','caption')): return 'Vision, OCR and embeddings'
    return 'Language models'
def node(title,meta='',body='',open_=False,cls=''):
    return f"<details class='n {cls}'{' open' if open_ else ''}><summary><span class='t'>{title}</span><span class='m'>{meta}</span></summary><div class='b'>{body}</div></details>"
def leaf(title,meta='',detail=''):
    return f"<div class='leaf'><span class='t'>{title}</span><span class='m'>{meta}</span>{('<div class=d>'+detail+'</div>') if detail else ''}</div>"
def kv(pairs): return ' '.join(f"<span class='kv'><b>{esc(k)}</b> {esc(v)}</span>" for k,v in pairs if v)
# ── stores
drives=inv['drives']; used=sum(v['total']-v['free'] for v in drives.values()); total=sum(v['total'] for v in drives.values())
stores=''.join(node(f"<span class='mono'>{esc(d)}</span>", f"{gb(v['total']-v['free'])} used · {gb(v['free'])} free",
    ''.join(leaf(f"<span class='mono'>{esc(k)}/</span>", gb(s)) for k,s in sorted(v['top'].items(),key=lambda kv:-kv[1]) if s>1e6)) for d,v in drives.items())
# ── models
models=inv['models']; groups={}
for m in models: groups.setdefault(kind(m),[]).append(m)
def mdetail(m):
    nt=notes.get(next((k for k in notes if k.split('/')[-1].lower()==m['name'].split('__')[-1].lower()),''),{})
    return kv([('path',f"/mnt/{m['drive']}/models/{m['name']}"),('layout',' '.join(m['layout'])),('formats',' '.join(m['formats'])),('quants',' '.join(m['quants'])),('note',nt.get('note','')),('include',nt.get('include',''))])
msec=''.join(node(esc(g), f"{len(ms)} · {gb(sum(m['size'] for m in ms))}", ''.join(leaf(esc(m['name']), f"<span class='mono'>{esc(m['drive'])}</span> · {gb(m['size'])}", mdetail(m)) for m in sorted(ms,key=lambda m:-m['size']))) for g,ms in sorted(groups.items(),key=lambda kv:-sum(m['size'] for m in kv[1])))
# ── comfy
comfy=inv['comfy']; csize=sum(b['size'] for t in comfy.values() for b in t.values()); cfiles=sum(b['files'] for t in comfy.values() for b in t.values())
csec=''.join(node(f"<span class='mono'>{esc(t)}/</span>", f"{sum(b['files'] for b in bs.values())} files · {gb(sum(b['size'] for b in bs.values()))}", ''.join(leaf(f"<span class='mono'>{esc(b)}/</span>", f"{v['files']} files · {gb(v['size'])}", kv([('path',f'/mnt/nv6/comfy/{t}/{b}')])) for b,v in sorted(bs.items(),key=lambda kv:-kv[1]['size']))) for t,bs in sorted(comfy.items(),key=lambda kv:-sum(b['size'] for b in kv[1].values())))
# ── helper weights
hfa=inv['hf_assets']; horg={}
for x in hfa: horg.setdefault(x['org'],[]).append(x)
hsec=''.join(node(f"<span class='mono'>{esc(o)}/</span>", f"{len(v)} · {gb(sum(x['size'] for x in v))}", ''.join(leaf(esc(x['repo']), gb(x['size']), kv([('path',f"/mnt/nv3/hf-assets/{o}/{x['repo']}"),('note',notes.get(f'{o}/{x["repo"]}',{}).get('note','')),('include',notes.get(f'{o}/{x["repo"]}',{}).get('include',''))])) for x in sorted(v,key=lambda x:-x['size']))) for o,v in sorted(horg.items(),key=lambda kv:-sum(x['size'] for x in kv[1])))
# ── reference data
D=inv.get('data',{})
def dnode(title,d,path,extra=''):
    return node(title, f"{len(d)} · {gb(sum(v['size'] for v in d.values()))}", (extra and f"<p class='note'>{extra}</p>")+''.join(leaf(esc(k), gb(v['size'])+(f" · {v['files']} files" if v.get('files',1)>1 else ''), kv([('path',f'{path}/{k}'),('note',notes.get(k.replace('__','/'),{}).get('note',''))])) for k,v in sorted(d.items(),key=lambda kv:-kv[1]['size'])))
zims={k:v for k,v in D.get('zim',{}).items() if k!='devdocs'}
dsec=(dnode("Offline knowledge (Kiwix ZIM)",zims,'/mnt/nv4/data/reference/zim',"Serve with <span class='mono'>kiwix-serve --port 8081 *.zim devdocs/*.zim</span>; Gutenberg lives on nv2.")
 +dnode("DevDocs sets",D.get('devdocs',{}),'/mnt/nv4/data/reference/zim/devdocs')
 +dnode("Genome references (GRCh38)",D.get('genome',{}),'/mnt/nv4/data/reference/genome',"hg38 + Ensembl 116 assembly/GTF, VEP cache (tar), ClinVar, dbSNP, gnomAD chr22 sample.")
 +dnode("Datasets (training and eval)",D.get('datasets',{}),'/mnt/nv6/data/datasets')
 +dnode("CC0 assets",D.get('assets',{}),'/mnt/nv6/data/assets')
 +dnode("Container images (docker load -i)",D.get('containers',{}),'/mnt/nv2/software/containers')
 +dnode("Embedded toolchains",D.get('embedded',{}),'/mnt/nv2/software/embedded',"PlatformIO core + cached compilers (XIAO ESP32-S3/C3/C6, RP2040, AVR), arduino-cli + cores, esp-idf tools; set the three env vars from the README there."))
dtot=sum(sum(v['size'] for v in D.get(k,{}).values()) for k in ('zim','devdocs','genome','datasets','assets','containers','embedded'))
# ── software
sw=inv['software']; repos=sw['repos']; nrepos=sum(len(v) for v in repos.values())
def rlabel(u): return re.sub(r'^https?://(github\.com/|gitlab\.com/|gitlab\.[a-z.]+/)?','',u)
ssec=''.join(node(esc(sec), f"{len(v)} repos · {gb(sum(r['size'] for r in v))}", ''.join(leaf(f"<a href='{esc(r['url'])}'>{esc(rlabel(r['url']))}</a>"+(" <i class='tag'>node_modules</i>" if r['node_modules'] else '')+('' if r['present'] else " <i class='tag warn'>not cloned</i>"), gb(r['size']), kv([('path','/mnt/nv2/software/src/'+re.sub(r'^https?://','',r['url']).replace('/','__')),('note',notes.get(r['url'].rstrip('/'),{}).get('note',''))])) for r in sorted(v,key=lambda r:-r['size']))) for sec,v in repos.items())
W=sw['wheels']; R={k:v for k,v in sw.items() if k.startswith('resolve')}
lanes=''.join(leaf(f"<span class='mono'>{esc(k.replace('resolve-',''))}</span>", f"{v['reqs']}/{v['reqs']+v['reqs_fail']} requirement sets · {v['projects']}/{v['projects']+v['projects_fail']} projects resolve offline") for k,v in sorted(R.items()))
tools=node("Toolchains and binaries", f"{len(sw['binaries'])}", ''.join(leaf(esc(b)) for b in sw['binaries'] if not b.startswith('python')))
pyb=node("CPython builds (python-build-standalone)", f"{len(sw['python'])}", ''.join(leaf(esc(p.split('/')[-1])) for p in sw['python']))
stores_tbl=node("Package stores", "", ''.join(leaf(f"<span class='mono'>{esc(e)}/</span>", f"{gb(sw[e]['size'])} · {sw[e]['entries']} entries") for e in ['wheels-cuda-cu130','wheels-cuda-cu128','debs','rocm','containers','cargo-home','cmake-deps','gomodcache','npm-cache','pnpm-store','bun-cache','docs'] if sw.get(e))+leaf("<span class='mono'>nv4/ubuntu-mirror/</span>", f"{gb(sw['ubuntu_mirror']['size'])} · {len(sw['ubuntu_mirror']['repos'])} apt sources"))
lanesec=node("Python wheel lanes", f"{W['total']:,} wheels · {gb(W['size'])}", f"<p class='note'>{W['cp312']} cp312 · {W['cp313']} cp313 · {W['cp314']} cp314 native · {W['pure']:,} pure-Python · {W['sdist']} sdists. cp312 = primary GPU lane (ROCm torch), cp313 = second GPU lane, cp314 = tools only.</p>"+lanes)
docs=node("Docs on the mirror", f"{len(inv['docs'])}", ''.join(leaf(esc(d), '', kv([('path',f'/mnt/nv2/software/docs/{d}')])) for d in inv['docs']))
today=datetime.date.today().isoformat()
page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Pod Directory</title>
<style>
:root{{--bg:#0f1317;--panel:#161c22;--panel2:#1c242c;--ink:#dfe6e3;--ink2:#93a19b;--rule:#2a343b;--accent:#5fd3c3;--accent2:#1c3a37;--warn:#e0955a}}
*{{box-sizing:border-box}} html{{color-scheme:dark}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px clamp(16px,3vw,32px) 64px}}
h1{{font-size:clamp(26px,4vw,38px);margin:0 0 4px;letter-spacing:-.01em}} .eyebrow{{font:500 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
.lede{{color:var(--ink2);max-width:66ch;margin:8px 0 18px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin-bottom:18px}} .tile{{background:var(--panel);padding:12px 14px}} .tile b{{display:block;font-size:24px;font-variant-numeric:tabular-nums}} .tile span{{color:var(--ink2);font-size:12px}}
.bar{{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 0;border-bottom:1px solid var(--rule);margin-bottom:14px}}
input[type=search]{{flex:1 1 260px;font:14px system-ui;padding:8px 10px;background:var(--panel);color:var(--ink);border:1px solid var(--rule);border-radius:4px}} input:focus{{outline:2px solid var(--accent);outline-offset:1px}}
button{{font:500 12px system-ui;padding:7px 10px;background:var(--panel);color:var(--ink2);border:1px solid var(--rule);border-radius:4px;cursor:pointer}} button:hover{{color:var(--ink);border-color:var(--accent)}} #hits{{color:var(--ink2);font-size:12px;font-variant-numeric:tabular-nums}}
details.n{{border-left:2px solid var(--rule);margin:2px 0 2px 0;padding-left:10px}} details.n[open]{{border-color:var(--accent2)}} details.top{{border-left:none;padding-left:0;margin:0 0 10px}} details.top>summary{{background:var(--panel);padding:10px 12px;border:1px solid var(--rule);border-radius:4px;font-size:16px}}
summary{{cursor:pointer;display:flex;justify-content:space-between;gap:12px;align-items:baseline;padding:4px 6px;border-radius:3px;list-style:none}} summary::-webkit-details-marker{{display:none}} summary::before{{content:"▸";color:var(--accent);margin-right:8px;display:inline-block;width:12px}} details[open]>summary::before{{content:"▾"}} summary:hover{{background:var(--panel2)}}
.t{{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}} .m{{color:var(--ink2);font-size:12.5px;font-variant-numeric:tabular-nums;white-space:nowrap;font-family:ui-monospace,Menlo,monospace}}
.b{{padding:2px 0 6px 14px}} .leaf{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;padding:3px 6px;border-radius:3px;font-size:14px}} .leaf:hover{{background:var(--panel2)}} .leaf .t{{flex:1 1 60%}} .leaf .d{{flex-basis:100%;color:var(--ink2);font-size:12px;padding:2px 0 2px 20px;display:none}} .leaf.show .d,.leaf:focus-within .d{{display:block}} .leaf.has{{cursor:pointer}}
.kv{{display:inline-block;margin-right:12px}} .kv b{{color:var(--ink);font-weight:500;margin-right:4px}} .mono{{font-family:ui-monospace,Menlo,monospace;font-size:13px}} a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
.tag{{font-style:normal;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);border:1px solid var(--accent2);padding:0 5px;border-radius:3px;margin-left:6px}} .tag.warn{{color:var(--warn);border-color:var(--warn)}}
.note{{color:var(--ink2);font-size:13px;margin:4px 0 8px;border-left:3px solid var(--accent);padding:4px 10px}} .hit>summary .t,.leaf.hit .t{{color:var(--accent)}} .hide{{display:none!important}}
footer{{color:var(--ink2);font-size:12px;border-top:1px solid var(--rule);padding-top:12px;margin-top:24px}}
</style></head><body><div class="wrap">
<span class="eyebrow">Provisions for a voyage with no resupply · bigboy, six 2 TB stores · surveyed {today}</span>
<h1>AI Pod Directory</h1>
<p class="lede">Everything stocked for the air-gapped Pod, as a drill-down. Open a section, then a group, then an item; click an item for its path and notes. Search opens every branch that matches.</p>
<div class="tiles"><div class="tile"><b>{gb(used)}</b><span>stowed of {gb(total)}</span></div><div class="tile"><b>{len(models)}</b><span>model folders</span></div><div class="tile"><b>{cfiles:,}</b><span>Comfy asset files</span></div><div class="tile"><b>{len(hfa)}</b><span>helper-weight repos</span></div><div class="tile"><b>{gb(dtot)}</b><span>reference data</span></div><div class="tile"><b>{nrepos}</b><span>source repos</span></div><div class="tile"><b>{W['total']:,}</b><span>Python wheels</span></div></div>
<div class="bar"><input type="search" id="q" placeholder="Search everything (name, path, note, category)" aria-label="Search"><button id="exp">expand all</button><button id="col">collapse all</button><span id="hits"></span></div>
{node("Stores", f"{len(drives)} drives · {gb(used)} used", stores, cls='top')}
{node("Models", f"{len(models)} folders · {gb(sum(m['size'] for m in models))}", "<p class='note'>Layout: <span class='mono'>models/&lt;name&gt;/raw</span> = the release as published, <span class='mono'>gguf</span> = llama.cpp quants, <span class='mono'>colibri</span> = Colibrì engine format. Every store keeps an <span class='mono'>llm → models</span> symlink.</p>"+msec, cls='top')}
{node("Comfy assets", f"{cfiles:,} files · {gb(csize)}", "<p class='note'>One root, <span class='mono'>/mnt/nv6/comfy/&lt;type&gt;/&lt;base&gt;/</span>, one extra_model_paths entry.</p>"+csec, cls='top')}
{node("Helper weights", f"{len(hfa)} repos · {gb(sum(x['size'] for x in hfa))}", "<p class='note'><span class='mono'>/mnt/nv3/hf-assets/&lt;org&gt;/&lt;repo&gt;</span>: what mirrored code downloads at first run, the voice stack, Comfy node weights, the realtime-diffusion stack. Point <span class='mono'>HF_HOME</span> here with <span class='mono'>HF_HUB_OFFLINE=1</span>.</p>"+hsec, cls='top')}
{node("Reference data and provisions", gb(dtot), dsec, cls='top')}
{node("Software mirror", f"{nrepos} repos · {len(repos)} categories", "<p class='note'><span class='mono'>/mnt/nv2/software</span>: latest-only shallow clones under <span class='mono'>src/</span>, wheels, apt/ROCm/CUDA pools, containers, caches for cargo/go/npm/pnpm/bun. Manifest and fetchers: <span class='mono'>~/Code/ark</span>.</p>"+ssec+tools+pyb+stores_tbl+lanesec+docs, cls='top')}
<footer>Generated from bigboy <span class="mono">~/storage-review/inventory.json</span> and the ark manifests by <span class="mono">report/gen-directory.py</span>. Indexes: <span class="mono">/mnt/nv2/CATALOG-latest.tsv</span>, <span class="mono">MANIFEST.tsv</span> (sha256 per file).</footer></div>
<script>
(function(){{var q=document.getElementById('q'),hits=document.getElementById('hits');
document.querySelectorAll('.leaf').forEach(function(l){{if(l.querySelector('.d')){{l.classList.add('has');l.tabIndex=0;l.addEventListener('click',function(e){{if(e.target.tagName==='A')return;l.classList.toggle('show')}})}}}});
function all(open){{document.querySelectorAll('details').forEach(function(d){{d.open=open}})}}
document.getElementById('exp').onclick=function(){{all(true)}};document.getElementById('col').onclick=function(){{all(false);document.querySelectorAll('details.top').forEach(function(d){{d.open=false}})}};
var timer;q.addEventListener('input',function(){{clearTimeout(timer);timer=setTimeout(run,120)}});
function run(){{var t=q.value.trim().toLowerCase();document.querySelectorAll('.hit').forEach(function(e){{e.classList.remove('hit')}});document.querySelectorAll('.hide').forEach(function(e){{e.classList.remove('hide')}});
if(!t){{hits.textContent='';return}}var n=0;document.querySelectorAll('.leaf').forEach(function(l){{var ok=l.textContent.toLowerCase().indexOf(t)>-1;if(ok){{n++;l.classList.add('hit');var p=l.parentElement;while(p){{if(p.tagName==='DETAILS'){{p.open=true;p.classList.add('hit')}}p=p.parentElement}}}}else l.classList.add('hide')}});
document.querySelectorAll('details.n').forEach(function(d){{if(!d.classList.contains('hit')){{if(d.querySelector('summary').textContent.toLowerCase().indexOf(t)>-1){{d.classList.add('hit');d.open=true;var p=d.parentElement;while(p){{if(p.tagName==='DETAILS'){{p.open=true;p.classList.add('hit')}}p=p.parentElement}};d.querySelectorAll('.hide').forEach(function(e){{e.classList.remove('hide')}});n+=d.querySelectorAll('.leaf').length}}else d.classList.add('hide')}}}});
hits.textContent=n+' matches'}}
try{{var s=localStorage.getItem('pod-dir-q');if(s){{q.value=s;run()}}q.addEventListener('input',function(){{try{{localStorage.setItem('pod-dir-q',q.value)}}catch(e){{}}}})}}catch(e){{}}
}})();
</script></body></html>"""
open(sys.argv[2],'w').write(page); print(f'{len(page)//1024} KB, {nrepos} repos, {len(models)} models, {len(hfa)} helper repos')
