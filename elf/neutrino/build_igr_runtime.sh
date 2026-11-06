#!/bin/sh
# Optional matching LUNA runtime for IGR testing. Run inside the pinned
# LUNA build container (ps2max/dev@sha256:e390699d46818e7c736f414ae5b1789d3ef7d3d914ce646a8a7bd027bd7e4521). Does not change the user's existing Neutrino installation.
set -eu
WORK="${1:?pass a new build directory}"
OUT="${2:?pass a new output directory}"
REF=af68bf4c285d6d9114a60675edff0cf7306a4f54
REPO="${NEUTRINO_REPO:-https://github.com/Warksmith/neutrino-luna.git}"
if [ -e "$WORK" ] || [ -e "$OUT" ]; then
    echo "Use new build and output directories; existing files are not replaced." >&2
    exit 1
fi
git init -q "$WORK"
git -C "$WORK" fetch -q --depth 1 "$REPO" "$REF"
git -C "$WORK" checkout -q FETCH_HEAD
make -C "$WORK" -j2 GIT_TAG=af68bf4-IGR all
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
printf 'Source: https://github.com/Warksmith/neutrino-luna\nCommit: %s\nNo source modifications. Build: make GIT_TAG=af68bf4-IGR all; make copy\nIOP dependency modules come from the pinned LUNA build SDK.\n' "$REF" > "$OUT/SOURCE.txt"
