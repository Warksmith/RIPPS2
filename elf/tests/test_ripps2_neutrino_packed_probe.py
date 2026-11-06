"""Run the production Neutrino probe on packed ELF fixtures and optional real ELFs.

RIPTOPL_DIR=out/igr-src python3 elf/tests/test_ripps2_neutrino_packed_probe.py [ELF ...]
Requires a host compiler and liblzma headers/library.
"""
import lzma
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

root = Path(os.environ.get('RIPTOPL_DIR', '.')).resolve()
source = (root / 'src/system.c').read_text()
probe = source[source.index('#define NF_CFG'):source.index('static int sysNeutrinoHas(')]


def packed(parts, split=False, old_size=False):
    """ps2-packer's merged/separate PT_LOAD layouts, raw LZMA1 + properties."""
    phnum = 2 if split else 1
    start = 52 + 32 * phnum
    base, payload_base = 0x01D00000, 0x01C00000
    stub = bytearray(64)
    stub[:8] = b'LZMA' + struct.pack('<I', payload_base if split else base + len(stub))
    payload = bytearray(struct.pack('<II', 0x100000, len(parts)))
    for part in parts:
        stream = bytes([0x5D]) + struct.pack('<I', 196608) + lzma.compress(
            part, format=lzma.FORMAT_RAW,
            filters=[dict(id=lzma.FILTER_LZMA1, dict_size=196608, lc=3, lp=0, pb=2)])
        payload += struct.pack('<4I', len(part) + int(old_size), 4096, 0x100000, len(stream)) + stream
        payload += bytes(-len(payload) % 4)
    header = bytearray(52)
    header[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH', header, 16, 2, 8, 1, base + 28, 52, 0, 0, 52, 32, phnum, 0, 0, 0)
    segment = lambda offset, address, size: struct.pack('<8I', 1, offset, address, address, size, size + 4096, 7, 16)
    if split:
        header += segment(start, base, len(stub)) + segment(start + len(stub), payload_base, len(payload))
    else:
        header += segment(start, base, len(stub) + len(payload))
    return header + stub + payload


with tempfile.TemporaryDirectory() as directory:
    td = Path(directory)
    c = td / 'probe.c'
    exe = td / 'probe'
    c.write_text('''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "elfprobe.h"
''' + probe + '''
int main(int argc, char **argv) {
    unsigned int flags = 0;
    if (argc != 2) return 1;
    int found = sysNeutrinoProbeElf(argv[1], &flags);
    printf("%d %x\\n", found, flags);
    return 0;
}
''')
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                    '-Wno-unused-variable', '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-I', str(root / 'include'), str(c), str(root / 'src/elfprobe.c'), '-llzma', '-o', str(exe)], check=True)

    def check(data, expected, label):
        file = td / 'fixture.elf'
        file.write_bytes(data)
        result = subprocess.run([str(exe), str(file)], check=True, capture_output=True, text=True)
        found, flags = result.stdout.split()
        actual = (int(found), int(flags, 16))
        assert actual == expected, (label, actual, expected)

    luna = b'\0-dvd=\0-igr=\0-mmce_gameid=\0'
    for split in (False, True):
        for old_size in (False, True):
            check(packed([luna], split, old_size), (1, 0xC00), 'LUNA packed')
    check(packed([b'\0-dvd=\0-igr=\0']), (1, 0x400), 'older IGR-only LUNA')
    check(packed([b'-dvd=\0 usage -igr=<target> -mmce_gameid=<slot>']), (1, 0), 'stock usage')
    check(packed([b'\0-dvd=\0', b'\0-igr=\0-mmce_gameid=\0'], True), (1, 0xC00), 'multiple sections')
    check(packed([b'-dvd=\0-ig', b'r=\0']), (1, 0), 'section boundary cannot invent literals')
    check(packed([b'-dvd=\0-igr=']), (1, 0), 'unterminated text is not a parser literal')
    good = packed([luna])
    for cut in (0, 6, 51, 83, 148, len(good) - 6):
        check(good[:cut], (0, 0), 'truncation')
    for offset, value in ((24, 1), (28, 0xFFFFFFF0), (84 + 4, 0xDEADBEEF),
                          (148 + 4, 0xFFFFFFFF), (156, 0xFFFFFFFF),
                          (156 + 12, 0xFFFFFFFF), (172 + 1, 0xFFFFFFFF)):
        damaged = bytearray(good)
        struct.pack_into('<I', damaged, offset, value)
        check(damaged, (0, 0), 'invalid header/size/dictionary')
    damaged = bytearray(good)
    damaged[84:88] = b'LZ4\0'
    check(damaged, (0, 0), 'unsupported packer')
    damaged = bytearray(packed([luna, b'tail']))
    damaged[-8:] = b'\xff' * 8
    check(damaged, (0, 0), 'bad later section must discard earlier flags')
    print('PASS: packed Neutrino layouts, versions, boundaries and malformed inputs (ASan/UBSan)')
    for name in sys.argv[1:]:
        result = subprocess.run([str(exe), str(Path(name).resolve())], check=True, capture_output=True, text=True)
        print(f'{name}: readable / capability flags = {result.stdout.strip()}')
