# Network boot and node provisioning from the ark

What the ark holds so that a bare x86-64 node can be installed, or run diskless, with no network beyond the island's own switch.

## The three places it lives
| layer | where in the ark | fetched by |
|---|---|---|
| installer ISO | `$ARK_SOFTWARE/binaries/iso/ubuntu-24.04.<n>-live-server-amd64.iso` + `SHA256SUMS` | `fetch/reference.sh` (`reference.tsv` kind `iso`, latest point release, checksum-verified) |
| debs | the flat apt mirror (`fetch/apt-mirror.py`): shim/grub/iPXE/syslinux boot binaries, dnsmasq, tftpd, NFS/NBD/iSCSI, dracut, cloud-init, image builders | `verify/apt-netboot.txt` lists them; `verify/apt-coverage.sh` proves each deb is on disk |
| sources | `manifest/repos.tsv` category `netboot` | `fetch/repos.sh netboot` |

## What is deliberately covered
- **UEFI PXE chain**: `shimx64.efi.signed` (shim-signed) → `grubnetx64.efi.signed` (grub-efi-amd64-signed) → the ISO's casper `vmlinuz`/`initrd` over TFTP/HTTP, with `ip=dhcp url=http://<server>/ubuntu-24.04.<n>-live-server-amd64.iso autoinstall ds=nocloud-net;s=http://<server>/nocloud/`. No separate "netboot tarball" is needed for 24.04: the live-server ISO is the netboot image.
- **iPXE** (source + the `ipxe` deb): `snponly.efi` uses the firmware's own NIC driver, so it works on NICs iPXE has no native driver for; an embedded script can skip DHCP entirely and chain straight to an HTTP URL.
- **Segments without a DHCP server**: pixiecore (proxyDHCP+TFTP+HTTP in one Go binary) or `dnsmasq --dhcp-range=...,proxy`.
- **Diskless / stateless nodes**: Warewulf (overlay + container images), LTSP (squashfs over NFS/NBD), `dracut-network` (nfs/iscsi/nbd/livenet root), `overlayroot` for read-only roots with a tmpfs overlay.
- **Building images without a live ISO**: mkosi, ubuntu-image, live-build, mmdebstrap/debootstrap against the apt mirror.
- **Testing before hardware**: qemu + OVMF (also in the mirror) boot the same ISO or PXE server in a VM.
- **No-network fallback**: Ventoy on a USB stick with the ISO, or the ISO written raw.

## Notes from the reference fleet
- The subiquity autoinstall schema is **not** in apt (subiquity and curtin are snaps inside the ISO); their repos are mirrored so the schema and examples are readable offline.
- Keep the point release the node images were actually built from alongside the latest one; the ISO directory is latest-only by fetch but nothing deletes an older ISO.
- Signed boot binaries: extract from the debs (`dpkg-deb -x shim-signed_*.deb .` → `usr/lib/shim/shimx64.efi.signed`; `grub-efi-amd64-signed` → `usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed`) rather than relying on archive.ubuntu.com's `dists/.../uefi/` paths, which no longer serve them.
- Realtek RTL8125 (2.5GbE, common on mini-PCs): UEFI PXE and iPXE `snponly.efi` work through the firmware driver; iPXE's native `realtek` driver also covers it.
