# UDPFS libraries

Build 145 accepts OPL libraries and ordinary folders in the same UDPFS share.
Select **UDPFS**, **Files** in Network settings, start the source, and refresh
the list after changing files on the PC. Games still launch through your own
Neutrino installation.

For release notes, the causes and fixes, and the validation record, see the
[branch release and PR writeup](udpfs-layout-compatibility-release-and-pr.md).

```text
shared-folder/
  Game.iso
  Another Game.cso        # a decompression server advertises Another Game.cso.iso
  RPG/
    Game.iso
  CD/
    SLUS_123.45.Classic.iso
  DVD/
    Game.iso
```

- Both `CD/` and `DVD/` are optional. Their spelling is preserved on
  case-sensitive servers, including lowercase `cd/` and `dvd/`.
- With folder browsing off, discovery walks ordinary subfolders, up to eight
  levels below the share root. With folder browsing on, the root still includes
  the contents of `CD/` and `DVD/`; other folders become navigation rows.
  Opening a folder combines that relative folder under the share root, `CD/`
  and `DVD/`, preserving the existing OPL browsing behavior.
- Plain ISO names and OPL's `SLUS_123.45.Title.iso` naming convention work
  together. Plain images obtain their disc ID from `SYSTEM.CNF`.
- The exact server path is retained for launching, size lookup and file
  operations. Equal titles or disc IDs at different paths remain separate
  entries. Per-game settings and artwork retain their existing disc-ID keys.
- Compressed games work when the server presents decompressed sectors through
  an `.iso` name, such as `Title.cso.iso`, `Title.zso.iso` or `Title.chd.iso`.
  RIPPS2 passes that advertised name unchanged to Neutrino. Raw `.cso`, `.zso`,
  `.chd` and USBExtreme split images are not added to this Neutrino-backed list.
  Which compressed formats are available depends on the server build.
- Metadata, artwork, saves and launcher directories are not searched for PS2
  images. In particular `ART`, `CFG`, `CHT`, `VMC`, `THM`, `LNG`, `APPS`, `POPS`,
  `EMBER`, `AUDIO`, `MEDIA`, `PADS`, `RIPPS2`, `neutrino`, `LUNA` and `nhddl`
  are excluded, along with hidden/system directories.

The scan does not create `CD/`, `DVD/` or `games.bin`. Existing optional asset
folder setup is retained. A read-only share can be listed without those folders.
Unchanged image IDs are reused from the current in-memory list and, from build
152, the optional `RIPPS2.UID` cache described below; this does not change the OPL
cache format. A failed, cancelled or incomplete directory scan
keeps both the previous games and their paths. Automatic refresh checks the
directories visited by the last successful scan; SELECT explicitly rescans.

Paths must fit the loader's existing 256-byte path buffers, and display titles
must fit 160 bytes. Longer entries are skipped, never truncated into a different
file. Discovery uses 64-bit directory-entry sizes, including DVD9 images larger
than 4 GiB. `CD/` supplies the CD media hint; other locations use the DVD hint.

## Faster repeat scans (build 152)

With **Fast Cache** and writes enabled, a successful scan with folder browsing
off saves verified disc IDs in `RIPPS2.UID` at the share root. The next start still
enumerates the live directories, but reuses an ID only when the exact advertised
path, 64-bit size and modification timestamp match. New, renamed or changed
images use the existing `SYSTEM.CNF` probe. Legacy OPL filenames already contain
their IDs and need no image probe.

This follows LUNA's persistent title-ID cache approach, reviewed at
[LUNA bbd2b70](https://github.com/Warksmith/LUNA/tree/bbd2b70d4f983528c1620481deb5686f8bb305e3)
and its pinned
[NHDDL scanner b2b11f4](https://github.com/Warksmith/nhddl-luna/blob/b2b11f45f843ba44cd46cae4c731c749f7945f7e/src/devices/iso.c).
RIPPS2 additionally validates size and timestamp instead of relying on path alone.
No LUNA cache file or game-ID parser is imported.

- The first scan of plain-named games still opens each image. A server's
  `decompressing` log line indicates that it opened a compressed-image reader;
  it does not by itself mean the entire image was decompressed.
- The cache contains IDs, not a saved game list, artwork or settings. Live
  discovery still supplies titles, paths, sizes, media hints and folder rows.
  Artwork, CFG/metadata, themes, languages and launch paths keep their existing
  discovery code and disc-ID keys.
- Folder browsing can read an existing cache. It does not replace it with a
  partial folder view; scan once with folder browsing off to populate it.
- Unknown sizes or timestamps cannot produce persistent cache hits. Invalid
  images are not cached as failures and are retried.
- Disabled writes and read-only shares still scan normally and can read an
  existing cache. **Fast Cache** off bypasses persistent ID reads and writes.
  Failed/cancelled directory scans never save IDs; unchanged caches are not
  rewritten. Writes use the existing launch-drain guard.
- The versioned cache is bounded to 4,096 catalogue rows and checked for exact
  length, checksum, terminated strings and duplicate paths. UDPFS has no rename
  operation, so an interrupted cache write is discarded on the next read and
  the images are probed again. Cache failures never gate listing or launching.
- As with any size/timestamp cache, replacing an image while preserving both
  values cannot be detected. Delete `RIPPS2.UID` and refresh to rebuild its IDs.
  SELECT otherwise enumerates the server and reuses matching IDs.

The host regression fixture with 291 valid games (one legacy filename) takes
290 image probes on its first scan and zero after a process restart. This is a
probe-count measurement, not console timing. The harness also checks changed
IDs, additions/removals/renames, corrupt caches, missing metadata, read-only and
failed writes, folder navigation, cancellation and existing catalogue behavior.

Validation: all 248 host checks completed with zero unexpected failures and the
existing expected-failure list unchanged. The RA-enabled build 152 compiled with
the workflow's pinned PS2DEV image; the changed scanner produced no warnings.
Console timing, artwork/metadata display and launch validation remain pending.

## Faster startup enumeration (build 153)

The ID cache removed repeat ISO probes, but asset discovery still listed the
entire share root separately for THM, LNG and ART before listing games. In a
291-game emulator run these three redundant passes cost about 14 seconds.

Build 153 collects the exact ART/THM/LNG directory spellings during the game
scan and hands them to asset discovery before publishing the menu. This reduces
the common PS2 startup from four root traversals to one. Only up to 24 short
folder names are shared in memory; the live game list is still enumerated.
PS1-only startup and subsequent asset retries use one shared root pass too.

All case variants, populated-ART preference, CFG/metadata keys and existing
theme/language registration callbacks are retained. Partial, failed or cancelled
listings never publish folder names. Names are consumed once so a failed asset
probe can discover newly added folders on its next retry. Optional folder
creation still happens after the existing ART spelling has been resolved.

In one paired RIPPCSX2 test with the same read-only configuration and live
291-game share, launch-to-menu time fell from **30.3 s to 15.9 s**. All 291 paths,
disc IDs and sizes matched the baseline. The follow-up reported 291 reused IDs,
zero ISO probes and completed ART/THM/LNG discovery. These are emulator wall-clock
measurements, not a console timing guarantee. The first uncached scan still
opens each plain-named image to identify it; the redundant root passes are
removed for both cold and cached scans.

**Status > Save Diagnostics** now records UDPFS module-load, catalogue and asset
discovery milestones, including reused-ID and ISO-probe counts, in `DIAG.TXT`.
This distinguishes remaining boot/network setup time from actual scanning.

Validation: 249 host checks completed with zero unexpected failures. The new
shared-discovery harness covers case collisions, late folders, failed opens,
partial reads, close failures, cancellation and unchanged per-image art paths.
The RA-enabled PS2 build passed with no warnings in the changed scanners.
Physical-console startup timing remains to be checked.

## Server interoperability

Some UDPFS servers can list and open files but return `EIO` or `ENOSYS` for
`GETSTAT`, including for virtual ISO names. For an explicit server error of
either kind, the filesystem driver obtains the metadata available from a
temporary read-only `OPEN` and closes it immediately. Transport timeouts,
permission failures and missing files remain errors. The block-device capacity
query is unchanged.

The server used for development was an already-running `udpfsd.exe -fsroot
GAMES -verbose` on Windows. A read-only protocol probe found 275 ISO names at
its root and 16 in `DVD/`, and read `SYSTEM.CNF` through compressed ISO aliases
in both locations. Its `GETSTAT` replies returned `EIO`, while `OPEN` supplied
directory metadata. Its compressed aliases returned zero sizes and placeholder
timestamps from `OPEN`, so the catalogue uses `DREAD` metadata directly. This
also avoids a separate metadata request for every discovered file.

## Building and checking

The change is `elf/patches/0145-ripps2-udpfs-layouts.patch`, applied after the
existing patch series. Build 146 adds
`elf/patches/0146-ripps2-vsync-handoff.patch` for the launch handoff described
below. Use the pinned PS2DEV image from
`.github/workflows/build-elf.yml` and the existing `elf/build.sh` workflow.
When staging files from a Windows checkout into a Linux container, preserve
LF line endings in the scripts and `elf/RIPTOPL_UPSTREAM`.

```sh
sh elf/build.sh --prepare-only
python3 elf/tests/run_host_tests.py riptopl
```

`test_ripps2_udpfs_layout.py` compiles the production scanner and shared path
composer with address/undefined-behavior sanitizers. It covers mixed, flat and
OPL trees, case, aliases, nested navigation, duplicate titles, exact paths,
cache reuse, sizes above 4 GiB, positive directory-close results, cancellation,
partial reads and allocation failures. The virtual-image fixture deliberately
returns incomplete `GETSTAT` metadata to ensure discovery uses `DREAD`.
`test_ripps2_udpfs_stat.py` exercises the production protocol fallback,
including 64-bit sizes, timestamps, closing handles and preserving errors.

Emulator testing uses RIPPCSX2 with isolated settings and no real memory cards.
Its Sockets adapter uses `192.0.2.100` for the emulated PS2 and `192.0.2.1` as
the gateway; use those addresses in the test ELF's network configuration.
These addresses are for that emulator test, not a console on your LAN.
The RA-enabled PS2DEV build listed all 291 games from the running server and
matched their exact paths and advertised sizes, including 70 images larger than
4 GiB, with a disc ID extracted for every image. A manual refresh retained all
291 entries. It launched both
`DVD/Ace Combat 4 - Shattered Skies (USA).cso.iso` and the root-level
`Asterix & Obelix - Kick Buttix.cso.iso` through the local Neutrino installation.
The full host suite ran 242 tests with zero unexpected failures; its existing
expected-failure list was unchanged. Emulator results do not replace a console
test of discovery, refresh and Neutrino launch on the intended hardware.

## Neutrino handoff with arguments hidden

Console testing with Neutrino on MMCE exposed an intermittent freeze at
"Please Wait" when `neutrino_show_args=0`. Stage markers narrowed it to the
renderer sleeping for vertical sync during the handoff fade, before pad
shutdown or loading Neutrino. Showing the arguments avoided the freeze in
initial console tests; display blanking alone did not resolve it.

Build 146 replaces the normal renderer's thread wakeup/latch pair with a
dedicated vertical-sync semaphore. Each interrupt signals the semaphore,
coalescing old ticks so time spent in device preflight cannot create a backlog
of frames. The interrupt is detached before its semaphore is deleted, including
when changing video modes. If creating the semaphore or installing the handler
fails, the renderer uses gsKit's polling wait. This applies to all video modes
using the normal renderer; gsKit's separate `hires` rendering path keeps its
existing synchronization.

The normal fade and optional argument preview remain available. The change
does not add a launch delay or change Neutrino arguments, MMCE settings or
device teardown order. `test_ripps2_vsync.py` compiles the actual synchronization
helpers and checks interrupts before/during a wait, notification loss, long
preflight gaps, unrelated thread wakeups, mode-change lifecycle and allocation
or handler failures.

The full host suite with this follow-up passes 243 tests with zero unexpected
failures. The RA-enabled build also launches through Neutrino in RIPPCSX2 with
arguments hidden (NTSC) and with the argument preview enabled (PAL). On the
affected physical PS2 with Neutrino on MMCE, build 146 passed three fresh
launches of the same UDPFS game with `neutrino_show_args=0`.
