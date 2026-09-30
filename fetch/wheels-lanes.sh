#!/bin/bash
. "$(dirname "$0")/../ark.env"
# python-lanes.sh (bigboy, run as dad) — "long voyage" Python provisioning. Claude 2026-09-29.
#  1. CPython 3.12 / 3.13 / 3.14 relocatable builds (python-build-standalone) -> binaries/python/  (uv-mirror layout + plain tar use)
#  2. cp313 wheel lane: every requirements/project in src/ + torch ROCm7.2/CPU stack for cp313 (ROCm ships cp312+cp313; NO cp314 torch yet)
#  3. cp314 wheel lane: best effort (pure-python + whatever ships cp314; native gaps fall back to sdists)
#  4. offline resolve check per lane (pip --dry-run --no-index against wheels/) -> ~/depaudit/reqs-cp31X.log projects-cp31X.log
#  then re-runs the cp312 check (pyresolve.sh) so the new waves are covered. Idempotent/resumable. Log: ~/python-lanes.log
export PATH=/home/dad/miniconda3/bin:/home/dad/.local/bin:$PATH
S=$ARK_SOFTWARE; B=$S/binaries/python; TAG=20260929; log(){ echo "$(date -Is) $*"; }
mountpoint -q /mnt/nv2 || { log "FAILED: /mnt/nv2 not mounted"; exit 1; }; cd $S; mkdir -p $B/$TAG ~/depaudit/tmp
A="$HOME/.local/bin/aria2c -c -x4 -s4 --file-allocation=none --auto-file-renaming=false --console-log-level=warn --summary-interval=0"
log "== 1. CPython builds ($TAG)"
for v in 3.12.14 3.13.15 3.14.7; do for arch in x86_64 x86_64_v3 aarch64; do f=cpython-$v+$TAG-$arch-unknown-linux-gnu-install_only_stripped.tar.gz
  [ -s $B/$TAG/$f ] || $A -d $B/$TAG "https://github.com/astral-sh/python-build-standalone/releases/download/$TAG/$f" >/dev/null 2>&1 || log "  FAIL $f"; done; done
[ -s $B/$TAG/SHA256SUMS ] || $A -d $B/$TAG "https://github.com/astral-sh/python-build-standalone/releases/download/$TAG/SHA256SUMS" >/dev/null 2>&1
( cd $B/$TAG && grep -F "$(ls *.tar.gz)" SHA256SUMS | sha256sum -c --quiet && log "  sha256 ok: $(ls *.tar.gz | wc -l) tarballs" || log "  SHA MISMATCH in $B/$TAG" )
cat > $B/README.md <<'R'
# CPython relocatable builds (astral-sh/python-build-standalone, install_only_stripped)
<tag>/cpython-<ver>+<tag>-<arch>-unknown-linux-gnu-install_only_stripped.tar.gz  (+ .sha256)   arch: x86_64 (portable), x86_64_v3 (AVX2, Strix/Zen), aarch64 (phones/SBCs)
Plain use:   tar xf <tarball> -C /opt && /opt/python/bin/python3.14 -m venv ~/venv
uv offline:  UV_PYTHON_INSTALL_MIRROR=file://$ARK_SOFTWARE/binaries/python  uv python install 3.14   (layout mirrors the GitHub release path;
             uv's own manifest must know this tag — if the mirrored uv is older, use the plain tar route)
Lanes (2026-09-29): cp312 = primary (full ROCm torch stack, everything resolved).  cp313 = secondary GPU lane (ROCm 7.2 ships cp313 torch).
cp314 = pure-python/tools lane only: NO ROCm/CUDA torch cp314 wheels exist yet (pytorch#156856, ROCm#5920); native pkgs may need sdist builds (build-essential from the nv4 mirror).
Resolve reports: bigboy ~/depaudit/reqs-cp31X.log / projects-cp31X.log (FAIL lines = what is missing for that lane).
R
py(){ tar tf $B/$TAG/cpython-$1*-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz >/dev/null 2>&1 || return 1; d=~/depaudit/py$1; [ -x $d/python/bin/python3 ] || { mkdir -p $d; tar xf $B/$TAG/cpython-$1.*-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz -C $d; }; echo $d/python/bin/python3; }
lane(){ v=$1; abi=cp${v/./}; PY=$(py $v) || { log "  no interpreter for $v"; return; }
  [ -x ~/depaudit/venv$abi/bin/pip ] || $PY -m venv ~/depaudit/venv$abi >/dev/null 2>&1
  PIP=~/depaudit/venv$abi/bin/pip; $PIP install -q -U pip >/dev/null 2>&1
  PD="$PIP download --dest wheels --disable-pip-version-check -q --python-version $v --implementation cp --abi $abi --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --only-binary=:all:"
  SD="$PIP download --dest wheels --disable-pip-version-check -q --no-deps --no-binary=:all:"
  log "== lane $abi: torch stack"; for idx in rocm7.2 cpu; do $PD --index-url https://download.pytorch.org/whl/$idx --extra-index-url https://pypi.org/simple torch torchvision torchaudio >/dev/null 2>&1 && log "  torch $idx $abi ok" || log "  torch $idx $abi: none (expected for cp314)"; done
  log "== lane $abi: requirements + projects"; n=0
  for r in src/*/requirements*.txt; do n=$((n+1)); $PD -r "$r" >/dev/null 2>&1 || grep -vE "^\s*(#|$|-r|--|-e|git\+|http)" "$r" | sed -E 's/#.*//; s/;.*//' | while read -r l; do $PD "$l" >/dev/null 2>&1 || $SD "$l" >/dev/null 2>&1 || log "  $abi unfetchable $r: $l"; done; done
  for d in src/*/; do d=${d%/}; { [ -f $d/pyproject.toml ] || [ -f $d/setup.py ]; } || continue; echo "$d" | grep -qE "pytorch__pytorch|ROCm__pytorch|onnxruntime|blender|godot|nodejs__node|numpy__numpy|opencv|cpython|pytorch__vision|pytorch__audio|mediapipe|manifold|PyMeshLab|pedalboard|pysam|yosys|OpenROAD|tauri|django|open-webui|mne-lsl|uv$" && continue
    $PD "./$d" >/dev/null 2>&1 || $PD --no-deps "./$d" >/dev/null 2>&1 || log "  $abi project deps miss $d"; done
  log "  wheels now: $(ls wheels | wc -l) ($(ls wheels | grep -c $abi) $abi); nv2 free $(df -h /mnt/nv2 | awk 'NR==2{print $4}')"
  log "== lane $abi: offline resolve check"
  P="$PIP install --dry-run --ignore-installed --no-index --find-links $S/wheels --disable-pip-version-check --no-warn-script-location"; export PIP_NO_CACHE_DIR=1 TMPDIR=~/depaudit/tmp
  ( cd src; for req in */requirements*.txt; do out=$(timeout 240 $P -r "$req" 2>&1 >/dev/null); [ $? -eq 0 ] && echo "OK   $req" || echo "FAIL $req :: $(echo "$out" | grep -oE "No matching distribution found for [^ ]+.*|Could not find a version that satisfies the requirement [^ ]+.*|ERROR: .*" | head -2 | tr '\n' ' | ')"; done ) > ~/depaudit/reqs-$abi.log 2>&1
  ( cd src; for d in */; do d=${d%/}; { [ -f $d/pyproject.toml ] || [ -f $d/setup.py ]; } || continue; out=$(timeout 300 $P "./$d" 2>&1 >/dev/null); [ $? -eq 0 ] && echo "OK   $d" || echo "FAIL $d :: $(echo "$out" | grep -oE "No matching distribution found for [^ ]+.*|Could not find a version that satisfies the requirement [^ ]+.*|ERROR: .*|error: .*" | head -2 | tr '\n' ' | ')"; done ) > ~/depaudit/projects-$abi.log 2>&1
  log "  $abi resolve: reqs $(grep -c ^OK ~/depaudit/reqs-$abi.log) ok / $(grep -c ^FAIL ~/depaudit/reqs-$abi.log) fail; projects $(grep -c ^OK ~/depaudit/projects-$abi.log) ok / $(grep -c ^FAIL ~/depaudit/projects-$abi.log) fail"
}
free=$(df --output=avail -BG /mnt/nv2 | tail -1 | tr -dc 0-9); [ "$free" -gt 60 ] || { log "FAILED: only ${free}G free on nv2; lanes need headroom"; exit 1; }
lane 3.13
lane 3.14
log "== cp312 re-check (pyresolve.sh, covers the voice + swarm waves)"; bash ~/depaudit/pyresolve.sh; log "  cp312 resolve: reqs $(grep -c ^OK ~/depaudit/reqs.log) ok / $(grep -c ^FAIL ~/depaudit/reqs.log) fail; projects $(grep -c ^OK ~/depaudit/projects.log) ok / $(grep -c ^FAIL ~/depaudit/projects.log) fail"
log "wheels total $(du -sh wheels | cut -f1); nv2 free $(df -h /mnt/nv2 | awk 'NR==2{print $4}')"; log "LANES-DONE"
