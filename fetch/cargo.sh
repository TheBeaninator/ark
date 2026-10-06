#!/bin/bash
# fetch/cargo.sh — fill $ARK_SOFTWARE/cargo-home (an offline cargo registry cache) so Rust builds work air-gapped:
#   1. every Cargo.lock under $ARK_SOFTWARE/src (the mirrored repos)
#   2. every row of manifest/cargo-repos.tsv and manifest-private/cargo-repos.tsv: your OWN Rust repos, which are not
#      in src/ (on 2026-10-03 the pod could not build agent-kanban, factmap or Loom because pass 2 did not exist).
# Rows: name<TAB>git url or local path[#branch]<TAB>note. Every row is cloned into one work dir under its name, so path
# dependencies on sibling repos (factmap -> ../verbkit, loom-integrate -> ../../../buzz) resolve: list the siblings too.
# Needs cargo >= 1.85 (lockfile v4); if the host's is older it unpacks the mirror's own toolchain from binaries/.
# On the target: copy cargo-home to writable storage, CARGO_HOME=<copy>, cargo build --offline --locked.
# Usage: fetch/cargo.sh [src|own|all]   (default all)
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."
export CARGO_HOME=${ARK_CARGO_HOME:-$ARK_SOFTWARE/cargo-home}; mkdir -p "$CARGO_HOME"
WORK=${ARK_CARGO_WORK:-$ARK_ROOT/cargo-work}; MODE=${1:-all}
cargo_ok() { v=$("${1:-cargo}" --version 2>/dev/null | awk '{split($2,a,"."); print a[1]*1000+a[2]}'); [ "${v:-0}" -ge 1085 ]; }
CARGO=cargo
if ! cargo_ok cargo; then
  T=$ARK_ROOT/.tools/rust; tb=$(ls "$ARK_SOFTWARE"/binaries/rust-*-x86_64-unknown-linux-gnu.tar.* 2>/dev/null | sort -V | tail -1)
  if [ ! -x "$T/bin/cargo" ] && [ -n "$tb" ]; then x=$(mktemp -d); tar -xf "$tb" -C "$x" && "$x"/rust-*/install.sh --prefix="$T" --without=rust-docs >/dev/null && rm -rf "$x"; fi
  [ -x "$T/bin/cargo" ] && cargo_ok "$T/bin/cargo" && { CARGO=$T/bin/cargo; export PATH=$T/bin:$PATH; } || { echo "need cargo >= 1.85 (host or $ARK_SOFTWARE/binaries/rust-*.tar.*)"; exit 1; }
fi
export RUSTUP_TOOLCHAIN=${RUSTUP_TOOLCHAIN:-stable}   # rust-toolchain.toml pins must not trigger downloads; the lockfile decides versions
fetch_dir() { local d=$1 label=$2
  if (cd "$d" && "$CARGO" fetch --locked >/dev/null 2>"$WORK/.last.err"); then echo "OK     $label"
  elif (cd "$d" && "$CARGO" fetch >/dev/null 2>>"$WORK/.last.err"); then echo "OK-UNLOCKED $label (stale Cargo.lock; fetched what it resolves to today)"
  else echo "FAIL   $label: $(grep -m1 -E '^error|failed' "$WORK/.last.err" | cut -c1-160)"; fi; }
mkdir -p "$WORK"
if [ "$MODE" != own ]; then
  find "$ARK_SOFTWARE/src" -maxdepth 3 -name Cargo.lock 2>/dev/null | while read -r l; do fetch_dir "$(dirname "$l")" "src/${l#$ARK_SOFTWARE/src/}"; done
fi
if [ "$MODE" != src ]; then
  rows=$( { tail -n +2 manifest/cargo-repos.tsv; [ -f manifest-private/cargo-repos.tsv ] && tail -n +2 manifest-private/cargo-repos.tsv; } | grep -v '^#' | awk -F'\t' 'NF>=2 && $1!=""')
  # clone/refresh every row first, so all siblings exist before any fetch
  echo "$rows" | tr -d '\r' | tr '\t' '\037' | while IFS=$'\037' read -r name url note; do [ -z "$name" ] && continue
    r=${url%%#*}; b=; [ "$r" != "$url" ] && b=${url#*#}; d=$WORK/$name
    if [ -d "$d/.git" ]; then (cd "$d" && git fetch -q --depth 1 origin ${b:+"$b"} 2>/dev/null && git reset -q --hard FETCH_HEAD) || echo "UPDATE-FAIL $name"
    else git clone -q --depth 1 ${b:+-b "$b"} "$r" "$d" 2>/dev/null || echo "CLONE-FAIL $name ($url)"; fi
  done
  echo "$rows" | tr -d '\r' | tr '\t' '\037' | while IFS=$'\037' read -r name url note; do [ -f "$WORK/$name/Cargo.toml" ] && fetch_dir "$WORK/$name" "own/$name"; done
fi
echo "cargo-home: $(ls "$CARGO_HOME"/registry/cache/*/ 2>/dev/null | wc -l) crates, $(du -sh "$CARGO_HOME" 2>/dev/null | cut -f1)"
