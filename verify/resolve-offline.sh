#!/bin/bash
. "$(dirname "$0")/../ark.env"
# Resolve every requirements file and every python project against ONLY the wheel mirror.
S=$ARK_SOFTWARE
python3 -m venv --without-pip ~/depaudit/venv 2>/dev/null; PY=~/depaudit/venv/bin/python
[ -x $PY ] || PY=python3
P="$HOME/depaudit/venv/bin/pip install --dry-run --ignore-installed --no-index --find-links $S/wheels --disable-pip-version-check --no-warn-script-location"
export PIP_NO_CACHE_DIR=1 TMPDIR=~/depaudit/tmp; mkdir -p $TMPDIR
cd $S/src
for req in */requirements*.txt; do
  out=$(timeout 240 $P -r "$req" 2>&1 >/dev/null); rc=$?
  if [ $rc -eq 0 ]; then echo "OK   $req"; else echo "FAIL $req :: $(echo "$out" | grep -oE "No matching distribution found for [^ ]+.*|Could not find a version that satisfies the requirement [^ ]+.*|ERROR: .*|Invalid requirement.*" | head -2 | tr '\n' ' | ')"; fi
done > ~/depaudit/reqs.log 2>&1
SKIP="pytorch__pytorch|ROCm__pytorch|onnxruntime|blender|godot|nodejs__node|numpy__numpy|opencv|cpython|pytorch__vision|pytorch__audio|mediapipe|manifold|PyMeshLab|pedalboard|pysam|yosys|OpenROAD|tauri|django|open-webui|mne-lsl|uv$"
for d in */; do d=${d%/}; [ -f $d/pyproject.toml ] || [ -f $d/setup.py ] || continue
  echo "$d" | grep -qE "$SKIP" && { echo "SKIP $d (native build; checked via requirements only)"; continue; }
  out=$(timeout 300 $P "./$d" 2>&1 >/dev/null); rc=$?
  if [ $rc -eq 0 ]; then echo "OK   $d"; else echo "FAIL $d :: $(echo "$out" | grep -oE "No matching distribution found for [^ ]+.*|Could not find a version that satisfies the requirement [^ ]+.*|ERROR: .*|error: .*" | head -2 | tr '\n' ' | ')"; fi
done > ~/depaudit/projects.log 2>&1
echo PYRESOLVE-DONE >> ~/depaudit/projects.log
