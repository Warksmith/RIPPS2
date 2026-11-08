# BIBLE, as RIPPS2 installs it

From build 134 these files are **BIBLE**, akilluminati47's boot loader built on **PS2BBL (PlayStation 2 Basic
BootLoader) by El Isra (israpps)** and saildot4k's PS2BBL Extended: its splash, its keys pages and its HD modes, from
[github.com/akilluminati47/BIBLE](https://github.com/akilluminati47/BIBLE). Every build here was **signed by
akilluminati47**, with kelftool on their own PC (build 133 and earlier carried El Isra's own PS2BBL 1.2.0 builds,
unchanged). Build 155 carries BIBLE at commit `a060790`, signed 2026-11-07:

| File here | BIBLE build | SHA-256 |
|---|---|---|
| `SYSTEM.XLF` | `PS2` (memory card KELF) | `7e1c919e7dca2e8629d183959afbda90ee5161df149b339fe9b5793b11679f43` |
| `MX4SIO/SYSTEM.XLF` | `PS2_MX4SIO` (memory card KELF; also reads `mx4sio:/` in slot 2) | `245a63b9705f2fc95107820412ed2c35ec35e3a9d067c03097b55f16a6495831` |
| `MMCE/SYSTEM.XLF` | `PS2_MMCE` (memory card KELF; also reads `mmce0:/` and `mmce1:/`, an SD2PSX or MemCard PRO 2) | `f5fe7e982ed34631de21e94ed0b37d7b89a2aba3d3c1ab93541d19812aea5009` |
| `HSYSTEM.XLF` | `PS2_HDD` (for the HDD's boot area) | `adfff5c3a96564afa64032c205cf39d039a910f0bd981630f3658ae6bb19a9de` |
| `bible.icn`, `icon.sys` | BIBLE's card icon and the colours and light it was checked under, from BIBLE's `assets/icon` (commit `c1e950c`) | |
| `LICENSE.TXT` | GNU General Public License v3 | |

- **Build 155 (BIBLE `a060790`):** a card keeps one settings file, in BIBLE's own system folder. BIBLE reads it from this
  console's folder first, then the other regions' folders, then `mc?:/SYS-CONF` for a card set up before, so every region's copy
  of BIBLE on the card shares it. RIPPS2's install now writes BIBLE's settings, their backup and the boot sound in that one folder,
  and tidies away what an older install left in `SYS-CONF` and `PS2BBL`. Manage calls `f5705eb` older and offers the update.
- **Build 143 (BIBLE `f5705eb`):** a missing file on an AUTO path, on a drive BIBLE has to load a driver for, no longer stops
  the boot on the splash (`301de13`): BIBLE moves on to the next path. BIBLE no longer reads `boot.adp` into memory: it only
  tells RIPPS2 the folder, and RIPPS2 reads it (BIBLE's `docs/boot-sound-handoff.md` has the lab's numbers). The stage 2
  loader is out of the MMCE, MX4SIO and HDD builds, about 9.6 KB each. BIBLE's folders wear BIBLE's own icon.
- **Build 139 (BIBLE `3282396`):** `BIBLE_BACKGROUND` (AUTO: RIPPS2's sky when RIPPS2's settings are found, else black;
  SKY; BLANK), RIPPS2's settings also read from `mc?:/RIPPS2` when AUTO starts RIPPS2 from an SD2PSX, USB or the HDD,
  RIPPS2 first in AUTO, and the boot sound read during the splash and handed to RIPPS2 in RAM. RIPPS2's Manage opens a
  BIBLE menu that sets these keys. Manage now calls this build older and offers the update, and RIPPS2 still takes the RAM
  copy from a card bound with it.
- **Build 138 (BIBLE `a1ffb0b`):** the MMCE and MX4SIO builds that builds 134 to 137 carried (`f31c8d5`) stopped on a black
  screen at power on: their own memory card driver did not link on the console (an IOP link error). `a1ffb0b` loads
  RIPPS2's memory card and pad drivers instead; its MMCE build, bound to an SD2PSX BOOT card by KELFBinder and by RIPPS2
  1.3.8's Manage, started RIPPS2 on a real PS2 (SCPH-39001) at power on.
- Source: https://github.com/akilluminati47/BIBLE, built on https://github.com/israpps/PlayStation2-Basic-BootLoader (GPL-3)
- The signed files are also on BIBLE's releases page.
- A signature is proven only when a console binds the file. If a bind is refused, RIPPS2 puts the card back as it was.

RIPPS2 carries them as data, inside RIPPS2.elf, and writes them to a memory card, or `HSYSTEM.XLF` to the internal
HDD's boot area, when you choose **Settings > General > Boot Loader > Manage**. From build 155 the install writes BIBLE's
config as `PS2BBL.INI` in BIBLE's own system folder (`mc?:/B?EXEC-SYSTEM`), where `a060790` looks first; older builds wrote
`mc?:/SYS-CONF/PS2BBL.INI` (PS2BBL Extended's place; PS2BBL 1.2.0 read `PS2BBL/CONFIG.INI`). It waits 0 ms for a button
and starts RIPPS2 first, with BOOT LOCK on.
The HDD install follows the FHDB / OSDMenu MBR steps: the old boot program is read out and kept in
`hdd0:__sysconf/RIPPS2/MBR-BACKUP.KELF` (Manage > Restore puts it back), HSYSTEM.XLF goes at sector
0x2000 of `__mbr`, the `__mbr` header is pointed at it, and the console's HDD boot setting is turned on.
RIPPS2's APA driver allows only those writes: the partition table stays fenced. RIPPS2 does not run them and contains
none of their code. On the card, the console's MechaCon binds the file to that card (the standard way a system update
is installed); RIPPS2 boots KELFBinder's IOPRP image for that step (build 138, `elf/kelfbinder`) and holds no keys.

Many consoles from ROM 2.30 on no longer run system updates, so a bound BIBLE may not start there at power on: Manage says so
on those ROMs and still lets you try. BIBLE also comes as a plain, unsigned ELF on its releases page, for OpenTuna or FunTuna
to start from `mc?:/BOOT/BOOT.ELF`. RIPPS2 does not carry or install that one; Manage recognises it by its size and CRC-32,
so its settings rows work.

Everything PS2BBL does is El Isra's work, and PS2BBL Extended's is saildot4k's. Thank you.
