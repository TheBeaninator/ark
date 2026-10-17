#!/bin/bash
# fetch/reference.sh — manifest/reference.tsv: zim (latest match of a pattern in a Kiwix directory), zim-set (brace list of tools), url (with {REL} = latest Ensembl release), iso (latest match of a pattern in a releases directory, verified against its SHA256SUMS, into $ARK_SOFTWARE/binaries/iso),
# binaries (exact URL into $ARK_SOFTWARE/binaries/<pattern_or_target>/, '.' = the binaries root: toolchain tarballs and build-time tool downloads that fetchers and builds look for there, e.g. cargo.sh's rust-*.tar.xz),
# findlinks (pattern = a pip requirement, source = a pip find-links page; latest wheel for $ARK_PY into $ARK_SOFTWARE/wheels), whence (source = an amd/xdna-driver tools/WHENCE; its sync_from_whence.py pulls the NPU firmware it lists into $ARK_SOFTWARE/binaries/<pattern>/amdnpu).
set -u; . "$(dirname "$0")/../ark.env"; cd "$(dirname "$0")/.."; A="aria2c -c -x8 -s8 --file-allocation=none --auto-file-renaming=false --console-log-level=warn --summary-interval=0 --max-tries=20 --retry-wait=30"
UA="-sL -A Mozilla/5.0"; Z="$ARK_DATA/reference/zim"; G="$ARK_DATA/reference/genome"; mkdir -p "$Z/devdocs" "$G"
REL=$(curl $UA https://ftp.ensembl.org/pub/ | grep -oE "release-[0-9]+" | sort -t- -k2 -n | tail -1 | tr -dc 0-9)
{ tail -n +2 manifest/reference.tsv; [ -f manifest-private/reference.tsv ] && tail -n +2 manifest-private/reference.tsv; } | tr -d '\r' | tr '\t' '\037' | while IFS=$'\037' read -r kind src pat note; do [ -n "${ARK_ONLY:-}" ] && ! grep -qxF "$src" "$ARK_ONLY" && continue; ark_skip "$src" && continue; case $kind in
  zim) f=$(curl $UA "$src" | grep -oE "${pat//\*/[0-9-]+}" | sort -u | tail -1); [ -n "$f" ] && { $A -d "$Z" "$src$f" >/dev/null 2>&1 && echo "OK $f" || echo "FAIL $f"; } || echo "NO-MATCH $pat";;
  zim-set) all=$(curl $UA "$src" | grep -oE "devdocs_en_[a-z0-9_.-]+\.zim" | sort -u); for k in $(echo "$pat" | grep -oE "\{[^}]+\}" | tr -d '{}' | tr ',' ' '); do f=$(echo "$all" | grep -E "^devdocs_en_${k}_[0-9-]+\.zim$" | sort | tail -1); [ -n "$f" ] && { $A -d "$Z/devdocs" "$src$f" >/dev/null 2>&1 && echo "OK $f" || echo "FAIL $f"; } || echo "NO-MATCH $k"; done;;
  url) u=${src//\{REL\}/$REL}; d="$ARK_DATA/reference/$pat"; mkdir -p "$d"; $A -d "$d" "$u" >/dev/null 2>&1 && echo "OK $(basename "$u")" || echo "FAIL $u"; [ "${u##*.}" = gz ] && { $A -d "$d" "$u.tbi" >/dev/null 2>&1 || true; };;
  binaries) d="$ARK_SOFTWARE/binaries/${pat#./}"; d=${d%/.}; mkdir -p "$d"; $A -d "$d" "$src" >/dev/null 2>&1 && echo "OK $(basename "$src")" || echo "FAIL $src";;
  iso) d="$ARK_SOFTWARE/binaries/iso"; mkdir -p "$d"; curl $UA -o "$d/SHA256SUMS" "${src}SHA256SUMS"; f=$(grep -oE "${pat//\*/[0-9.]+}" "$d/SHA256SUMS" | sort -V | tail -1); [ -n "$f" ] || { echo "NO-MATCH $pat"; continue; }; $A -d "$d" "$src$f" >/dev/null 2>&1 && (cd "$d" && grep " \*\?$f\$" SHA256SUMS | sed "s/\*//" | sha256sum -c --quiet -) && echo "OK $f" || echo "FAIL $f";;
  findlinks) d="$ARK_SOFTWARE/wheels"; mkdir -p "$d"; pl=(); for t in 2_35 2_28 2_27 2_17; do pl+=(--platform "manylinux_${t}_x86_64"); done
    $ARK_PIP download -q --no-deps --only-binary :all: --python-version "$ARK_PY" "${pl[@]}" --platform linux_x86_64 -f "$src" -d "$d" "$pat" >/dev/null 2>&1 && echo "OK $pat" || echo "FAIL $pat ($src)";;
  whence) d="$ARK_SOFTWARE/binaries/$pat"; t=$(mktemp -d); mkdir -p "$d"; curl $UA -o "$t/WHENCE" "$src" && curl $UA -o "$t/sync.py" "${src%/*}/sync_from_whence.py" \
    && python3 "$t/sync.py" firmware --whence "$t/WHENCE" --out "$d/amdnpu" --commit-file "$d/.whence_commit" >/dev/null 2>&1 && cp "$t/WHENCE" "$d/" && echo "OK $pat ($(tail -1 "$d/.whence_commit"))" || echo "FAIL $pat"; rm -rf "$t";;
  mpi) # MPI-IS login-gated download (smpl-x, amass, ...): session from tools/mpi-session-from-har.py in $ARK_MPI_AUTH/<domain>.{cookie,referer}
    dom=$(echo "$src" | grep -oE "domain=[a-z0-9_-]+" | cut -d= -f2); sf=$(echo "$src" | grep -oE "sfile=[^&]+" | cut -d= -f2-)
    au="${ARK_MPI_AUTH:-$HOME/.config/ark/mpi}"; d="$ARK_DATA/reference/$pat"; f="$d/${sf##*/}"; mkdir -p "$d"
    [ -s "$f" ] && ! file -b --mime-type "$f" | grep -q html && { echo "have ${sf##*/}"; continue; }
    [ -r "$au/$dom.cookie" ] || { echo "NOAUTH $dom ${sf##*/} (log in, save a HAR of download.php, run tools/mpi-session-from-har.py)"; continue; }
    curl -sfL -C - -A Mozilla/5.0 -H "Cookie: $(cat "$au/$dom.cookie")" -e "$(cat "$au/$dom.referer")" -o "$f" "$src" || true
    file -b --mime-type "$f" 2>/dev/null | grep -q html && { rm -f "$f"; echo "FAIL-AUTH $dom ${sf##*/} (session expired: re-export the HAR)"; } || { [ -s "$f" ] && echo "OK ${sf##*/}" || echo "FAIL ${sf##*/}"; };;
esac; done
