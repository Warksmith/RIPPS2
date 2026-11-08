# In-game return (IGR branch)

Hold **L1 + L2 + R1 + R2 + SELECT + START** to leave a PS2 game.
With **Neutrino LUNA**, the chord returns directly. With the **built-in OPL
core**, it opens the in-game menu: choose **Exit Game**, or disable
**Settings > Game Launching > In-Game Menu** for a direct exit.
Compatibility **Mode 6 (Disable IGR)** disables automatic IGR integration.

## Direct return to RIPPS2

1. Install a complete GameID-capable **Neutrino LUNA** runtime, including its
   matching `neutrino.elf`, `modules/ee_core.elf` and `modules/mmceigr.irx`.
   Warksmith's [igr-hardening branch](https://github.com/Warksmith/neutrino-luna/tree/igr-hardening)
   at `9798232` includes the tested restoration and runtime validation.
2. Select that runtime explicitly under **Game Launching > Neutrino**.
   Automatic discovery can select an older installation when several exist.
3. Put RIPPS2 on the restored boot memory card, for example at
   `mc0:/RIPPS2/RIPPS2.ELF`. RIPPS2 can still initially start from MMCE SD;
   the memory-card copy is the IGR destination.
4. Set **Settings > Game Launching > In-Game Menu > IGR Path** to that exact
   memory-card path, and enable MMCE **Send GameID on Launch**.
5. Check the preview for both `-igr=mc0:/RIPPS2/RIPPS2.ELF` and
   `-mmce_gameid=0:SLUS_201.52` (slot 1 / Ace Combat 4 example).
6. Launch and use the chord. Release it when reset begins. The selected
   slot's boot card is restored before RIPPS2 is loaded from it.

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

Global/per-game `-igr=` and `-mmce_gameid=` arguments retain their
last-value-wins behavior. Disabled `$` arguments and options after `--b`
do not override the automatic handoff. The argument budget is checked before
teardown or any GameID switch. Build 151 does not discover or cache another
return executable when IGR Path is empty.

## MMCE restoration

| Engine | Card restored on IGR |
| --- | --- |
| Neutrino LUNA | The selected slot's boot card, using `mmceigr.irx` |
| Built-in OPL | The numbered card and channel captured before RIPPS2 sent GameID; boot fallback when that identity is unavailable or special |

For Neutrino, RIPPS2 leaves the GameID send to the external runtime, which
loads its files before switching and arms restoration at the same time.
VMC-protected slots are excluded. Slot selection follows the existing
preferred-slot/fallback order; it does not switch both cards.

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

`DIAG.TXT` beside RIPPS2 records the actual backend, return target and restore
decision before teardown. These records show what was armed; they do not
prove that hardware accepted the return command. UDPFS uses Neutrino even
when OPL is selected as a default. Build 151 retains these diagnostics.

## Validation and reproduction

`elf/build.sh` applies the committed patch series and derives the version
from the last patch: build 151 is `v1.5.1-beta`. The pinned target image and
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
