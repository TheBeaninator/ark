# Contributing a reference

ark holds **references, never data**. A contribution is a line in one of the TSV files under `manifest/`. CI checks that the line is well-formed and that the reference resolves. Keep the note column useful: what the thing is for, and anything a fetcher needs to know (gated, huge, licence caveat).

| file | one line per | columns |
|---|---|---|
| `repos.tsv` | git repository (GitHub, GitLab, Codeberg, Bitbucket) | `category  url  note` — append `#<branch>` to the url to track a non-default branch, or `#<full 40-hex commit>` to pin a commit a build depends on (keep the plain row too, so the latest is still mirrored) |
| `models.tsv` | Hugging Face model repo | `hf_id  kind  include  note` — kind `raw` (the release as published), `gguf`, `hf-asset` (helper weights code downloads at first run), `comfy`; `include` = space-separated glob patterns, empty = whole repo |
| `datasets.tsv` | Hugging Face dataset | `hf_id  include  note` |
| `reference.tsv` | offline reference data | `kind  source  pattern_or_target  note` — `zim` (Kiwix directory + filename pattern, latest wins), `zim-set` (brace list of tools), `url` (`{REL}` = latest Ensembl release), `iso`, `findlinks` (pattern = a pip requirement, source = a find-links page: latest wheel), `whence` (source = an amd/xdna-driver `tools/WHENCE`: the NPU firmware it lists) |
| `assets.tsv` | CC0 / permissive asset sources | `source  type  selection  license` |
| `containers.tsv` | docker image | `image  note` |
| `pypi-extra.txt` | PyPI package name beyond the repos' own requirements | one per line |

Rules
- Latest-only. The mirror keeps the current version of each thing; history is not a goal.
- Newest version of a model line only. Add the new one and remove the superseded one in the same change.
- Source access matters, licences do not gate inclusion. Prefer things whose source we can mirror; something without source still gets in if it is good enough, with a note on how to obtain and run it. Note gated repos and licence caveats in the note column; the fetcher tolerates gated repos.
- Categories are kebab-case and by purpose (what it is *for*), never by when it was added.
- Prefer a repo over a wheel and a raw release over a repack: everything else can be derived offline (see `docs/TOOLCHAIN.md`).
- Run `python3 verify/validate-manifest.py --online` before opening a PR.
