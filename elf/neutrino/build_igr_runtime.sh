#!/bin/sh
# Optional matching LUNA runtime for IGR testing. Run inside the pinned
# LUNA build container (ps2max/dev@sha256:e390699d46818e7c736f414ae5b1789d3ef7d3d914ce646a8a7bd027bd7e4521). Does not change the user's existing Neutrino installation.
set -eu
WORK="${1:?pass a new build directory}"
OUT="${2:?pass a new output directory}"
REF=af68bf4c285d6d9114a60675edff0cf7306a4f54
REPO="${NEUTRINO_REPO:-https://github.com/Warksmith/neutrino-luna.git}"
MODE="${3:-baseline}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$MODE" in
    baseline) TAG=af68bf4-IGR ;;
    hardened) TAG=af68bf4-IGR-h1 ;;
    *) echo "Mode must be baseline or hardened" >&2; exit 1 ;;
esac
if [ -e "$WORK" ] || [ -e "$OUT" ]; then
    echo "Use new build and output directories; existing files are not replaced." >&2
    exit 1
fi
git init -q "$WORK"
git -C "$WORK" fetch -q --depth 1 "$REPO" "$REF"
git -C "$WORK" checkout -q FETCH_HEAD
if [ "$MODE" = hardened ]; then
    git -C "$WORK" apply --check "$SCRIPT_DIR/igr-runtime-hardening.patch"
    git -C "$WORK" apply "$SCRIPT_DIR/igr-runtime-hardening.patch"
fi
make -C "$WORK" -j2 GIT_TAG="$TAG" all
make -C "$WORK" copy
mkdir -p "$OUT/config"
cp "$WORK/ee/loader/neutrino.elf" "$OUT/"
cp "$WORK/ee/loader/version.txt" "$OUT/"
cp -R "$WORK/ee/loader/modules" "$OUT/"
for file in "$WORK/ee/loader/config/"*; do
    case "$(basename "$file")" in pcsx2*) continue ;; esac
    cp -R "$file" "$OUT/config/"
done
cp "$WORK/LICENSE" "$WORK/README.md" "$OUT/"
if [ -f "$PS2SDK/LICENSE" ]; then cp "$PS2SDK/LICENSE" "$OUT/PS2SDK-LICENSE"; fi
printf 'Source: https://github.com/Warksmith/neutrino-luna\nCommit: %s\nMode: %s\nBuild: make GIT_TAG=%s all; make copy\nIOP dependency modules come from the pinned LUNA build SDK.\n' "$REF" "$MODE" "$TAG" > "$OUT/SOURCE.txt"
if [ "$MODE" = hardened ]; then
    cp "$SCRIPT_DIR/igr-runtime-hardening.patch" "$OUT/"
    printf 'Patch: igr-runtime-hardening.patch (included)\n' >> "$OUT/SOURCE.txt"
fi
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
