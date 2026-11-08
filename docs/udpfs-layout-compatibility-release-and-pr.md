# UDPFS layout compatibility and launch handoff

Branch: `udpfs-layout-compatibility`. This writeup covers the library changes in
build 145 and the launch fix in build 146 (`v1.4.6-beta`). For setup and browsing
instructions, see [UDPFS compatibility](udpfs-compatibility.md).

## Release notes

RIPPS2 can now use a UDPFS share containing both OPL-style `CD/` and `DVD/`
folders and ISOs at the share root or in ordinary subfolders. Existing libraries
can stay in place, including libraries shared with tools such as LUNA and
Neutrino. Plain filenames and OPL disc-ID-prefixed filenames work together.

The scanner preserves each game's actual server path, handles images larger
than 4 GiB, and retains the previous list if a refresh fails or is cancelled.
Server-decompressed images work through the server's advertised `.iso` names;
available compressed formats depend on the UDPFS server.

Build 146 also fixes the renderer wait implicated in a launch freeze at
"Please Wait" with `neutrino_show_args=0`. The fix passed three fresh launches
on the affected physical PS2 with Neutrino on MMCE. The normal fade and optional
argument preview remain available. Games still use the user's Neutrino
installation.

## Suggested PR title and opening

**Support mixed UDPFS library layouts and fix the Neutrino handoff vsync wait**

UDPFS discovery and path construction previously depended on OPL directory
conventions. This prevented reliable use of shares that also held games at the
root or in ordinary folders. This branch adds discovery for those layouts and
retains the exact pathname returned by the server for subsequent operations.
For example, `Game.iso`, `RPG/Another Game.iso` and `DVD/Classic.cso.iso` can
coexist in one share without moving files or reconstructing their locations
under `CD/` or `DVD/`.

Testing also exposed two independent compatibility problems: a server that
could list and open files but rejected `GETSTAT`, and a console launch hang in
the renderer's vertical-sync wait before Neutrino loaded. The branch adds a
selective metadata fallback and replaces the renderer's wakeup latch with a
dedicated semaphore. Validation covers production-code host tests, the live
UDPFS library in RIPPCSX2, and repeated launches on the affected console.

## Causes and fixes

### Library layout and file identity

The existing shared list/path machinery assumed an OPL layout. A game name,
disc ID and media type are insufficient to recover an arbitrary server path:
the same title may exist at the root, in a subfolder, and under `DVD/`.

The new UDPFS scanner stores an exact path, 64-bit size and modification time
alongside each game. This separate in-memory record avoids changing
`base_game_info_t` or the on-disk OPL cache formats. Launching, size lookup and
file operations resolve through that path. Rename path construction retains
the original directory and any legacy disc-ID prefix. Only identical paths
are deduplicated; equal titles or disc IDs at different paths remain separate.
Artwork and per-game settings continue to use their existing disc-ID keys.

With folder browsing disabled, discovery walks ordinary subfolders up to
eight levels below the root. With browsing enabled, root `CD/` and `DVD/`
contents remain visible together, while ordinary directories become navigation
rows. Entering a folder combines that relative location under the share root,
`CD/` and `DVD/`, preserving OPL's browsing behavior. Case-insensitive matching
recognizes ISO extensions and the special folders while retaining the server's
actual spelling. Plain images obtain their disc ID from `SYSTEM.CNF`.

Server-decompressed files such as `Game.cso.iso` are already ISO sector streams
from the client's perspective. The scanner accepts the advertised `.iso` name
and passes it unchanged to Neutrino. No client-side compressed-image decoder
is added by this feature.

The new list, its paths and its visited-directory records are published
together only after a complete scan. Cancellation, partial reads and allocation
failure preserve the previous catalog. Unchanged path/size/time records allow
disc-ID reuse. Automatic refresh checks visited directories; SELECT forces a
rescan. Discovery does not create `CD/`, `DVD/`, `games.bin` or `ul.cfg`;
existing optional asset-folder setup remains available.

### Server metadata and large images

The development Windows `udpfsd.exe` server returned `EIO` for `GETSTAT`, even
though `OPEN` and `DREAD` worked. Treating that response as proof that the share
or directory was unusable blocked otherwise valid operations.

The filesystem driver now falls back to a temporary read-only `OPEN` only when
the server explicitly returns `EIO` or `ENOSYS` for `GETSTAT`. It handles
directory opens, copies the reply's mode, size and creation/modification times,
then closes the handle. Copying happens before `CLOSE`, which reuses the reply
buffer. Because `OPEN` has no access timestamp, the fallback uses its
modification time for that field. Transport failures, malformed replies,
permission errors and missing files remain errors; close failures are also
propagated. The block-device capacity query is unchanged.

That fallback alone was insufficient for the catalog: this server's virtual
compressed images returned zero sizes and placeholder timestamps from `OPEN`,
but useful metadata from `DREAD`. The scanner therefore retains each native
directory entry's metadata instead of issuing another stat request per file.
It combines `hisize` and `size` into a 64-bit value, avoiding the EE newlib
32-bit `off_t` conversion that could reject or misrepresent large images.
The new scanner also accepts any nonnegative directory-close result as success.

### Freeze during the launch fade

On the affected physical PS2 with Neutrino on MMCE, hiding the arguments could
freeze the normal ELF at "Please Wait". Showing the arguments worked, but
leaving the selected game idle for 10–15 seconds did not prevent the freeze.
Display blanking alone also failed. Diagnostic successes were intermittent,
so a single successful trace run was insufficient to establish a fix.

Stage markers narrowed the stall to `SleepThread()` in the normal renderer's
vertical-sync wait during `guiFadeOutForHandoff()`, before pad shutdown or
loading Neutrino. The old synchronization had two separately maintained states:

```text
Vsync interrupt: if latch is clear, set latch and wake GUI thread
Frame end:      sleep GUI thread, then clear latch after returning
```

If the latch remained set while no usable thread wakeup was pending, the
renderer could sleep indefinitely: later interrupts skipped the wakeup, and
the only latch reset was after the sleep returned. The diagnostic located the
blocked wait; it did not capture the exact interrupt/thread sequence that
lost or consumed the wakeup. The evidence does not establish a defect in
Neutrino or MMCE firmware.

Build 146 replaces that latch and generic thread wakeup with a dedicated
vertical-sync semaphore. Every vsync interrupt signals it, coalescing old
pending ticks so time spent in launch preflight cannot accumulate a backlog
of frames. The renderer waits on that same semaphore. A lost notification
cannot permanently suppress later notifications through a separate latch.

The semaphore is created before the interrupt handler is registered. Shutdown
and video-mode changes detach the handler before deleting the semaphore. If
creation or registration fails, the renderer uses gsKit's polling vsync wait.
Frame presentation and wait-time accounting remain intact.

This change applies to all video modes using the normal renderer, beyond
UDPFS launches. gsKit's separate `hires` rendering path retains its existing
synchronization. The fix preserves the handoff fade, argument setting, Neutrino
arguments, MMCE settings and device teardown order. The release ELF contains
no diagnostic colors or added launch delay.

## Validation

| Layer | Evidence and result |
| --- | --- |
| Build | RA-enabled release build completed with the repository's pinned PS2DEV toolchain. |
| Host suite | Final build 146 suite: **243 tests, zero unexpected failures**. The existing expected-failure list was unchanged. |
| Scanner tests | Production scanner and shared path composer compiled with address/undefined-behavior sanitizers. Coverage includes mixed layouts, navigation, case, aliases, duplicates, exact paths, cache reuse, sizes above 4 GiB, directory close results, cancellation, partial reads and allocation failure. |
| Protocol tests | Production `GETSTAT` fallback exercised for selective fallback, 64-bit metadata, timestamps, handle cleanup and error propagation. |
| Renderer tests | Production synchronization helpers exercised for interrupts before/during waits, coalescing 600 ticks, unrelated thread wakeups, a dropped notification, repeated teardown, 20 mode changes and resource failures. Call-site checks verify integration with frame waits and shutdown. |
| Live library, build 145 | Read-only checks against the running server found **291 images: 275 at the root and 16 in `DVD/`**, including **70 larger than 4 GiB**. RIPPCSX2's catalog matched every advertised path and size, had a disc ID for every image, and retained all 291 after manual refresh. |
| Mixed-layout launches, build 145 | RIPPCSX2 launched `DVD/Ace Combat 4 - Shattered Skies (USA).cso.iso` and root-level `Asterix & Obelix - Kick Buttix.cso.iso` through Neutrino. |
| Final emulator checks, build 146 | The 291-game catalog remained available. Neutrino launch reached game runtime with arguments hidden in NTSC and with argument preview enabled in PAL. Emulator settings were isolated and real memory cards were not attached. |
| Physical PS2, build 146 | The user confirmed **three successful launches from fresh starts** of the same UDPFS game with `neutrino_show_args=0`, on the previously affected MMCE setup. |

The hardware result validates the reported regression on that setup. It is
not a claim of testing every console, video mode, server or title. LUNA itself
was not launched during validation; compatibility here means sharing its
generic library layout. Live file deletion and rename were not exercised;
the host tests cover path construction for file operations.

## Compatibility boundaries

- Raw `.cso`, `.zso`, `.chd` and USBExtreme split images are not added to this
  Neutrino-backed list. Compressed-image support requires the server to expose
  a decompressed `.iso` stream.
- Paths must fit the existing 256-byte buffers, including the terminator;
  display titles must fit 160 bytes. Overlong entries are skipped rather than
  truncated into another filename. Metadata, launcher and hidden/system
  directories are excluded from scanning; the operating guide lists them.
- `CD/` supplies a CD media hint; other locations default to DVD. Equal disc
  IDs still share the existing artwork/configuration keys.
- Servers with unreliable directory modification times may require SELECT
  to discover changes. The metadata fallback cannot manufacture accurate
  values absent from the server's replies.

## Review map and build provenance

| Change | Tracked source and checks |
| --- | --- |
| Mixed layouts, exact paths and metadata fallback | [Patch 0145](../elf/patches/0145-ripps2-udpfs-layouts.patch), [scanner tests](../elf/tests/test_ripps2_udpfs_layout.py), [protocol tests](../elf/tests/test_ripps2_udpfs_stat.py) |
| Vsync handoff fix | [Patch 0146](../elf/patches/0146-ripps2-vsync-handoff.patch), [renderer tests](../elf/tests/test_ripps2_vsync.py) |
| Build and complete host suite | [Build script](../elf/build.sh), [host test runner](../elf/tests/run_host_tests.py), [CI workflow](../.github/workflows/build-elf.yml) |

Implementation commits are `bd90ad1` (layout/server support) and `f7ad22a`
(vsync fix); `74931da` records the successful console validation. Both patches
are part of the existing ordered patch series. The upstream source recorded
in [RIPTOPL_UPSTREAM](../elf/RIPTOPL_UPSTREAM) is
`57c45b4fcc922ba00fed949c634caea0a2900c63` (revision 4224).

Use the dependencies and pinned image in the CI workflow:

```text
ps2dev/ps2dev@sha256:c64ae69c9817865ed98ff054e4ae5360b9e280ed952c97946bca95d9d35be995
```

From the repository root in the appropriate Linux build environment:

```sh
sh elf/build.sh --prepare-only
python3 elf/tests/run_host_tests.py riptopl
sh elf/build.sh
```

The exact console-tested build 146 candidate was promoted to local
`out/RIPPS2.elf` without rebuilding. It is the RA-enabled `v1.4.6-beta` release
ELF, **2,825,476 bytes**, with SHA-256:

```text
9784481C7CAB8EF0987D5A0F0F7EDA903F02A3F8994617CF00D016EAC5A077A6
```

The card test used the identical file named `RIPPS2-UDPFS-FIX.elf`. The user's
default installed ELF was left in place. This checksum identifies the tested
artifact, not a promise that a future rebuild is byte-identical. Release
packaging should use the normal ELF, not the intermediate TRACE, BLANK,
DISPLAY or FADE diagnostics. Neutrino remains a separate user installation.
