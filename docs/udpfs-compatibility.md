# UDPFS libraries

Build 145 accepts OPL libraries and ordinary folders in the same UDPFS share.
Select **UDPFS**, **Files** in Network settings, start the source, and refresh
the list after changing files on the PC. Games still launch through your own
Neutrino installation.

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
Unchanged image IDs are reused from the current in-memory list; this does not
change the OPL cache format. A failed, cancelled or incomplete directory scan
keeps both the previous games and their paths. Automatic refresh checks the
directories visited by the last successful scan; SELECT explicitly rescans.

Paths must fit the loader's existing 256-byte path buffers, and display titles
must fit 160 bytes. Longer entries are skipped, never truncated into a different
file. Discovery uses 64-bit directory-entry sizes, including DVD9 images larger
than 4 GiB. `CD/` supplies the CD media hint; other locations use the DVD hint.

## Server interoperability

Some UDPFS servers can list and open files but return `EIO` or `ENOSYS` for
`GETSTAT`, including for virtual ISO names. For an explicit server error of
either kind, the filesystem driver obtains the same metadata from a temporary
read-only `OPEN` and closes it immediately. Transport timeouts, permission
failures and missing files remain errors. The block-device capacity query is
unchanged.

The server used for development was an already-running `udpfsd.exe -fsroot
GAMES -verbose` on Windows. A read-only protocol probe found 275 ISO names at
its root and 16 in `DVD/`, and read `SYSTEM.CNF` through compressed ISO aliases
in both locations. Its `GETSTAT` replies returned `EIO`, while `OPEN` supplied
directory metadata. Its compressed aliases returned zero sizes and placeholder
timestamps from `OPEN`, so the catalogue uses `DREAD` metadata directly. This
also avoids a separate metadata request for every discovered file.

## Building and checking

The change is `elf/patches/0145-ripps2-udpfs-layouts.patch`, applied after the
existing patch series. Use the pinned PS2DEV image from
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
