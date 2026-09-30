# Lessons from the reference build (Sept 2026)
- USB NVMe enclosures on RTL9210 bridges drop under sustained I/O when the kernel runs them on `uas`. Force usb-storage: `options usb-storage quirks=0bda:9210:u` in modprobe.d, rebind, then check `readlink /sys/bus/usb/devices/<dev>/*:1.0/driver` on EVERY host before bulk work.
- A bus-powered hub cannot feed four NVMes under load; it disconnects all of them at once. Put source and destination of any bulk move on different controllers.
- Move data with verify-before-delete (`tools/reorg.py`: rsync, `rsync -c` dry-run must be clean, then remove the source; journal only on success; check mount + st_dev before every action). It turned two dropouts into zero loss.
- `hf download` hangs on repos with thousands of files (Piper voices). Use `fetch/hf-file.sh` (aria2c per file) for those.
- pip's resolver can spin for 30+ minutes on one project. Wrap every `pip download` in `timeout`.
- Node repos: use the mirrored Node 24, fall back to `pnpm install --no-frozen-lockfile`, and have bun on PATH; some need a newer pnpm than you mirrored.
- `--exclude a b` is not how `hf` takes patterns; repeat the flag. Check the exit code AND that files landed.
- Keep raw releases where the island can convert them (llama.cpp convert + quantize, ComfyUI-GGUF, llm-compressor, a shard-merge/fp8 script). Space is cheaper than a missing format.
- Categories by purpose, not by wave. "Wave 2" means nothing to the next reader.
