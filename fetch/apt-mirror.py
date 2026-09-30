#!/usr/bin/env python3
"""Latest-only flat apt mirror from bigboy's own apt lists. Per origin: <M>/<host>/<path>/{Packages,Packages.gz,Release,pool/...}
Use with: deb [trusted=yes] file:/mnt/nv4/ubuntu-mirror/archive.ubuntu.com/ubuntu ./"""
import os,re,glob,gzip,hashlib,subprocess,sys,collections
try:
    import apt_pkg; apt_pkg.init_system(); vcmp=apt_pkg.version_compare
except Exception:
    def vcmp(a,b): return 0 if a==b else (1 if subprocess.run(["dpkg","--compare-versions",a,"gt",b]).returncode==0 else -1)
M="/mnt/nv4/ubuntu-mirror"; L=os.environ.get("APT_LISTS","/var/lib/apt/lists")
SKIP=("downloads.claude.ai","packages.microsoft.com","_var_cuda-repo")
origins=collections.defaultdict(dict)   # root -> name -> stanza
ABI=re.compile(r"^linux-.*?-(\d+\.\d+\.\d+-\d+)(-|$)")
NVMOD=re.compile(r"^linux-(modules|objects|signatures)-nvidia-|^linux-restricted-modules|^linux-image-unsigned-|-dbgsym$|^.*-dbg$")
for f in sorted(glob.glob(f"{L}/*_binary-amd64_Packages"))+sorted(glob.glob(f"{L}/*_deb_amd64_Packages")):
    b=os.path.basename(f)
    if any(s in b for s in SKIP): continue
    root=b.split("_dists_")[0] if "_dists_" in b else b[:-len("_Packages")]
    if root=="security.ubuntu.com_ubuntu": root="archive.ubuntu.com_ubuntu"
    scheme="https://" if root.startswith(("ppa.launchpadcontent.net","download.docker.com","apt.kitware.com","nvidia.github.io")) else "http://"
    url=scheme+root.replace("_","/")
    for st in open(f,errors="replace").read().split("\n\n"):
        m=re.search(r"^Package: (\S+)",st,re.M); v=re.search(r"^Version: (\S+)",st,re.M); fn=re.search(r"^Filename: (\S+)",st,re.M)
        if not(m and v and fn): continue
        cur=origins[(root,url)].get(m.group(1))
        if cur is None or vcmp(v.group(1),cur[0])>0: origins[(root,url)][m.group(1)]=(v.group(1),st.strip())
# keep only the newest *generic* kernel ABI per major.minor series; drop cloud/board flavours entirely
CLOUD=re.compile(r"^linux-(image-|headers-|tools-|modules-|modules-extra-|cloud-tools-|buildinfo-|signed-|image-unsigned-|)(\d+\.\d+\.\d+-\d+-)?(aws|azure|gcp|gke|gkeop|oracle|ibm|intel-iotg|intel|nvidia-tegra|nvidia|raspi|xilinx|bluefield|riscv|kvm|oem|lowlatency|realtime)(-|$)")
for key,pk in origins.items():
    best={}
    for name in pk:
        m=ABI.match(name)
        if m and re.search(r"-generic(-64k)?$",name):
            abi=m.group(1); ser=".".join(abi.split(".")[:2])
            if ser not in best or vcmp(abi,best[ser])>0: best[ser]=abi
    drop=[n for n in pk if NVMOD.search(n) or CLOUD.match(n) or (ABI.match(n) and ABI.match(n).group(1) not in best.values())]
    for n in drop: del pk[n]
    print(f"{key[0]}: kept generic ABIs {sorted(best.values())}, dropped {len(drop)} pkgs")
total=0; jobs=[]
for (root,url),pk in origins.items():
    d=f"{M}/{root.replace('_','/')}"; os.makedirs(d,exist_ok=True)
    stanzas=[]; size=0
    for name,(ver,st) in sorted(pk.items()):
        fn=re.search(r"^Filename: (\S+)",st,re.M).group(1); sz=int(re.search(r"^Size: (\d+)",st,re.M).group(1)); size+=sz
        stanzas.append(st+"\n")
        jobs.append(f"{url}/{fn}\n  dir={d}/{os.path.dirname(fn)}\n  out={os.path.basename(fn)}\n")
    total+=size
    open(f"{d}/Packages","w").write("\n".join(stanzas))
    with gzip.open(f"{d}/Packages.gz","wb",9) as g: g.write("\n".join(stanzas).encode())
    rel=["Origin: bigboy-mirror",f"Label: {root}","Suite: noble","Architectures: amd64","Description: latest-only flat mirror",f"Date: {subprocess.check_output(['date','-Ru']).decode().strip()}","MD5Sum:"]
    for x in ("Packages","Packages.gz"):
        data=open(f"{d}/{x}","rb").read(); rel.append(f" {hashlib.md5(data).hexdigest()} {len(data)} {x}")
    rel.append("SHA256:")
    for x in ("Packages","Packages.gz"):
        data=open(f"{d}/{x}","rb").read(); rel.append(f" {hashlib.sha256(data).hexdigest()} {len(data)} {x}")
    open(f"{d}/Release","w").write("\n".join(rel)+"\n")
    print(f"{root}: {len(pk)} pkgs {size/1e9:.1f} GB -> {d}")
print(f"TOTAL {len(jobs)} files {total/1e9:.1f} GB")
open(f"{M}/aria2.list","w").write("".join(jobs))
