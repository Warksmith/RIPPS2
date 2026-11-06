# In-game return (IGR branch)

Hold **L1 + L2 + R1 + R2 + SELECT + START** to leave a PS2 game.

With **Neutrino LUNA**, the chord returns directly. With the **built-in OPL
core**, it opens RIPPS2's in-game menu: choose **Exit Game**, or turn off
**Settings > Game Launching > In-Game Menu** to make the chord exit directly.
Compatibility **Mode 6 (Disable IGR)** disables automatic IGR integration.

## RIPPS2 on MMCE SD

For an installation where the boot card starts RIPPS2 from the MMCE SD:

1. Keep the boot card configured to start RIPPS2 (BIBLE/Boot Lock or your
   existing boot-loader configuration).
2. Use the **GameID-capable Neutrino LUNA runtime**, including its matching
   `ee_core.elf` and `modules/mmceigr.irx`. The reference implementation is
   [neutrino-luna commit 3a60180](https://github.com/Warksmith/neutrino-luna/commit/3a601805da490fb276a6febe32bbd5cab954c684),
   also present in the fork's later `udpfs-speed` branch. Replacing only
   `neutrino.elf` is insufficient; install the complete matching runtime.
3. Enable **Send GameID on Launch** for MMCE. Leave **IGR Path** empty or
   `Browser` to use the boot-loader route.
4. Launch a PS2 game and use the chord. Neutrino switches the MMCE back to its
   boot card, then returns through OSDSYS. The boot loader starts RIPPS2 again.

RIPPS2 automatically supplies `-igr=hdd` and, for an eligible MMCE slot,
`-mmce_gameid=0:SLUS_203.12` (example). Despite the name, LUNA's `hdd` target
means **return through the console boot chain**; it does not require RIPPS2 or
the game to be on an HDD. Without an installed/configured boot loader it goes
to the PS2 browser.

RIPPS2 no longer sends the GameID itself for this handoff. Neutrino performs
the switch after loading its files and arms the matching IGR restoration.
Slots covered by virtual memory-card arguments are excluded. The selected
slot is the same preferred-slot/fallback order used by RIPPS2's existing
GameID support; this feature does not introduce switching of both cards.

## Return destinations and compatibility

For RIPPS2 launched from `mc0:/` or `mc1:/`, Neutrino's automatic destination
is that ELF. An explicit memory-card **IGR Path** takes precedence. Other
locations use the boot-loader route. Explicit global/per-game `-igr=` and
`-mmce_gameid=` arguments retain their existing last-value-wins behavior;
disabled `$` arguments and arguments after `--b` do not override the defaults.

RIPPS2 detects LUNA's options from the executable's parser strings, even when
`version.txt` only reports an upstream version such as `v1.8.0`. Build 148
also inspects the normal **ps2-packer LZMA** executable distributed by LUNA;
an unpacked executable is supported too. Build 147 missed packed executables
and therefore omitted automatic `-igr=` and `-mmce_gameid=` arguments.
Stock, unrecognized, corrupt or unsupported packed executables do **not**
automatically receive fork-only arguments. An older
LUNA build with only `-igr` can return, but does not provide the deferred
GameID/boot-card restore contract: use the complete GameID-capable runtime
for MMCE switching. The existing launch-argument budget is still enforced
before teardown and before any GameID switch.

| Engine | Card restored on IGR |
| --- | --- |
| Neutrino LUNA | The selected slot's boot card, using LUNA's bundled `mmceigr.irx` |
| Built-in OPL | The numbered card and channel captured immediately before RIPPS2 sent GameID; boot card if that identity is unavailable or special |

MMCE's current API does not distinguish boot, named and GameID cards reliably
on SD2PSX-family devices. The boot-card fallback follows LUNA's behavior. It
does not promise restoration of an arbitrary named card. Neutrino's current
external protocol supports boot-card restoration only, including when the
previous selection was numbered.

The native OPL restoration runs after shutdown and the IOP reset, before
MCMAN or the boot loader probes the card. It uses baseline Set Card and Set
Channel commands, waits between them, and bounds both the SIO2 transaction
and card-ready polling. A failed GameID send does not arm an automatic
restore. Explicit MMCE IGR slot settings still request boot-card restoration
for slots without a captured previous selection. The existing native IGR
destination policy remains in effect (boot-loader route by default).

PS1/POPStarter, physical reboot/power-cycle behavior, and arbitrary external
Neutrino runtimes are outside this change.

## Validation

The regression harness is `elf/tests/test_ripps2_igr.py`, run against the
prepared patch tree with `RIPTOPL_DIR=<tree>`. It executes the actual C
argument/capability and native restore code using host mocks. This checks
protocol ordering and failure handling; it cannot verify a console's SIO2
timing, boot exploit, or game-specific pad hook.

`elf/tests/test_ripps2_neutrino_packed_probe.py` exercises the actual decoder and
capability scanner with AddressSanitizer and UndefinedBehaviorSanitizer.
It covers merged/separate ELF segments, older packer sizes, multiple payload
sections, fork versus stock options, truncation and invalid size fields.
Host tests need a C compiler and `liblzma-dev`; the pinned PS2 toolchain
already supplies the target liblzma library. The decoder never executes the
payload or writes to addresses from the inspected ELF.

Build 148 fixes the confirmed Neutrino launch-argument omission and rearms
native OPL's pad-hook search at an IOP reset. Previously, a latched flag from
the old game code could suppress retries after the controller buffer was
invalidated. The new `test_ripps2_igr_rehook.py` executes the native scanner
and reset hook with a replaced call site, checking recovery in both standard
and RetroAchievements configurations. Temporary pauses in controller DMA
still do not trigger scans. Each actual IOP reset now incurs a pad scan.

The reported Ace Combat 4 failure still needs a console retest in each
engine. These tests establish the recovery behavior, not that this was the
cause of that game's native OPL failure on the console.

Console acceptance checks:

- Launch through Neutrino LUNA from MMCE SD, confirm the per-game card,
  hold the chord, confirm boot card restoration and RIPPS2 restart.
- Repeat with the card in slot 2, and with a VMC covering one physical slot.
- For the native core, start from a numbered card on a non-default channel;
  exit and confirm both are restored. Repeat from the boot card.
- Test a game with Mode 6 and a normal physical memory card; neither should
  gain an automatic MMCE switch/return behavior it does not support.

## Reference and provenance

- [LUNA GameID integration](https://github.com/Warksmith/LUNA/commit/6796954f4c5ce5c40d4dd074cfff0bfa1ba56325).
- [LUNA's OPL return hook](https://github.com/Warksmith/Open-PS2-Loader/commit/b881438a916ab1d2706134350dc850dc040d2604).
- [MMCE driver/protocol source](https://github.com/ps2-mmce/mmceman/tree/de28936fdf45fe445554cfa0b8f058b05fa8212f).
  The native restore module adapts its PIO transport, carries its MIT license,
  and retains the PS2SDK AFL-2.0 notice on the SIO2 register definitions.
- [ps2-packer layout reference](https://github.com/ps2dev/ps2-packer/tree/d43ac514cd9bcce3e04f0ea54509d88d1f4b9719).
  The probe reads its stub/header layout and decodes raw LZMA1 through liblzma.
