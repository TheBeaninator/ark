#!/usr/bin/env bash
# Write the pod-control installer to the 256 GB SD card (in bigboy USB reader; the M5 boots from its SD slot).
#   sudo bash ~/stick-control.sh
#
# Finds the stick by its PROPERTIES rather than a hardcoded /dev/sdX, because
# device letters move between plug-ins and dd to the wrong one is unrecoverable.
# Refuses to run unless exactly one device matches: removable, USB transport,
# ~250 GB, model "Storage Device" (the SD reader), not mounted as a system filesystem.
#
# Set SKIP_VERIFY=1 to skip the read-back check (saves ~3 min on USB 2.0).
set -uo pipefail

ISO=/home/dad/fleet-iso/node-autoinstall-control-20260928.iso   # CONTROL NODE image (pod-control); ~/stick.sh = worker image

die() { echo "ABORT: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run with sudo: sudo bash ~/stick-control.sh"
[ -f "$ISO" ] || die "image not found at $ISO"

echo "=== image"
printf '  %s\n  %.2f GB\n' "$ISO" "$(stat -c %s "$ISO" | awk '{print $1/1073741824}')"
ISO_SIZE=$(stat -c %s "$ISO")

# ── find the stick, by properties ────────────────────────────────────────────
echo "=== locating the stick"
CANDIDATES=()
for d in /sys/block/sd*; do
  name=$(basename "$d")
  [ -e "/sys/block/$name/removable" ] || continue
  [ "$(cat "/sys/block/$name/removable")" = "1" ] || continue
  tran=$(lsblk -dno TRAN "/dev/$name" 2>/dev/null | xargs)
  [ "$tran" = "usb" ] || continue
  model=$(lsblk -dno MODEL "/dev/$name" 2>/dev/null | xargs)
  case "$model" in *"Storage Device"*) ;; *) continue ;; esac
  bytes=$(lsblk -dnbo SIZE "/dev/$name" 2>/dev/null | xargs)
  # 240-280 GB window: the SD card reports 268.4e9 bytes (250 GiB) (the OCZ SATA disk is 223 GB and not removable anyway).
  [ "$bytes" -gt 240000000000 ] && [ "$bytes" -lt 280000000000 ] || continue
  CANDIDATES+=("/dev/$name")
  printf '  candidate %s  %s  model="%s"  removable=1 usb\n' \
         "/dev/$name" "$(lsblk -dno SIZE "/dev/$name" | xargs)" "$model"
done

[ "${#CANDIDATES[@]}" -eq 1 ] || die "expected exactly 1 matching SD card, found ${#CANDIDATES[@]} — plug in only the target stick"
DEV="${CANDIDATES[0]}"

# ── refuse if anything on it is a system mount ───────────────────────────────
while read -r part mnt; do
  case "$mnt" in
    ""|/media/*|/mnt/*) ;;
    *) die "$part is mounted at $mnt — that looks like a system disk, not the stick" ;;
  esac
done < <(lsblk -nro NAME,MOUNTPOINT "$DEV" | awk '{print "/dev/"$1, $2}')

[ "$ISO_SIZE" -lt "$(lsblk -dnbo SIZE "$DEV")" ] || die "image is larger than $DEV"

echo "=== target: $DEV  (everything on it will be destroyed)"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$DEV"

# ── what is on the stick RIGHT NOW? (before we destroy it) ──────────────────
# Settles "which image did I actually flash" forever. Stamped images carry
# /fleet-build-id; the two pre-stamp 2026-08-11 builds are told apart by a
# 1 MiB prefix hash (they diverge at byte 529).
echo "=== stick currently holds:"
MNT=$(mktemp -d)
if mount -o ro -t iso9660 "$DEV" "$MNT" 2>/dev/null || mount -o ro -t iso9660 "${DEV}1" "$MNT" 2>/dev/null; then
  if [ -f "$MNT/fleet-build-id" ]; then sed 's/^/  | /' "$MNT/fleet-build-id"
  else echo "  | an ISO with no build stamp (pre-2026-08-11c)"; fi
  umount "$MNT"
else
  echo "  | (not mountable as iso9660 — blank or non-ISO stick)"
fi
rmdir "$MNT" 2>/dev/null
case "$(head -c 1048576 "$DEV" | sha256sum | cut -d' ' -f1)" in
  88625fb006a98903c02f3911208a0d2ec8047a286b13f014fe081acaf5dfb7a4)
    echo "  | prefix-hash match: node-autoinstall-20260811.iso (fleet refresh, NO mac-naming)" ;;
  e9baa2975aef58a480c491627d7480655e048e7fc2abdece7fce83f81871d503)
    echo "  | prefix-hash match: node-autoinstall-20260811b.iso (mac-naming build)" ;;
  *) echo "  | prefix-hash: no match against known 2026-08-11 builds" ;;
esac

echo "=== about to write:"
MNT=$(mktemp -d)
STAMPED=0
if mount -o ro,loop -t iso9660 "$ISO" "$MNT" 2>/dev/null; then
  if [ -f "$MNT/fleet-build-id" ]; then sed 's/^/  | /' "$MNT/fleet-build-id"; STAMPED=1
  else echo "  | $ISO (unstamped image)"; fi
  umount "$MNT"
else
  echo "  | $ISO (could not inspect)"
fi
rmdir "$MNT" 2>/dev/null
# Refuse unstamped images. Three install cycles were lost on 2026-08-11 to a
# stale ISO= pointer silently flashing an old build (the pointer edit landed in
# a COPY of this script, not the one being run). Every current build is
# stamped; an unstamped image here means the pointer is stale again.
[ "$STAMPED" = 1 ] || [ "${FORCE:-0}" = 1 ] || \
  die "image has no /fleet-build-id stamp — stale ISO= pointer? (FORCE=1 to override)"

# ── unmount anything auto-mounted ────────────────────────────────────────────
for p in $(lsblk -nro NAME "$DEV" | tail -n +2); do
  mountpoint -q "/dev/$p" 2>/dev/null && umount "/dev/$p" 2>/dev/null
  grep -q "^/dev/$p " /proc/mounts && { umount "/dev/$p" && echo "  unmounted /dev/$p"; }
done

# ── write ────────────────────────────────────────────────────────────────────
echo "=== wiping old signatures (leaves no stale backup GPT behind)"
wipefs -a "$DEV" >/dev/null || die "wipefs failed"

echo "=== writing (USB 2.0: expect a few minutes)"
dd if="$ISO" of="$DEV" bs=4M oflag=direct conv=fsync status=progress || die "dd failed"
sync
echo "  written"

# ── verify by reading back, not by trusting dd ───────────────────────────────
if [ "${SKIP_VERIFY:-0}" = "1" ]; then
  echo "=== verify skipped (SKIP_VERIFY=1)"
else
  echo "=== verifying: reading the image back off the stick"
  A=$(sha256sum "$ISO" | cut -d' ' -f1)
  B=$(head -c "$ISO_SIZE" "$DEV" | sha256sum | cut -d' ' -f1)
  if [ "$A" = "$B" ]; then
    echo "  MATCH  $A"
  else
    echo "  image  $A"
    echo "  stick  $B"
    die "read-back MISMATCH — do not trust this stick"
  fi
fi

partprobe "$DEV" 2>/dev/null
echo
echo "=== done. $DEV now holds:"
lsblk -o NAME,SIZE,FSTYPE,LABEL "$DEV"
echo
echo "Put the card in the M5 SD slot, boot from it (F7/F11). Unattended, ~15 min, installs onto the internal Kingston."
echo "REMOVE THE CARD after the install reboots: left in, a firmware that prefers SD will reinstall (wipe) on every boot."
echo "Then: passwd; sudo fleet-provision -n; sudo fleet-provision; reboot; bash /opt/pod-payload/provision/pod-setup.sh"
