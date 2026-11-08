"""Build 155: BIBLE a060790 carried (signed by akilluminati47 on 11/07), the one-folder install on in every build, and f5705eb
(builds 143 to 154) known as an older BIBLE so Manage offers the update.

Static checks on the patched tree and on elf/bible."""
import hashlib
import os
import sys
from pathlib import Path

root = Path(os.environ.get('RIPTOPL_DIR', '.'))
here = Path(__file__).resolve().parents[1]
boot = (root / 'src/ripps2boot.c').read_text(encoding='utf-8').replace('\r\n', '\n')
mk = (root / 'Makefile').read_text(encoding='utf-8').replace('\r\n', '\n')
readme = (here / 'bible' / 'README.md').read_text(encoding='utf-8')
fail = []

# ---- the four signed files: a060790's plain ELF plus the 148-byte KELF wrapper
signed = {'SYSTEM.XLF': ('7e1c919e7dca2e8629d183959afbda90ee5161df149b339fe9b5793b11679f43', 116596),
          'MMCE/SYSTEM.XLF': ('f5fe7e982ed34631de21e94ed0b37d7b89a2aba3d3c1ab93541d19812aea5009', 169572),
          'MX4SIO/SYSTEM.XLF': ('245a63b9705f2fc95107820412ed2c35ec35e3a9d067c03097b55f16a6495831', 166804),
          'HSYSTEM.XLF': ('adfff5c3a96564afa64032c205cf39d039a910f0bd981630f3658ae6bb19a9de', 160180)}
for name, (want, plain) in signed.items():
    d = (here / 'bible' / name).read_bytes()
    if hashlib.sha256(d).hexdigest() != want:
        fail.append('elf/bible/%s is BIBLE a060790, signed 11/07' % name)
    if len(d) != plain + 148:
        fail.append('elf/bible/%s is its plain ELF (%d) plus 148 bytes' % (name, plain))
    if want not in readme:
        fail.append('elf/bible/README.md lists %s\'s SHA-256' % name)
if 'a060790' not in readme or 'B?EXEC-SYSTEM' not in readme:
    fail.append('elf/bible/README.md names the commit and the one folder')

# ---- the one-folder install, on unless the build turns it off
if 'ifneq ($(RIPPS2_BIBLE_ONE_FOLDER),0)\n  EE_CFLAGS += -DRIPPS2_BIBLE_ONE_FOLDER=1' not in mk:
    fail.append('Makefile: RIPPS2_BIBLE_ONE_FOLDER is on by default (=0 turns it off)')

# ---- f5705eb is an older build now, told by size and CRC; a060790's plain ELFs are known too
older = boot[boot.index('} blBibleOlder[] = {'):boot.index('};', boot.index('} blBibleOlder[] = {'))]
for want in ('{169576, 0xA690AAE8u, "MMCE"}', '{166840, 0x7CF44EA7u, "MX4SIO"}', '{116584, 0x5AAC1709u, "memory card"}'):
    if want not in older:
        fail.append('blBibleOlder has %s (f5705eb)' % want)
plain = boot[boot.index('} blBiblePlain[] = {'):boot.index('};', boot.index('} blBiblePlain[] = {'))]
for want in ('{169572, 0xFB4EA6A7u, "MMCE"}', '{166804, 0x0366135Fu, "MX4SIO"}', '{116596, 0x9A125C91u, "memory card"}',
             '{160180, 0xB0D7C11Au, "HDD"}'):
    if want not in plain:
        fail.append('blBiblePlain has %s (a060790)' % want)

print('\n'.join(fail) or 'build155: BIBLE a060790 carried, one folder on, f5705eb older OK')
sys.exit(1 if fail else 0)
