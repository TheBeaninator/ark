#!/usr/bin/env python3
"""gen-manifest.py inventory.json out.html — render the AI Pod manifest page from bigboy's inventory JSON (run remap.py on it first)."""
import json,html,re,datetime,sys
inv=json.load(open(sys.argv[1]))
def gb(b): return f"{b/1e9:,.0f}" if b>=1e9 else f"{b/1e6:,.0f} MB"
def tb(b): return f"{b/1e12:.2f}"
def esc(s): return html.escape(str(s))
drives=inv['drives']; used=sum(v['total']-v['free'] for v in drives.values()); total=sum(v['total'] for v in drives.values()); free=sum(v['free'] for v in drives.values())
models=sorted(inv['models'],key=lambda m:-m['size']); msize=sum(m['size'] for m in models)
comfy=inv['comfy']; csize=sum(b['size'] for t in comfy.values() for b in t.values()); cfiles=sum(b['files'] for t in comfy.values() for b in t.values())
hfa=sorted(inv['hf_assets'],key=lambda x:(x['org'].lower(),x['repo'].lower())); hsize=sum(x['size'] for x in hfa)
sw=inv['software']; repos=sw['repos']; nrepos=sum(len(v) for v in repos.values()); rsize=sum(r['size'] for v in repos.values() for r in v)
W=sw['wheels']; R={k:v for k,v in sw.items() if k.startswith('resolve')}
FAM=[('deepseek','DeepSeek'),('qwen','Qwen'),('agentworld','Qwen'),('agent-r2','Qwen'),('glm','GLM'),('kimi','Kimi'),('minimax','MiniMax'),('nemotron','Nemotron'),('mimo','MiMo'),('ornith','Ornith'),('mistral','Mistral'),('mn-grand','Mistral-Nemo'),('gemma','Gemma'),('granite','Granite'),('wan','Wan'),('hunyuan','Hunyuan'),('hy4','Hunyuan'),('llama','Llama'),('ling','Ling'),('laguna','Laguna'),('muse','Muse'),('cosyvoice','CosyVoice'),('sensevoice','SenseVoice'),('indextts','IndexTTS'),('paddle','PaddleOCR'),('whisper','Whisper'),('z-image','Z-Image'),('cydonia','Cydonia'),('hammer','Hammer'),('xlam','xLAM')]
def fam(name):
    n=name.lower()
    for k,v in FAM:
        if k in n: return v
    return 'Other'
def kind(m):
    n=m['name'].lower()
    if any(k in n for k in ('tts','asr','voice','whisper','cosy','sense','index','omni')): return 'speech'
    if any(k in n for k in ('wan','hunyuan','hy4','z-image','image','video')): return 'image/video'
    if any(k in n for k in ('embedding','reranker','ocr','vl','caption')): return 'vision/embed'
    return 'llm'
rows=[f"<tr data-k='{kind(m)}'><td class='name'>{esc(m['name'])}<span class='sub'>{esc(fam(m['name']))} · {kind(m)}</span></td><td class='mono'>{esc(m['drive'])}</td><td class='num'>{gb(m['size'])}</td><td class='mono'>{' '.join(esc(x) for x in m['layout'])}</td><td class='mono'>{' '.join(esc(x) for x in m['formats'])}</td><td class='mono q'>{' '.join(esc(x) for x in m['quants'])}</td></tr>" for m in models]
kinds={}
for m in models: kinds[kind(m)]=kinds.get(kind(m),0)+1
crow=[]
for t in sorted(comfy,key=lambda t:-sum(b['size'] for b in comfy[t].values())):
    bases=comfy[t]; ts=sum(b['size'] for b in bases.values()); tf=sum(b['files'] for b in bases.values())
    chips=' '.join(f"<span class='chip'><b>{esc(b)}</b> {bases[b]['files']}<i>{gb(bases[b]['size'])}</i></span>" for b in sorted(bases,key=lambda b:-bases[b]['size']))
    crow.append(f"<div class='ctype'><div class='ctype-h'><span class='mono'>{esc(t)}/</span><span class='num'>{tf} files · {gb(ts)} GB</span></div><div class='chips'>{chips}</div></div>")
horg={}
for x in hfa: horg.setdefault(x['org'],[]).append(x)
def _chip(x): return f"<span class=chip><b>{esc(x['repo'])}</b><i>{gb(x['size'])}</i></span>"
hrow=''.join(f"<div class='org'><div class='org-h'><span class='mono'>{esc(o)}/</span><span class='num'>{gb(sum(x['size'] for x in v))} GB</span></div><div class='repos'>{' '.join(_chip(x) for x in sorted(v,key=lambda x:-x['size']))}</div></div>" for o,v in sorted(horg.items(),key=lambda kv:kv[0].lower()))
srow=[]
for sec,lst in repos.items():
    present=sum(r['present'] for r in lst); node=sum(r['node_modules'] for r in lst)
    items=' '.join(f"<a class='repo{'' if r['present'] else ' miss'}' href='{esc(r['url'])}' target='_blank' rel='noopener'>{esc(re.sub(r'^https?://(github.com/|gitlab[^/]*/)?','',r['url']))}{' <i>node</i>' if r['node_modules'] else ''}</a>" for r in lst)
    srow.append(f"<details class='sec' open><summary><span>{esc(sec)}</span><span class='num'>{present}/{len(lst)} cloned{f' · {node} with node_modules' if node else ''} · {gb(sum(r['size'] for r in lst))} GB</span></summary><div class='repos'>{items}</div></details>")
bins=[b for b in sw['binaries'] if not b.startswith('python')]
pyb=[p.split('/')[-1] for p in sw['python']]
ROLE={'cp312':'primary GPU lane (ROCm 7.2 torch)','cp313':'second GPU lane (ROCm 7.2 torch)','cp314':'tools lane; no GPU torch exists yet'}
lanes=''.join(f"<tr><td class='mono'>{esc(k.replace('resolve-',''))}</td><td class='num'>{v['reqs']} / {v['reqs']+v['reqs_fail']}</td><td class='num'>{v['projects']} / {v['projects']+v['projects_fail']}</td><td>{ROLE.get(k.replace('resolve-',''),'')}</td></tr>" for k,v in sorted(R.items()))
extras=''.join(f"<tr><td class='mono'>{esc(e)}/</td><td class='num'>{gb(sw[e]['size'])} GB</td><td class='num'>{sw[e]['entries']} entries</td></tr>" for e in ['wheels-cuda-cu130','wheels-cuda-cu128','debs','rocm','containers','cargo-home','cmake-deps','gomodcache','npm-cache','pnpm-store','bun-cache','docs'] if sw.get(e))
drow=''.join(f"<div class='drive'><div class='drive-h'><span class='mono big'>{esc(d)}</span><span class='num'>{gb(v['total']-v['free'])} / {gb(v['total'])} GB</span></div><div class='bar'><i style='width:{(v['total']-v['free'])/v['total']*100:.1f}%'></i></div><div class='drive-top'>{' '.join(f'<span><b>{esc(k)}</b> {gb(s)}</span>' for k,s in sorted(v['top'].items(),key=lambda kv:-kv[1]) if s>1e9)}</div></div>" for d,v in drives.items())
D=inv.get('data',{})
def dsum(d): return sum(v['size'] for v in d.values())
dtot=sum(dsum(D.get(k,{})) for k in ('zim','genome','datasets','assets')) + dsum(D.get('devdocs',{}))
def dlist(d,top=None,showfiles=False):
    items=sorted(d.items(),key=lambda kv:-kv[1]['size'])[:top]
    return ' '.join(f"<span class='chip'><b>{esc(k)}</b><i>{gb(v['size'])}{' GB' if v['size']>=1e9 else ''}{(' · '+str(v['files'])+' files') if showfiles and v['files']>1 else ''}</i></span>" for k,v in items)
zims={k:v for k,v in D.get('zim',{}).items() if k!='devdocs'}
drow_data=f'''
<section id="provisions"><div class="sec-h"><h2>Reference data and provisions</h2><span class="num">{tb(dtot)} TB · offline knowledge, genome references, datasets, CC0 assets</span></div>
<div class="ctype"><div class="ctype-h"><span class="mono">reference/zim/ (nv4; Gutenberg on nv2)</span><span class="num">{gb(dsum(zims))} GB + {len(D.get('devdocs',{}))} DevDocs sets {gb(dsum(D.get('devdocs',{})))}</span></div><div class="chips">{dlist(zims)}</div>
<p class="note" style="margin-top:8px">Serve with <span class="mono">kiwix-serve --port 8081 *.zim devdocs/*.zim</span> (kiwix-tools mirrored). DevDocs covers {', '.join(sorted(k.split('_')[2] for k in D.get('devdocs',{})))}.</p></div>
<div class="ctype"><div class="ctype-h"><span class="mono">reference/genome/ (nv4)</span><span class="num">{gb(dsum(D.get('genome',{})))} GB</span></div><div class="chips">{dlist(D.get('genome',{}))}</div>
<p class="note" style="margin-top:8px">GRCh38 (UCSC hg38 and Ensembl primary assembly + GTF), VEP cache, ClinVar, dbSNP, one gnomAD chromosome as a sample. Tools under Genome analysis in the software register.</p></div>
<div class="ctype"><div class="ctype-h"><span class="mono">data/datasets/ (nv6)</span><span class="num">{len(D.get('datasets',{}))} sets · {gb(dsum(D.get('datasets',{})))} GB</span></div><div class="chips">{dlist(D.get('datasets',{}))}</div></div>
<div class="ctype"><div class="ctype-h"><span class="mono">data/assets/ (nv6, CC0)</span><span class="num">{gb(dsum(D.get('assets',{})))} GB</span></div><div class="chips">{dlist(D.get('assets',{}),showfiles=True)}</div></div>
<div class="ctype"><div class="ctype-h"><span class="mono">software/containers/ and software/embedded/ (nv2)</span><span class="num">{len(D.get('containers',{}))} images · {len(D.get('embedded',{}))} toolchain stores</span></div><div class="chips">{dlist(D.get('containers',{}))} {dlist(D.get('embedded',{}))}</div>
<p class="note" style="margin-top:8px">Images load with <span class="mono">docker load -i</span>. Embedded toolchains: PlatformIO core with cached compilers for XIAO ESP32-S3/C3/C6, RP2040 and AVR boards, arduino-cli with the AVR and ESP32 cores, esp-idf tools.</p></div>
</section>
'''
today=datetime.date.today().isoformat()
page=f"""<title>AI Pod Manifest</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: a cargo ledger — a summary strip up top, then long scannable registers (models, comfy, helpers, software) with a sticky section nav */
:root{{--bg:#f3f5f2;--paper:#fbfcfa;--ink:#16202b;--ink-2:#4b5866;--rule:#d5dbd6;--accent:#0f6e66;--accent-2:#dbeeea;--warn:#a5541c;--disp:'Fraunces',Georgia,serif;--body:'IBM Plex Sans',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0f1519;--paper:#161d23;--ink:#e6ebe8;--ink-2:#9aa8a3;--rule:#2a343b;--accent:#4fc2b5;--accent-2:#173a37;--warn:#e0955a;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#0f1519;--paper:#161d23;--ink:#e6ebe8;--ink-2:#9aa8a3;--rule:#2a343b;--accent:#4fc2b5;--accent-2:#173a37;--warn:#e0955a;color-scheme:dark}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 var(--body);margin:0}}
.wrap{{max-width:1180px;margin:0 auto;padding-inline:clamp(16px,3vw,32px);padding-block:24px 64px}}
h1{{font:500 clamp(30px,4.5vw,46px)/1.05 var(--disp);letter-spacing:-.01em;margin:0;text-wrap:balance}}
h2{{font:700 22px/1.2 var(--disp);margin:0 0 4px;text-wrap:balance}}
.eyebrow{{font:500 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
.lede{{color:var(--ink-2);max-width:62ch;margin:10px 0 0}}
header{{display:grid;gap:12px;padding-bottom:20px;border-bottom:2px solid var(--ink)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin-top:22px}}
.tile{{background:var(--paper);padding:14px 16px}}
.tile b{{display:block;font:500 26px/1 var(--disp);font-variant-numeric:tabular-nums}}
.tile span{{color:var(--ink-2);font-size:12px}}
nav.toc{{position:sticky;top:env(safe-area-inset-top,0px);z-index:2;background:var(--bg);display:flex;gap:4px 18px;flex-wrap:wrap;padding:10px 0;margin:8px 0 28px;border-bottom:1px solid var(--rule);font:500 13px var(--body)}}
nav.toc a{{color:var(--ink-2);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent}}
nav.toc a:hover,nav.toc a:focus-visible{{color:var(--accent);border-color:var(--accent);outline:none}}
section{{margin:0 0 44px}}
.sec-h{{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px 16px;margin-bottom:14px}}
.num{{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2);font-size:13px}}
.mono{{font-family:var(--mono);font-size:13px}}
.big{{font-size:16px;font-weight:500;color:var(--ink)}}
.drives{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}
.drive{{background:var(--paper);border:1px solid var(--rule);padding:12px 14px;min-width:0}}
.drive-h{{display:flex;justify-content:space-between;align-items:baseline;gap:8px}}
.bar{{height:6px;background:var(--rule);margin:8px 0 10px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--accent)}}
.drive-top{{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--ink-2)}}.drive-top b{{font-weight:500;color:var(--ink);font-family:var(--mono)}}
.tools{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}}
input[type=search]{{font:14px var(--body);padding:7px 10px;border:1px solid var(--rule);background:var(--paper);color:var(--ink);min-width:220px;flex:1 1 220px}}
.filters{{display:flex;flex-wrap:wrap;gap:6px}}
.filters button{{font:500 12px var(--body);padding:5px 10px;border:1px solid var(--rule);background:var(--paper);color:var(--ink-2);cursor:pointer}}
.filters button[aria-pressed=true]{{background:var(--accent-2);border-color:var(--accent);color:var(--ink)}}
.filters button:focus-visible{{outline:2px solid var(--accent);outline-offset:1px}}
.tbl{{overflow-x:auto;border:1px solid var(--rule);background:var(--paper)}}
table{{border-collapse:collapse;width:100%;min-width:760px;font-size:13.5px}}
th{{text-align:left;font:500 11px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2);padding:10px 12px;border-bottom:1px solid var(--rule);background:var(--paper);position:sticky;top:0}}
td{{padding:9px 12px;border-bottom:1px solid var(--rule);vertical-align:top}}
td.name{{font-weight:500;max-width:340px;word-break:break-word}}td .sub{{display:block;font:12px var(--body);color:var(--ink-2);font-weight:400}}
td.num{{text-align:right;color:var(--ink);white-space:nowrap}}td.q{{color:var(--ink-2)}}
tr[hidden]{{display:none}}
.ctype,.org{{border-top:1px solid var(--rule);padding:12px 0}}
.ctype-h,.org-h{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:8px}}.ctype-h .mono,.org-h .mono{{font-weight:500;color:var(--ink)}}
.chips,.repos{{display:flex;flex-wrap:wrap;gap:6px}}
.chip{{display:inline-flex;gap:6px;align-items:baseline;font:12px var(--body);background:var(--paper);border:1px solid var(--rule);padding:3px 8px}}
.chip b{{font-weight:500}}.chip i{{font-style:normal;color:var(--ink-2);font-family:var(--mono);font-size:11px}}
.repo{{font:12.5px var(--mono);color:var(--ink);text-decoration:none;background:var(--paper);border:1px solid var(--rule);padding:3px 8px;max-width:100%;overflow-wrap:anywhere}}
.repo:hover{{border-color:var(--accent);color:var(--accent)}}.repo i{{font-style:normal;color:var(--accent);font-size:10px;letter-spacing:.08em;text-transform:uppercase;margin-left:4px}}
.repo.miss{{color:var(--warn);border-style:dashed}}
details.sec{{border-top:1px solid var(--rule);padding:10px 0}}details.sec summary{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px 16px;cursor:pointer;font-weight:500;list-style:none;padding:2px 0 8px}}
details.sec summary::-webkit-details-marker{{display:none}}details.sec summary::before{{content:"▸ ";color:var(--accent)}}details[open].sec summary::before{{content:"▾ "}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}}.two>*{{min-width:0}}
ul.plain{{margin:0;padding-left:18px;color:var(--ink-2)}}ul.plain li{{margin:2px 0}}ul.plain b{{color:var(--ink);font-weight:500}}
.note{{border-left:3px solid var(--accent);padding:8px 12px;background:var(--paper);color:var(--ink-2);font-size:13.5px}}
footer{{color:var(--ink-2);font-size:12.5px;border-top:1px solid var(--rule);padding-top:14px}}
@media (max-width:520px){{table{{min-width:640px}}}}
@media (prefers-reduced-motion:no-preference){{.bar i{{transition:width .4s ease}}}}
</style>
<div class="wrap">
<header>
<span class="eyebrow">Provisions for a voyage with no resupply · bigboy, six 2 TB NVMe stores · surveyed {today}</span>
<h1>AI Pod Manifest</h1>
<p class="lede">Every model, asset, software package and reference set stocked for the air-gapped Pod. Models are clustered one folder per model with raw releases and quants underneath, Comfy assets share one root on nv6, and the software mirror on nv2 carries the toolchains, wheels, packages and containers to rebuild and convert all of it offline.</p>
<div class="tiles">
<div class="tile"><b>{tb(used)} TB</b><span>stowed of {tb(total)} TB · {tb(free)} TB free</span></div>
<div class="tile"><b>{len(models)}</b><span>model folders · {tb(msize)} TB</span></div>
<div class="tile"><b>{cfiles:,}</b><span>Comfy asset files · {tb(csize)} TB</span></div>
<div class="tile"><b>{len(hfa)}</b><span>helper-weight repos · {gb(hsize)} GB</span></div>
<div class="tile"><b>{nrepos}</b><span>source repos mirrored · {gb(rsize)} GB</span></div>
<div class="tile"><b>{W['total']:,}</b><span>Python wheels · {gb(W['size'])} GB · 3 interpreters</span></div>
<div class="tile"><b>{tb(dtot)} TB</b><span>reference data · ZIMs, genome, datasets, assets</span></div>
</div>
</header>
<nav class="toc"><a href="#stores">Stores</a><a href="#models">Models</a><a href="#comfy">Comfy assets</a><a href="#helpers">Helper weights</a><a href="#provisions">Reference data</a><a href="#software">Software</a><a href="#lanes">Python lanes</a><a href="#tools">Conversion tooling</a></nav>

<section id="stores"><div class="sec-h"><h2>Stores</h2><span class="num">ext4 by label, mounted at /mnt/nv#, RTL9210 enclosures on usb-storage</span></div>
<div class="drives">{drow}</div></section>

<section id="models"><div class="sec-h"><h2>Models</h2><span class="num">{len(models)} folders · {' · '.join(f'{v} {k}' for k,v in sorted(kinds.items(),key=lambda kv:-kv[1]))}</span></div>
<div class="tools"><input type="search" id="mq" placeholder="Filter by name, family, format or quant" aria-label="Filter models"><div class="filters" id="mf"><button aria-pressed="true" data-k="">all</button>{''.join(f'<button aria-pressed="false" data-k="{k}">{k}</button>' for k in sorted(kinds))}</div></div>
<div class="tbl"><table id="mt"><thead><tr><th>Model</th><th>Store</th><th style="text-align:right">GB</th><th>Layout</th><th>Formats</th><th>Quants seen</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="note">Layout <span class="mono">raw</span> = the Hugging Face release as published (re-quant source); <span class="mono">gguf</span> = llama.cpp quants; <span class="mono">flat</span> = single-format folders not yet split. Every store keeps an <span class="mono">llm → models</span> symlink for older paths.</p></section>

<section id="comfy"><div class="sec-h"><h2>Comfy assets</h2><span class="num">/mnt/nv6/comfy/&lt;type&gt;/&lt;base&gt;/ · {cfiles:,} files · {tb(csize)} TB</span></div>
{''.join(crow)}
<p class="note">One <span class="mono">extra_model_paths</span> root for ComfyUI. <span class="mono">packages/minimax-h3</span> is a self-contained model package with its workflows; <span class="mono">misc/</span> holds per-host leftovers (engines, diffusers pipelines, detectors) that don't map to a Comfy folder.</p></section>

<section id="helpers"><div class="sec-h"><h2>Helper weights</h2><span class="num">/mnt/nv3/hf-assets/&lt;org&gt;/&lt;repo&gt; · {len(hfa)} repos · {gb(hsize)} GB · what mirrored code downloads at first run, plus the voice-assistant stack</span></div>
{hrow}</section>

{drow_data}
<section id="software"><div class="sec-h"><h2>Software mirror</h2><span class="num">/mnt/nv2/software · latest-only shallow clones · {nrepos} repos, grouped by purpose</span></div>
{''.join(srow)}
<div class="two" style="margin-top:22px">
<div><h2>Toolchains and binaries</h2><ul class="plain">{''.join(f'<li><b>{esc(b)}</b></li>' for b in bins)}</ul></div>
<div><h2>Package stores</h2><div class="tbl"><table style="min-width:0"><thead><tr><th>Store</th><th style="text-align:right">Size</th><th style="text-align:right">Entries</th></tr></thead><tbody>{extras}<tr><td class="mono">nv4/ubuntu-mirror/</td><td class="num">{gb(sw['ubuntu_mirror']['size'])} GB</td><td class="num">{len(sw['ubuntu_mirror']['repos'])} apt sources</td></tr></tbody></table></div>
<p class="note" style="margin-top:10px">apt: <span class="mono">{' · '.join(esc(r) for r in sw['ubuntu_mirror']['repos'])}</span> plus the ROCm 7.2.4 pool. Containers: <span class="mono">{' · '.join(esc(c) for c in sw['containers_list'])}</span>.</p></div>
</div></section>

<section id="lanes"><div class="sec-h"><h2>Python lanes</h2><span class="num">{W['total']:,} wheel files · {W['cp312']} cp312 · {W['cp313']} cp313 · {W['cp314']} cp314 native · {W['pure']:,} pure-Python · {W['sdist']} sdists</span></div>
<div class="two"><div><div class="tbl"><table style="min-width:0"><thead><tr><th>Lane</th><th style="text-align:right">Requirement sets</th><th style="text-align:right">Projects</th><th>Role</th></tr></thead><tbody>{lanes}</tbody></table></div>
<p class="note" style="margin-top:10px">Counts are how many of the mirror's own requirements files and projects resolve with <span class="mono">pip --no-index</span> against the wheel store alone. Remaining failures are old pins with no wheel for that interpreter, build systems that need Rust or the network, and Python-version caps.</p></div>
<div><h2>Interpreters</h2><ul class="plain">{''.join(f'<li><b>{esc(p)}</b></li>' for p in pyb)}</ul><p class="note" style="margin-top:10px">python-build-standalone, sha256-verified, laid out for <span class="mono">UV_PYTHON_INSTALL_MIRROR</span> or a plain <span class="mono">tar xf</span>. x86_64_v3 builds are the ones for the Strix Halo boxes.</p></div></div></section>

<section id="tools"><div class="sec-h"><h2>Conversion tooling</h2><span class="num">what the island can do with a raw release</span></div>
<div class="two">
<div><ul class="plain">
<li><b>LLM raw → GGUF</b> llama.cpp convert_hf_to_gguf.py + llama-quantize + llama-imatrix (b11193 builds: Vulkan, ROCm, CPU, SYCL, OpenVINO); ik_llama.cpp for its extra quant types</li>
<li><b>LLM raw → FP8 / W4A16 / AWQ</b> llm-compressor + compressed-tensors for vLLM</li>
<li><b>Abliteration</b> heretic (automatic directional ablation, Optuna-tuned)</li>
<li><b>Diffusion/video raw → Comfy single-file</b> docs/repack/repack_fp8.py (shard merge + fp8 cast, smoke-tested); raw → GGUF via ComfyUI-GGUF convert.py</li>
<li><b>Diffusion Controller</b> Google Research paper + LaTeX source in docs/diffusion-controller; reference code efzero/diffusioncontroller (unlicensed, unverified provenance)</li>
</ul></div>
<div><h2>Docs on the mirror</h2><ul class="plain">{''.join(f'<li><b>{esc(d)}</b></li>' for d in inv['docs'])}</ul>
<p class="note" style="margin-top:10px">Raw releases (Wan 2.2, HunyuanVideo 1.5, DeepSeek V4.1, Coder-Next, AgentWorld, Qwen3.5-122B FP8, GLM-4.6V) are kept on purpose: with this toolchain aboard, every other format can be derived from them.</p></div>
</div></section>

<footer>{esc(inv.get('note',''))} Source of truth: bigboy <span class="mono">~/storage-review/inventory.json</span>, <span class="mono">/mnt/nv2/CATALOG-latest.tsv</span> and <span class="mono">MANIFEST.tsv</span> (sha256 per file). Reorganised {today} with journaled, verify-before-delete moves.</footer>
</div>
<script>
(function(){{
var q=document.getElementById('mq'),fb=document.getElementById('mf'),rows=[].slice.call(document.querySelectorAll('#mt tbody tr')),k='';
function apply(){{var t=q.value.trim().toLowerCase();rows.forEach(function(r){{var ok=(!k||r.dataset.k===k)&&(!t||r.textContent.toLowerCase().indexOf(t)>-1);r.hidden=!ok;}});}}
q.addEventListener('input',apply);
fb.addEventListener('click',function(e){{var b=e.target.closest('button');if(!b)return;k=b.dataset.k;[].forEach.call(fb.children,function(x){{x.setAttribute('aria-pressed',x===b?'true':'false')}});apply();}});
try{{var s=localStorage.getItem('podm-q');if(s){{q.value=s;apply();}}q.addEventListener('input',function(){{try{{localStorage.setItem('podm-q',q.value)}}catch(e){{}}}});}}catch(e){{}}
}})();
</script>
"""
open(sys.argv[2],'w').write(page); print(len(page)//1024,'KB')
