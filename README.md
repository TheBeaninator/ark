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

## What is in the ark

Numbers are live counts from `manifest/` (588 repos, 138 weight repos, 21 datasets, 43 reference sets, 12 container images). The drill-down with every entry is `docs/directory.html`.

### Capabilities, not just lists

An island with this mirror can, with no network:

- **Run** any current open model: llama.cpp (Vulkan, ROCm, CPU builds), vLLM, SGLang, exo and prima.cpp for multi-box serving, Colibrì for streaming 744B-class MoE models from NVMe, llama-swap to route between them, Open WebUI and friends on top.
- **Convert** what it holds: raw release to GGUF (convert + quantize + imatrix), to FP8 or W4A16 for vLLM (llm-compressor), to ComfyUI single-file (shard merge + fp8 cast) or GGUF (ComfyUI-GGUF), abliteration (heretic), merging (mergekit). Raw releases are kept precisely so every other format can be derived.
- **Teach** its models: unsloth, axolotl, LLaMA-Factory, ms-swift, torchtune, peft/trl; RL with verl, OpenRLHF, ART, SkyRL; diffusion and video LoRA trainers (ai-toolkit, diffusion-pipe, kohya, musubi-tuner, OneTrainer, SimpleTuner); evaluation with lm-evaluation-harness, lighteval, inspect_ai; starter datasets for each of those.
- **Make media**: ComfyUI with 62 node packs for image, video, audio and 3D (Wan, Hunyuan, LTX, FramePack, Qwen-Image, Flux, TRELLIS, Hunyuan3D), upscaling and restoration, face tools, matting and inpainting; audio stem separation, voice conversion, TTS and music generation; Blender, Godot and the rest of the 3D and game toolchains.
- **Talk**: a complete voice-assistant stack (speech-to-speech models, streaming STT and TTS, VAD, wake word, turn-taking, pipelines) that runs end to end on local hardware.
- **Act**: 42 agent harnesses and frameworks, 28 multi-agent and swarm frameworks, orchestration, the MCP/A2A/AG-UI protocols, parallel coding agents, and decision models (Jev-style one-pass typed answers) for cheap, calibrated routing and judging.
- **Know**: Wikipedia, Stack Overflow, Gutenberg and DevDocs as Kiwix ZIMs; retrieval and document tooling (vector stores, RAG frameworks, embedders, parsers) to make them searchable.
- **Build**: Python 3.12/3.13/3.14 with wheel lanes proven to resolve offline, Node/Go/Rust/bun toolchains with offline registries, a latest-only apt mirror plus ROCm and CUDA pools, container images for the heavy services, and firmware toolchains for the island's own microcontrollers.
- **Specialise**: genome analysis with GRCh38 reference data, circuit design and HDL simulation, 3D capture, BCI/EEG tooling.

### Category guide (`manifest/repos.tsv`)

| category | repos | what it holds |
|---|---|---|
| `inference` | 16 | llama.cpp and ik_llama.cpp, whisper.cpp, llama-swap, Open WebUI, stable-diffusion.cpp, ollama, koboldcpp, text-generation-webui, SillyTavern, mlc-llm, Colibrì |
| `multi-box` | 7 | exo, distributed-llama, prima.cpp, lemonade, vLLM, SGLang, LiteLLM |
| `decision-models` | 17 | kev, decider, von, Laya runners, AnyJev/LLM2Jev (turn any LLM into a decision model), openjev/lichen servers, jevlike |
| `ml-frameworks` | 38 | PyTorch, transformers, diffusers, safetensors, tokenizers, ROCm and Vulkan stacks, ONNX Runtime, OpenCV, numpy, CPython, uv, docker/podman |
| `training`, `training-diffusion` | 29 | unsloth, axolotl, LLaMA-Factory, ms-swift, torchtune, litgpt, open-instruct, verl, OpenRLHF, ART, SkyRL, Megatron, nanotron, DeepSpeed, Liger, flash-attention; ai-toolkit, diffusion-pipe, kohya, musubi-tuner, OneTrainer, SimpleTuner |
| `quantisation`, `conversion` | 9 | llm-compressor, GPTQModel, exllamav3, optimum(-quanto), torchao, mergekit, heretic |
| `eval-data` | 8 | lm-evaluation-harness, lighteval, inspect_ai, evaluate, datasets, datatrove, distilabel |
| `model-source` | 24 | the upstream repos of models we hold (TRELLIS, Pixal3D, Hunyuan3D, Wan, LTX, Flux, Qwen-Image, ACE-Step, Qwen3-TTS/ASR, VibeVoice, CosyVoice, OCR models) |
| `comfyui` | 62 | ComfyUI and Manager plus the node packs for video, audio, 3D, upscaling, inpainting, control, and workflow quality of life |
| `image-video` | 26 | model code for held image/video weights, FramePack, vision utilities (YOLO, SAM2, Depth-Anything, insightface, Real-ESRGAN, SUPIR, CodeFormer, rembg, BiRefNet), MMAudio, pyannote, bark, YuE |
| `media-tooling`, `audio-restoration` | 29 | FFmpeg, Audacity, Kdenlive, GIMP, Inkscape, Krita, ImageMagick, demucs, audiocraft, stable-audio; stem separation, voice conversion, denoise and restoration, forced alignment, mastering |
| `voice` | 36 | Qwen3-Omni, Moshi/Unmute/Pocket TTS, Ultravox, CSM, GLM-4-Voice, Step-Audio, faster-whisper, moonshine, kokoro, piper, Dia, Orpheus, fish-speech, silero-vad, openWakeWord, smart-turn, pipecat, LiveKit agents, wyoming |
| `agents` | 42 | coding harnesses (deepseek-harness, hermes-agent, opencode, OpenHands, goose, aider, qwen-code, cline, codex, gemini-cli, Claude Code and SDKs, continue, Roo, kilocode), smolagents, crewAI, autogen, langgraph, pydantic-ai, letta, OpenAI Agents, ADK, mastra, llama_index, browser-use, mem0, MCP SDKs, dify, n8n, langflow |
| `multi-agent`, `orchestration` | 42 | AgentScope, swarms, agency-swarm, claude-flow, Microsoft agent-framework, Semantic Kernel, Magentic-UI, AG2, Agno, CAMEL/OWL, MetaGPT, ChatDev; LangChain, deepagents, deer-flow, Haystack, DSPy, Composio, Flowise |
| `agent-protocols`, `coding-agents`, `fronts-eval` | 30 | A2A, AG-UI, fastmcp, mcp-use; vibe-kanban, claude-squad, humanlayer, stagewise, SWE-ReX, pr-agent, skills; LibreChat, AnythingLLM, Lobe Chat, NeMo Guardrails, SWE-bench, AgentBench |
| `retrieval` | 16 | chroma, qdrant, faiss, lancedb, pgvector, ragflow, txtai, LightRAG, graphrag, sentence-transformers, FlagEmbedding, colpali, docling, marker, unstructured, PyMuPDF |
| `dev-infra`, `dev-toolchains`, `offline-reference` | 26 | gitea, jupyterlab, marimo, mkdocs, pandoc, typst, neovim, emacs; node, go, code-server, git, sqlite, postgres, redis, nginx, flask, fastapi, django, electron, tauri, flutter; kiwix and zim tools |
| `embedded`, `edge-vision` | 20 | platformio, esp-idf, pico-sdk, arduino-cli and cores, QMK, freerouting; Grove Vision AI V2 / Himax WiseEye2 toolchain (SSCMA, vela, tflite-micro, LiteRT, onnx2tf) |
| `games`, `3d` | 33 | Godot, Bevy, raylib, LÖVE, SDL, pygame, Phaser, Defold, GDevelop, Tiled, LDtk, glTF samples, Google Fonts; Blender, FreeCAD, OpenSCAD, CadQuery, MeshLab, Open3D, trimesh, slicers, colmap, nerfstudio, Meshroom, gaussian-splatting |
| `circuit-design` | 25 | KiCad and its libraries, ngspice, Verilator, Icarus, yosys, nextpnr, OpenROAD, openEMS, LibrePCB, GHDL, nvc, VUnit, cocotb, CERN's colibri VHDL library |
| `genome` | 27 | samtools, bcftools, minimap2, bwa, GATK, VEP, SnpEff, DeepVariant, fastp, bedtools, MultiQC, IGV, biopython, nextflow, snakemake, bioconda recipes (plus GRCh38 reference data under `reference.tsv`) |
| `bci-biosignals` | 26 | brainflow, OpenBCI, MNE, LSL, EEGLAB, braindecode, pyRiemann, NeuroKit, YASA, muse-lsl, timeflux, pupil, mediapipe, OpenFace, rPPG, PsychoPy, LaBraM |

### Weights, data and the rest

- `models.tsv`: 32 raw releases and 26 GGUF repos are the deliberate picks (newest of each model line, Sept 2026); 56 helper-weight repos and 24 Comfy assets are dependencies that mirrored code loads at first run, each annotated with what needs it.
- `datasets.tsv`: pretraining sample, SFT, preference, reasoning, code-instruction, eval sets, TTS and small image sets, decision-model suites.
- `reference.tsv`: Wikipedia, Stack Overflow, Gutenberg and ~70 DevDocs ZIMs; GRCh38 assembly, GTF, VEP cache, ClinVar, dbSNP, a gnomAD sample.
- `assets.tsv`: CC0 HDRIs, textures and materials. `containers.tsv`: gitea, qdrant, chroma, jupyter, pgvector, postgres, redis, nginx, ollama, open-webui, ragflow, valkey. `pypi-extra.txt`, `apt.txt`: packages and pools beyond what repos declare.

## Private overlay
Anything you do not want in the public list goes in `manifest-private/` (same files, same columns, git-ignored). Every fetcher reads it after `manifest/`; the validator checks it locally.

## Directory
The directory is published at **https://thebeaninator.github.io/ark/** (rebuilt by GitHub Pages on every push from `manifest/`). The same page is checked in as `docs/directory.html`; regenerate locally with `python3 report/gen-ark-directory.py` (add `--private` to include the overlay; that output is git-ignored).

## Contributing
Add a line, not code: see `CONTRIBUTING.md`. CI validates that every reference resolves.

## Provenance
Built from the reference build on a fleet of AMD Strix Halo boxes with a six-drive USB store (Sept 2026). `docs/LESSONS.md` records what broke and what fixed it. The reference build's own layout is in `docs/LAYOUT.md`.

## Licence
Scripts and docs: MIT. The manifest lists third-party works under their own licences; check each before redistribution.
