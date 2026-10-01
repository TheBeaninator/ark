# Layout on disk (the reference build)
```
$ARK_MODELS/<Org__Repo>/raw/            the Hugging Face release as published (re-quant source)
$ARK_MODELS/<Org__Repo>/gguf/           llama.cpp quants; companions (mmproj, mtp, dflash) at the model root
$ARK_HF_ASSETS/<org>/<repo>/            helper weights that mirrored code downloads at first run (point HF_HOME / HF_HUB_OFFLINE=1 here)
$ARK_SOFTWARE/src/<host>__<owner>__<repo>/   latest-only shallow clones (Node repos carry node_modules/)
$ARK_SOFTWARE/{wheels,binaries,debs,rocm,containers,cargo-home,cmake-deps,gomodcache,npm-cache,pnpm-store,bun-cache,embedded,docs}/
$ARK_SOFTWARE/binaries/python/<tag>/    python-build-standalone tarballs (uv-mirror layout)
$ARK_SOFTWARE/binaries/iso/             OS installer ISOs + their SHA256SUMS (reference.tsv kind=iso)
$ARK_DATA/reference/{zim,genome}/  $ARK_DATA/datasets/<org__name>/  $ARK_DATA/assets/{polyhaven,ambientcg}/
comfy/<type>/<base>/                    ComfyUI assets: one root, one extra_model_paths entry
```
Indexes: `verify/catalog.sh` (size/mtime/path of everything) and `verify/hash-manifest.sh` (sha256 per file, incremental). After moving things, `tools/migrate-manifest.py` rewrites paths from `tools/reorg.py`'s journal instead of re-hashing.
Wheel lanes: the primary lane is the Python with a GPU torch build for your hardware (3.12 for ROCm as of 2026-09), a second GPU lane where one exists (3.13), and a tools-only lane (3.14: no GPU torch anywhere yet). `verify/resolve-offline.sh` proves every requirements file in `src/` resolves against `wheels/` alone; its FAIL lines are the honest gap list.
