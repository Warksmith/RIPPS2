# v1.5.7 beta: builds 142 to 157 since 1.4.1. BIBLE a060790 rides inside, a ripped CD track plays from an SD2PSX, and Warksmith's and RiptOPL's fixes are in.

## BIBLE a060790 inside (155)
- **One settings file on a card**: BIBLE reads `PS2BBL.INI` from this console's region folder first, then the other regions', then `SYS-CONF`. Manage installs it that way and offers the update to a card with `3282396` or `f5705eb`.
- **The AUTO hang is fixed**: a missing file on an AUTO path no longer leaves BIBLE on its splash. BIBLE no longer reads the boot sound into memory: RIPPS2 reads it, for a faster start.
- ROM 2.30 and up: Manage warns a bound BIBLE may not start there. BIBLE's card icon is remade in Blender.

## Music from an MMCE card (156)
- **A ripped `.wav` plays from an SD2PSX**: the music is read in small pieces with a short gap after each on MMCE, as the covers are. Keep `.wav` for rips; for music kept on MMCE, `.ogg` 44.1 kHz stereo is the safe choice.
- DIAG.TXT now logs each track's read speed and every time the sound ran dry.

## From Warksmith (145 to 154)
- **UDPFS**: OPL and plain libraries on one share, disc IDs checked once and kept. **In-game return**: packed Neutrino detected, the pad hook recovers, MMCE put back on the way out.

## From RiptOPL (157)
- **MX4SIO saves no longer lose sectors** (the fixed driver from ps2sdk #936 is built in). Two IOP hangs in the CD stream emulation gone. .hack//Infection's IOP allocations fit. 8-bit art keeps its colours.

## Fixes and pages (142 to 156)
- Save Settings To stays where you chose and starts that drive. All Games keeps every drive. The internal HDD comes back after an IOP restart (no more 401 on exFAT). RIPSHOT on MMCE makes its roll. Back on a changed page asks first. A colour picker for every colour row. One Controller Settings page with a Button Map. Back from a rip's folder lands on Memory Files with the right bar.

## Test list
- **A ripped CD track (`.wav`) from your SD2PSX or MemCard PRO 2**: does it play through without skips? If not, play it, then STATUS > SAVE DIAGNOSTICS and send the `music read` lines.
- **BIBLE a060790**: Settings > General > Boot Loader > Manage on a card with an older BIBLE. Does the update bind, and does BIBLE start RIPPS2 at the next power on? Which console and ROM?
- **MX4SIO**: save in a game, then load it. Any lost or broken save?
- **UDPFS**: launch the same network game three times from fresh starts.
- **Internal HDD (exFAT)**: any "401: Hard drive not detected" after coming back from a launch?
- **RIPSHOT on MMCE**: does the roll fill, and does NO ROLL: SEE DIAG.TXT show when it cannot?

## Report
Post here with your **console model and ROM**, which drives you use (USB, HDD, MMCE, MX4SIO, network), and your `DIAG.TXT` (STATUS > SAVE DIAGNOSTICS) for anything odd.
