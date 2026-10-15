# Mesh2Motion kit: everything the island needs to run, build and extend it

Mesh2Motion (`games` rows in `manifest/repos.tsv`) is a browser auto-rigger and CC0 animation library, the open Mixamo
replacement. Its own README lists Node and a browser. This page is the real bill of materials, found by reading the
three repos (2026-10-15, app HEAD of 2026-10-06), and where each item lives in the ark.

## Three tiers of use

| tier | what you do | needs |
|---|---|---|
| **use** | rig a mesh, export animations | the app repo (static/ carries all 70 MB of rigs, animations, previews), Node 24, `npm ci`, a browser |
| **build desktop** | a Tauri binary for machines without a dev toolchain | the above + Rust ≥ Tauri 2 MSRV, cargo-home, webkit2gtk dev libs, linuxdeploy tools |
| **author** | new rigs/animations, mocap retargeting, preview clips | Blender 5.x, the assets repo, a BVH source (Mocopi), the in-browser preview generator |

## Bill of materials

### Code (repos.tsv, `fetch/repos.sh`)
| item | row | notes |
|---|---|---|
| mesh2motion-app | `games` | Vite 8 / TS 6 / three 0.185; multi-page build (`index`, `create`, `retarget/`); `.nvmrc` 24.11.0 |
| mesh2motion-assets | `games` | ~385 MB, no LFS; `.blend` sources saved by **Blender 5.0**, mocap add-on wants 4.2+ |
| mesh2motion-desktop | `games` | Tauri 2.11 wrapper; the app is a **git submodule** pinned to a commit, `fetch/repos.sh --recurse-submodules` picks it up; `Cargo.lock` under `src-tauri/` (depth 2, within cargo.sh's `-maxdepth 3`) |
| three.js | `media-tooling` | already mirrored; the app imports `addons/loaders/{GLTF,FBX,Collada}Loader`, `GLTFExporter`, `OrbitControls`, `TransformControls`, `NURBSCurve`, `fflate` |
| google/fonts | `games` | already mirrored; `ofl/jost/Jost[wght].ttf` is the font `styles.css` fetches from fonts.googleapis.com at runtime |
| tauri-apps/tauri, nodejs/node | `dev-toolchains` | already mirrored (source) |

### npm (`npm ci` in the clone; `$ARK_SOFTWARE/src/github.com__Mesh2Motion__mesh2motion-app/node_modules`)
`package-lock.json` resolves 325 packages. Things the author would not list:
- **wrangler 4 + workerd** (Cloudflare deploy CLI, a 90 MB native binary) is a *runtime* dependency in `package.json`, so `npm ci` cannot skip it. Harmless, never invoked offline.
- **sharp / libvips** prebuilt binaries ride in via wrangler, platform-specific optional deps (82 entries). `npm ci` on x86-64 Linux bakes only linux-x64; an aarch64 island node would need its own install.
- Install scripts run for `esbuild`, `workerd`, `fsevents` (macOS only). All are "verify the prebuilt binary" scripts; no compiler needed.
- `@comfyorg/fbx-exporter-three` is the FBX exporter (the app vendors its own FBX *loader* under `src/lib/io/fbx`).
- Dev/test: vitest 4 + jsdom 30 + `@vitest/coverage-v8`, eslint 10. No Playwright/Chrome.
- Not present and worth knowing: **no Draco, KTX2/Basis or meshopt decoder**. A Draco-compressed GLB will not import; decompress with Blender or `gltf-transform` first.

### Binaries (reference.tsv `url` rows, `fetch/reference.sh` → `$ARK_DATA/reference/<target>/`)
| target | item | why |
|---|---|---|
| `toolchains/node-v24.22.0-linux-x64` | Node 24 LTS tarball | noble ships nodejs 18; vite 8 / vitest 4 need ≥ 20 |
| `toolchains/rust-1.99.1-x86_64-unknown-linux-gnu` | Rust stable standalone installer | noble's rustc 1.75 is below Tauri 2's MSRV; `fetch/cargo.sh` needs cargo ≥ 1.85 and looks for `rust-*.tar.*` in **`$ARK_SOFTWARE/binaries/`**: copy or link it there |
| `3d/blender-5.2.2-linux-x64` | Blender 5.2.2 release tarball (383 MB) | the assets are 5.0 files, noble has 4.0.2; building `blender/blender` needs its precompiled `lib-linux_x64` tree (multi-GB, not mirrored) |
| `tauri/bundler-tools` | `linuxdeploy-x86_64.AppImage` (tauri-apps build `07333c6`), `AppRun-x86_64`, `linuxdeploy-plugin-appimage-x86_64.AppImage` | **tauri-bundler downloads these during `tauri build`** for the `appimage` target. Pre-seed `~/.cache/tauri/` with them named `linuxdeploy-07333c6-x86_64.AppImage`, `AppRun-x86_64`, `linuxdeploy-plugin-appimage.AppImage`, or build only the `deb` target (`tauri build --bundles deb`), which downloads nothing |

### Crates (`fetch/cargo.sh`, `$ARK_SOFTWARE/cargo-home`)
`src-tauri/Cargo.lock` lists 477 crates (tauri 2.11.2, wry 0.55.1, tao 0.35.3, gtk 0.18.2). Covered by pass 1 of
`fetch/cargo.sh` once the desktop repo is in `src/`. Build with `CARGO_HOME=<copy> cargo build --offline --locked`.

### Debs (`verify/apt-mesh2motion.txt`, check with `verify/apt-coverage.sh verify/apt-mesh2motion.txt`)
All from noble main/universe, which the apt mirror carries in full: webkit2gtk 4.1 dev + runtime, ayatana-appindicator,
librsvg, libxdo, libssl, patchelf, libfuse2 (AppImage), gstreamer (webkit media), the X/GL/Wayland libs the Blender
tarball dlopens, docker-ce for the compose path.

### Container (containers.tsv, `fetch/containers.sh`)
`node:24-alpine`, the base of `mesh2motion-app/Dockerfile`, so `docker compose up` works as documented.

## Things that only work online (and what happens offline)
- **Google Fonts**: `src/styles.css` `@import`s Jost from fonts.googleapis.com. Offline the browser falls back to the
  system sans-serif. To fix properly, install `Jost[wght].ttf` from the mirrored google/fonts repo and replace the import
  with a local `@font-face`.
- **Telemetry**: `DownloadSuccessDialog` and `AnimationRequestDialog` POST to `mesh2motion-app.scottpetrovic.workers.dev`
  (a Cloudflare Worker + D1, source in `src/survey-worker.js`, config in `wrangler.jsonc`). Offline the fetch rejects and
  is caught; nothing else depends on it. `PROCESS_ENV` in `vite.config.js` only exposes Cloudflare CI variables.
- **Mocap capture**: `mesh2motion-assets/motion-capture/` retargets **Sony Mocopi** BVH files with a bundled Blender
  extension (`blender-plugin/`, Blender 4.2+, no Rokoko add-on needed any more). The hardware and its phone app are the
  only non-mirrorable part; any BVH at 0.01 scale with the same bone names goes through the same path.
- **Affinity files**: `graphic-design/*.af*` are Affinity Designer/Publisher sources (proprietary, Windows/macOS only).
  Everything derived from them is already exported as PNG/SVG in the app's `static/images`. Krita (`.kra`) is mirrored.

## Bring-up on the island
```
export PATH=$ARK_DATA/reference/toolchains/node-v24.22.0-linux-x64/bin:$PATH   # after tar -xf
cd $ARK_SOFTWARE/src/github.com__Mesh2Motion__mesh2motion-app
npm ci --prefer-offline --no-audit --no-fund       # or reuse the node_modules shipped in the clone
npm run dev -- --host                               # http://<node>:5173 ; /preview-generator/ and /retarget/ live there too
npm run build                                       # dist/ is a static site: serve with nginx from the mirror
# desktop: tar -xf rust-1.99.1-*.tar.xz && ./rust-1.99.1-*/install.sh --prefix=$HOME/.local
cd ../github.com__Mesh2Motion__mesh2motion-desktop && (cd mesh2motion-app && npm ci --prefer-offline && npm run build)
CARGO_HOME=<writable copy of cargo-home> cargo tauri build --bundles deb --offline   # appimage needs ~/.cache/tauri pre-seeded, see above
# authoring: tar -xf blender-5.2.2-linux-x64.tar.xz ; blender $ARK_SOFTWARE/src/github.com__Mesh2Motion__mesh2motion-assets/3d-models/model-human.blend
```

## Gaps left open
- Rust and Node tarballs land under `$ARK_DATA/reference/toolchains/` because `reference.tsv` has no `binaries/` kind;
  `fetch/cargo.sh` expects the Rust tarball under `$ARK_SOFTWARE/binaries/`. One `cp` or a `binaries` kind in
  `fetch/reference.sh` closes it.
- Only x86-64 tarballs and npm optional deps are listed. Add aarch64 rows if an ARM node ever needs the desktop build.
- Tauri 2.11's MSRV was not pinned here; Rust stable 1.99.1 clears it with margin, but the row will age like the other
  version-pinned `url` rows. Refresh when `inbox-sync` flags it.
