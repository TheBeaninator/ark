# What the island can do with a raw release (all mirrored)
LLM raw -> GGUF: llama.cpp `convert_hf_to_gguf.py`, `llama-quantize`, `llama-imatrix`; ik_llama.cpp for extra quant types.
LLM raw -> FP8 / W4A16 / AWQ for vLLM: llm-compressor + compressed-tensors; GPTQModel; exllamav3.
Abliteration: heretic. Merging: mergekit. Fine-tuning: unsloth, axolotl, LLaMA-Factory, ms-swift, torchtune, peft/trl; RL: verl, OpenRLHF, ART, SkyRL.
Diffusion/video raw -> Comfy single file: shard merge + fp8 cast (`repack_fp8.py` in the reference build's docs/repack); raw -> GGUF: ComfyUI-GGUF `tools/convert.py`. LoRA trainers: ai-toolkit, diffusion-pipe, kohya, musubi-tuner, OneTrainer, SimpleTuner.
Decision models (typed answers in one pass): AnyJev / LLM2Jev turn any held LLM into one; kev, decider, Laya, von ship weights.
