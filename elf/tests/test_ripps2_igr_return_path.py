"""Exercise the native explicit return path and Browser fallback with host mocks."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(os.environ['RIPTOPL_DIR']).resolve()
source = (root / 'src/ripps2boot.c').read_text()
code = source[source.index('static int exitStale = 0;'):
              source.index('// build 119: 1 when an IGR Path')]
program = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define LOG(...) ((void)0)
static char gExitPath[256], own[256] = "mmce0:/APPS/RIPPS2.ELF";
static int exists = 1, probes;
static int blFileExists(const char *path) {
    assert(!strcmp(path, gExitPath)); probes++; return exists;
}
static int ripps2BootLockIgrPath(char *path, int size) {
    snprintf(path, size, "%s", own); return !strncmp(own, "mc", 2);
}
''' + code + r'''
static const char *target(void) { char buf[256]; return ripps2ExitPath(buf, sizeof(buf)); }
int main(void) {
    ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser") && !probes);
    strcpy(gExitPath, "Browser");
    ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser") && !probes);
    for (int slot = 0; slot < 2; slot++) {
        snprintf(gExitPath, sizeof(gExitPath), "mc%d:/RIPPS2/RIPPS2.ELF", slot);
        exists = 1; int before = probes;
        ripps2ExitPathCheck(); assert(probes == before + 1);
        assert(!strcmp(target(), gExitPath));
        exists = 0; // A later GameID switch must not re-probe the game's card.
        assert(!strcmp(target(), gExitPath) && probes == before + 1);
        ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser"));
    }
    exists = 1; strcpy(gExitPath, "mass:/APPS/OTHER.ELF");
    ripps2ExitPathCheck(); assert(!strcmp(target(), gExitPath));
    strcpy(gExitPath, "mmce0:/APPS/RIPPS2.ELF");
    ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser"));
    strcpy(own, "mc0:/RIPPS2/RIPPS2.ELF"); strcpy(gExitPath, own);
    ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser"));
    gExitPath[0] = 0; int before = probes;
    ripps2ExitPathCheck(); assert(!strcmp(target(), "Browser") && probes == before);
    puts("PASS: explicit return paths, both slots, cached presence, native self-return policy and Browser fallback");
}
'''
with tempfile.TemporaryDirectory() as directory:
    td = Path(directory)
    c, exe = td / 'return_path.c', td / 'return_path'
    c.write_text(program)
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
