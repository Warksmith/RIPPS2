#!/bin/sh
# Build the optional plain BIBLE/MMCE return ELF with BIBLE's pinned SDK:
# ps2dev/ps2dev@sha256:c64ae69c9817865ed98ff054e4ae5360b9e280ed952c97946bca95d9d35be995
set -eu
WORK="${1:?pass a new build directory}"
OUT="${2:?pass a new output directory}"
REF=f5705eb6ae422b95c08d4e5662f72b54e133e857
REPO="${BIBLE_REPO:-https://github.com/akilluminati47/BIBLE.git}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -e "$WORK" ] || [ -e "$OUT" ]; then
    echo "Use new build and output directories; existing files are not replaced." >&2
    exit 1
fi
git init -q "$WORK"
git -C "$WORK" fetch -q --depth 1 "$REPO" "$REF"
git -C "$WORK" checkout -q FETCH_HEAD
git -C "$WORK" apply "$SCRIPT_DIR/igr-bridge-auto-start.patch"
make -C "$WORK" release COMMIT_HASH=f5705eb BINDIR=igr/ PSX_ALL_DRIVERS_LAZY_LOADING=0 MMCE=1 EGSM_BUILD=0 DEBUG=0 PRINTF=NONE
mkdir -p "$OUT/RIPPS2"
cp "$WORK/igr/COMPRESSED_PS2BBL.ELF" "$OUT/RIPPS2/IGR.ELF"
cp "$WORK/LICENSE" "$OUT/BIBLE-LICENSE.txt"
if [ -f "$PS2SDK/LICENSE" ]; then cp "$PS2SDK/LICENSE" "$OUT/PS2SDK-LICENSE"; fi
cp "$SCRIPT_DIR/igr-bridge-auto-start.patch" "$SCRIPT_DIR/build_igr_bridge.sh" "$OUT/"
git -C "$WORK" archive --format=tar.gz --prefix=BIBLE/ HEAD > "$OUT/BIBLE-source.tar.gz"
printf 'BIBLE MMCE plain ELF with the included igr-bridge-auto-start.patch\nSource: https://github.com/akilluminati47/BIBLE\nBase commit: %s\nSource archive contains this base; apply the included patch to reproduce.\nThe dedicated bridge bypasses startup hotkeys and uses AUTO, so the IGR chord cannot select rescue or a launch key.\nInstall RIPPS2/IGR.ELF on the restored memory card (mc0: or mc1:), not MMCE SD.\nUses the existing SYS-CONF/PS2BBL.INI. No system update is installed or rebound.\n' "$REF" > "$OUT/SOURCE.txt"
