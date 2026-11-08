# In-game return (IGR branch)

Hold **L1 + L2 + R1 + R2 + SELECT + START** to leave a PS2 game.
With **Neutrino LUNA**, the chord returns directly. With the **built-in OPL
core**, it opens the in-game menu: choose **Exit Game**, or disable
**Settings > Game Launching > In-Game Menu** for a direct exit.
Compatibility **Mode 6 (Disable IGR)** disables automatic IGR integration.

## Direct return to RIPPS2

1. Install a complete GameID-capable **Neutrino LUNA** runtime, keeping its
   loader, EE core, configuration and modules together.
   Warksmith's [igr-hardening branch](https://github.com/Warksmith/neutrino-luna/tree/igr-hardening)
   at `9798232` includes the tested restoration and runtime validation; this
   version requires `modules/mmceigr.irx`. Current
   [Neutrino LUNA](https://github.com/dnunezx/neutrino-luna/tree/669acaa3838770481e4f9b5a708c133c3a4e7278)
   uses a different GameID interface and embeds its restoration module in the
   EE core. Build 160 recognizes both interfaces.
   For that modern interface, use a runtime with the
   [resident-module discovery fix](https://github.com/Warksmith/neutrino-luna/commit/5313ff61143966b161752cfcc4ff3f240a04abc5).
   LUNA `669acaa` uses a module-search RPC unavailable in ROM LOADFILE and can
   silently skip GameID switching even when the flag is present. The focused
   `5313ff` test runtime fixes that check; console confirmation is still needed.
2. Select that runtime explicitly under **Game Launching > Neutrino**.
   Automatic discovery can select an older installation when several exist.
3. Put RIPPS2 on the restored boot memory card, for example at
   `mc0:/RIPPS2/RIPPS2.ELF`. RIPPS2 can still initially start from MMCE SD;
   the memory-card copy is the IGR destination.
4. Set **Settings > Game Launching > In-Game Menu > IGR Path** to that exact
   memory-card path, and enable MMCE **Send GameID on Launch**.
5. Check the preview for `-igr=mc0:/RIPPS2/RIPPS2.ELF` and the option matching
   your runtime: `-mmce_gameid=0:SLUS_201.52` for the older slot/ID interface
   (slot 1 / Ace Combat 4 example), or the standalone `-mmce-gameid` flag for
   current LUNA. RIPPS2 selects the interface automatically.
6. Launch and use the chord. Release it when reset begins. Neutrino restores
   the switched slots' boot cards before loading RIPPS2.

Use `mc1:` and slot `1` when appropriate. The ELF must exist on the card
that will be restored. Neutrino's resident return loader accepts memory-card
ELF paths, not direct MMCE SD, USB or network ELF paths.

The user confirmed this route with Ace Combat 4 over UDPFS using both
`af68bf4-IGR` and `af68bf4-IGR-h1`. The published `9798232-igr-hardening`
build contains the same hardened source; its 41 modules match the test kit.

## Destination selection

An explicit memory-card IGR Path takes precedence. When it is empty,
Neutrino uses RIPPS2's own launch path if it is on a memory card; otherwise
it uses the existing `hdd`/Browser fallback. Typing `Browser` explicitly
selects that fallback. `hdd` means the console's browser/HDD boot chain,
not a direct load of RIPPS2 from an HDD. This fallback stalled on the tested
BIBLE setup; use the explicit memory-card destination above for that setup.

The native OPL destination policy is unchanged: an empty path means Browser,
and existing reachability/stale-path checks still apply to explicit paths.
Its policy can reject a self-return path that Neutrino accepts.

Global/per-game `-igr=` and legacy `-mmce_gameid=` arguments retain their
last-value-wins behavior. An explicit supported `-mmce-gameid` flag also
suppresses automatic duplication. Explicit supported GameID arguments opt in
even when **Send GameID on Launch** is off. Use the syntax your runtime accepts;
RIPPS2 does not rewrite manually supplied options for a different runtime.
Disabled `$` arguments and options after `--b` do not override the automatic
handoff. The argument budget is checked before teardown or any GameID switch.
Build 151 does not discover or cache another
return executable when IGR Path is empty.

## MMCE restoration

| Engine | Card restored on IGR |
| --- | --- |
| Neutrino LUNA, `-mmce_gameid=slot:ID` | The selected slot's boot card, using the runtime's `mmceigr.irx` |
| Neutrino LUNA, `-mmce-gameid` | Boot cards for the slots the runtime records as successfully switched |
| Built-in OPL | The numbered card and channel captured before RIPPS2 sent GameID; boot fallback when that identity is unavailable or special |

For either recognized Neutrino interface, RIPPS2 leaves the GameID send to
the external runtime, which loads its files before switching and arms
restoration at the same time. RIPPS2 does not fall back to switching cards
itself when an automatic handoff is disabled or skipped.

The legacy interface excludes VMC-protected slots and follows the existing
preferred-slot/fallback order. The modern flag lets Neutrino derive the game
ID and probe eligible slots itself; it can switch both cards and has no slot
exclusion argument. RIPPS2 therefore skips automatic modern switching when
any VMC argument is active, logging the reason in `DIAG.TXT`. If a runtime
supports both interfaces, RIPPS2 prefers the modern flag without VMCs and the
legacy slot-specific form with VMCs. Explicit GameID arguments remain the
user's choice.

MMCE's current API does not reliably distinguish boot, named and GameID
cards on SD2PSX-family devices. Boot fallback follows LUNA's behavior. The
external Neutrino protocol does not restore arbitrary numbered/named cards.

Native restoration runs after shutdown and IOP reset, before MCMAN probes
the card. It uses Set Card/Set Channel with bounded SIO2 and card-ready
polling. A failed GameID send does not arm automatic restoration. Explicit
MMCE IGR slot settings request boot fallback where no previous selection
was captured. PS1/POPStarter and physical power cycles are outside this feature.

## Runtime compatibility and diagnostics

RIPPS2 detects LUNA options from executable parser strings, including
standard ps2-packer LZMA executables. Stock, unrecognized or malformed
executables do not automatically receive fork-only arguments.

The bare `-mmce-gameid` flag is complete: it takes no equals sign, slot or
GameID value. Seeing it in the preview confirms the selected interface, not
that Neutrino actually switched a card. In particular, the runtime's module
discovery can fail before any MMCE command; updating RIPPS2 alone cannot fix
that runtime check. Keep the matching loader and EE core together when testing
a corrected Neutrino installation.

The previously failing `F:/neutrino` was `02cbf4f`: it supported `-igr` but
lacked `-mmce_gameid` and the restore module. The working `nigr` was Warksmith
LUNA `af68bf4`, which includes MMCE restoration from `3a60180`. The older
runtime attempted to open the return ELF while the game card was selected.
Install the complete matching runtime rather than replacing only its loader.

Hardened LUNA checks the loader/core configuration signature and size,
validates return paths before switching, requires complete module reads,
and stops launch on missing restoration support, GameID errors or exhausted
status polling. After a timeout, restart before retrying because card
selection may be uncertain. Polling assumes individual driver calls return.

`DIAG.TXT` beside RIPPS2 records the actual backend, return target, supported
GameID interfaces, switching ownership and restore decision before teardown.
These records show what was armed; they do not
prove that hardware accepted the return command. UDPFS uses Neutrino even
when OPL is selected as a default. Build 151 retains these diagnostics.

## Validation and reproduction

`elf/build.sh` applies the committed patch series and derives the version
from the last patch: build 160 is `v1.6.0-beta`. The pinned target image and
host prerequisites are in `.github/workflows/build-elf.yml`.

`python3 elf/tests/run_host_tests.py <prepared-tree>` runs the host suite.
IGR harnesses execute argument selection, native restoration, pad-hook
recovery, shutdown deadlines and return-path selection with host mocks.
The packed capability probe runs with ASan/UBSan. These checks do not
establish physical SIO2 timing or every game's pad compatibility.

`elf/neutrino/build_igr_runtime.sh <new-work-dir> <new-out-dir> hardened`
reproduces `af68bf4-IGR-h1` using the pinned LUNA image documented in that
script. Its patch is also committed upstream as `9798232`; the external
runtime is not embedded in RIPPS2.

Native OPL still needs independent console testing on a supported backend
such as MMCE, USB or APA HDD. Test numbered-card/channel restoration and
boot fallback separately. Slot 2, VMC-protected slots, Mode 6 and other
games/backends also need broader hardware coverage.

## Reference and provenance

- [LUNA GameID integration](https://github.com/Warksmith/LUNA/commit/6796954f4c5ce5c40d4dd074cfff0bfa1ba56325).
- [Neutrino MMCE restoration](https://github.com/Warksmith/neutrino-luna/commit/3a601805da490fb276a6febe32bbd5cab954c684).
- [LUNA's OPL return hook](https://github.com/Warksmith/Open-PS2-Loader/commit/b881438a916ab1d2706134350dc850dc040d2604).
- [MMCE driver/protocol source](https://github.com/ps2-mmce/mmceman/tree/de28936fdf45fe445554cfa0b8f058b05fa8212f).
  The native restore module retains its MIT license and PS2SDK AFL-2.0 notice.
- [ps2-packer layout reference](https://github.com/ps2dev/ps2-packer/tree/d43ac514cd9bcce3e04f0ea54509d88d1f4b9719).
