"""Execute native pad patching and IOP-reset recovery with a replaced call site."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(os.environ.get('RIPTOPL_DIR', '.')).resolve()


def function(file, signature):
    text = (root / file).read_text()
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2]


scanner = function('ee_core/src/util.c', 'u32 *find_pattern_with_mask(')
patcher = function('ee_core/src/padhook.c', 'int Install_PadOpen_Hook(').replace(
    'int Install_PadOpen_Hook(', 'static int patchCalls(')
reset = function('ee_core/src/syshook.c', 'u32 New_SifSetDma(')
program = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <sys/mman.h>
typedef uint32_t u32;
typedef uint8_t u8;
typedef int32_t s32;
typedef struct { const u32 *pattern, *mask; int size, type, version; } pattern_t;
#include "ee_core/include/padpatterns.h"
#define NB_PADOPEN_PATTERN 7
#define IGR_LIBPAD 1
#define PADOPEN_HOOK 0
#define PADOPEN_CHECK 1
#define COMPAT_MODE_6 0x20
#define DPRINTF(...) ((void)0)
#define DBGCOL(...) ((void)0)
#define BGCOLND(...) ((void)0)
static int EnableDebug, flushes;
static struct { int libpad, libversion; void *pad_buf; } Pad_Data;
static void *scePadPortOpen, *scePad2CreateSocket;
static void Hook_scePadPortOpen(void) {}
static void Hook_scePad2CreateSocket(void) {}
static void _sw(u32 value, u32 at) { *(u32 *)(uintptr_t)at = value; }
static void iFlushCache(int kind) { (void)kind; flushes++; }
''' + scanner + '\n' + patcher + r'''
static int padOpen_hooked, disable_padOpen_hook, g_compat_mask;
static int scans, installs, resetResult = 1, invalidates;
static u32 *site;
static u32 original;
static unsigned int ra_snap_iop;
static int raInstalls;
static void Install_RA_Vblank(void) { raInstalls++; }
static int Install_PadOpen_Hook(u32 begin, u32 end, int mode) {
    assert(begin == 0x100000 && end == 0x1ff0000);
    scans++;
    return patchCalls(0x100000, 0x110000, mode);
}
static void Install_IGR(void) { installs++; }
static void Invalidate_PadBuffer(void) { invalidates++; Pad_Data.pad_buf = NULL; }
struct _iop_reset_pkt { int arglen; char arg[16]; };
typedef struct { void *src; } SifDmaTransfer_t;
static int New_Reset_Iop(const char *arg, int length) {
    (void)arg; (void)length;
    assert(disable_padOpen_hook && Pad_Data.pad_buf == NULL);
    *site = original; // simulate a game restoring/loading calls after the reset scan
    return resetResult;
}
''' + reset + r'''
int main(void) {
    void *memory = mmap((void *)0x100000, 0x10000, PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    assert(memory == (void *)0x100000);
    memcpy((void *)0x100100, padPortOpenpattern3, sizeof(padPortOpenpattern3));
    site = (u32 *)0x100300;
    original = 0x0c000000 | (0x100100 >> 2);
    *site = original;
    assert(patchCalls(0x100000, 0x110000, PADOPEN_HOOK) == 1);
    assert(*site != original && Pad_Data.libversion == 0x0150 && flushes == 2);
    assert(patchCalls(0x100000, 0x110000, PADOPEN_HOOK) == 0); // calls already patched
    struct _iop_reset_pkt packet = {0};
    SifDmaTransfer_t dma = {&packet};
    for (int failure = 0; failure < 2; failure++) {
        padOpen_hooked = 1; Pad_Data.pad_buf = memory; scans = 0;
        resetResult = !failure;
        assert(New_SifSetDma(&dma, 1) == (u32)resetResult);
        assert(scans == 1 && !padOpen_hooked && !disable_padOpen_hook);
        assert(Pad_Data.pad_buf == NULL && *site == original);
        // Hook_CreateThread may retry now: the previous ELF's flag must not block it.
        if (!disable_padOpen_hook && !padOpen_hooked)
            padOpen_hooked = Install_PadOpen_Hook(0x100000, 0x1ff0000, PADOPEN_HOOK);
        assert(padOpen_hooked && *site != original);
    }
    assert(installs == 2 && invalidates == 2);
    g_compat_mask = COMPAT_MODE_6; scans = installs = 0; ra_snap_iop = 1;
    resetResult = 1;
    assert(New_SifSetDma(&dma, 1) == 1);
    assert(!scans && !installs && !disable_padOpen_hook);
#ifdef RETROACHIEVEMENTS
    assert(raInstalls == 1);
#endif
    munmap(memory, 0x10000);
    puts("PASS: native IOP reset rearms pad-hook recovery; Mode 6 stays disabled");
}
'''
with tempfile.TemporaryDirectory() as directory:
    td = Path(directory)
    c, exe = td / 'rehook.c', td / 'rehook'
    c.write_text(program)
    (td / 'tamtypes.h').write_text('/* Types supplied by the harness. */\n')
    for defines in ([], ['-DRETROACHIEVEMENTS']):
        subprocess.run(['gcc', '-std=gnu99', '-Wall', '-Werror', '-Wno-unused-variable',
                        '-Wno-unused-function', '-Wno-pointer-to-int-cast', '-Wno-int-to-pointer-cast',
                        '-I', str(td), '-I', str(root), *defines, str(c), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)

asm = (root / 'ee_core/src/asm.S').read_text()
hook = asm[asm.index('Hook_CreateThread:'):asm.index('.end    Hook_CreateThread')]
assert 'la      $v1, padOpen_hooked' in hook and 'jal     Install_PadOpen_Hook' in hook
