#!/usr/bin/env python3
"""migrate-manifest.py — rewrite paths in /mnt/nv2/MANIFEST.tsv using reorg's journal (moves/renames) so nothing gets re-hashed;
drop rows whose file no longer exists at old or new path. Also rewrites /media/dad/nv2 -> /mnt/nv2 and /mnt/weights -> /mnt/nv5."""
import os,shutil,time
M='/mnt/nv2/MANIFEST.tsv'; J=os.path.expanduser('~/storage-review/plan/journal.tsv')
moves=[]   # (src,dst) longest-first
for line in open(os.path.expanduser('~/storage-review/plan/reorg.log')):
    # lines: [P] KIND src -> dst: result   (only successful moves/renames)
    if ('] MOVE' in line or '] MV ' in line) and (': renamed' in line or ': moved' in line):
        body=line.split('] ',1)[1]; kind,rest=body.split(' ',1); sd,res=rest.rsplit(': ',1); src,dst=sd.split(' -> ')
        moves.append((src.rstrip('/'),dst.rstrip('/')))
moves.sort(key=lambda x:-len(x[0]))
shutil.copy(M,M+'.bak-'+time.strftime('%F')); out=[]; kept=dropped=rewritten=0
for line in open(M):
    parts=line.rstrip("\n").split("\t",2)
    if len(parts)!=3 or not parts[2].startswith("/"): dropped+=1; continue
    h,s,p=parts; p0=p
    p=p.replace('/media/dad/nv2/','/mnt/nv2/').replace('/mnt/weights/','/mnt/nv5/')
    for a,b in moves:
        if p==a or p.startswith(a+'/'): p=b+p[len(a):]; break
    if os.path.exists(p): out.append(f'{h}\t{s}\t{p}\n'); kept+=1; rewritten+=(p!=p0)
    else: dropped+=1
open(M,'w').writelines(out); print(f'manifest: kept {kept} (rewritten {rewritten}), dropped {dropped} missing; backup {M}.bak-*')
