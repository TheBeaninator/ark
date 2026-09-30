# ark

Provisions for an AI island: a **manifest of references** (git repos, model weights, datasets, reference data, assets, containers, packages) and **fetchers** that turn it into a complete offline mirror — enough to run, convert, fine-tune and build with no resupply.

The manifest is data. Nothing in this repo is a model or a dataset; `manifest/*.tsv` says what to get, `fetch/` gets it, `verify/` proves it is complete and intact, `report/` renders the ship's ledger.

## Quick start
```
cp ark.env ark.local.env && $EDITOR ark.local.env     # ARK_ROOT etc.; one filesystem is fine
. ark.local.env
fetch/repos.sh                 # ~500 shallow clones (latest only)
fetch/wheels-lanes.sh          # CPython builds + wheels for every requirements file in src/, per lane
fetch/apt-mirror.py            # latest-only apt mirror (Ubuntu noble + ROCm/CUDA/docker pools; see manifest/apt.txt)
fetch/hf-models.sh             # weights -> models/<Org__Repo>/{raw,gguf}, helper weights -> hf-assets/
fetch/hf-datasets.sh  fetch/reference.sh  fetch/assets.py "$ARK_DATA/assets"  fetch/containers.sh  fetch/embedded.sh
verify/resolve-offline.sh      # does everything in src/ install from wheels/ alone?  FAIL lines = your gap list
verify/catalog.sh && verify/hash-manifest.sh
python3 report/inventory.py && python3 report/gen-manifest.py inventory.json manifest.html
```
Fetchers are idempotent and resumable; re-run them to refresh. Expect several TB and days on a fast link for the full set; start with `fetch/repos.sh` and the wheel lanes, which are the part that makes everything else usable.

## What is in the manifest (2026-09-30)
About 525 repos in 31 purpose-based categories (inference engines, multi-box serving, ML frameworks, conversion and quantisation, training and RL, ComfyUI and its helper nodes, image/video and vision helpers, voice-assistant stack, audio restoration, agent harnesses, multi-agent and orchestration frameworks, agent protocols, coding agents, retrieval and documents, decision models, developer toolchains and island infrastructure, embedded firmware, games, 3D modelling and capture, circuit design, genome analysis, BCI/biosignals); ~120 weight repos; 17 datasets; Wikipedia, Stack Overflow, DevDocs and Gutenberg ZIMs; GRCh38 reference data; CC0 HDRIs/textures; 13 containers; Python 3.12/3.13/3.14 with three wheel lanes.

## Contributing
Add a line, not code: see `CONTRIBUTING.md`. CI validates that every reference resolves.

## Provenance
Built from the reference build on a fleet of AMD Strix Halo boxes with a six-drive USB store (Sept 2026). `docs/LESSONS.md` records what broke and what fixed it. The reference build's own layout is in `docs/LAYOUT.md`.

## Licence
Scripts and docs: MIT. The manifest lists third-party works under their own licences; check each before redistribution.
