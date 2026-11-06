"""Exercise cached pre-GameID bridge discovery and explicit return precedence."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(os.environ.get('RIPTOPL_DIR', '.')).resolve()
source = (root / 'src/ripps2boot.c').read_text(encoding='utf-8')
start = source.index('static int exitStale = 0;')
end = source.index('// build 119: 1 when an IGR Path', start)
code = source[start:end]
cc = shutil.which('cc') or shutil.which('gcc')
assert cc, 'A C compiler is required'

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    test = path / 'bridge.c'
    test.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#define O_RDONLY 0
#define LOG(...) ((void)0)
#define ripps2Diag(...) ((void)0)
static char gExitPath[256], own[256] = "mmce0:/APPS/RIPPS2.ELF";
static unsigned char headers[2][52];
static int available[2], lengths[2], opens, reads, closes, explicitExists = 1;
static int mock_open(const char *p, int flags) {
    (void)flags; opens++;
    assert(!strcmp(p,"mc0:/RIPPS2/IGR.ELF") || !strcmp(p,"mc1:/RIPPS2/IGR.ELF"));
    int slot = p[2]-'0';
    return available[slot] ? slot+1 : -1;
}
static int mock_read(int fd, void *p, unsigned n) {
    assert(n==52); reads++; memcpy(p,headers[fd-1],52); return lengths[fd-1];
}
static void mock_close(int fd) { assert(fd==1 || fd==2); closes++; }
#define open mock_open
#define read mock_read
#define close mock_close
static int blFileExists(const char *p) { (void)p; return explicitExists; }
static int ripps2BootLockIgrPath(char *p, int n) {
    snprintf(p,n,"%s",own); return !strncmp(own,"mc",2);
}
''' + code + r'''
static void valid(int slot) {
    memset(headers[slot],0,52);
    memcpy(headers[slot],"\177ELF\1\1\1",7);
    headers[slot][16]=2; headers[slot][18]=8;
    lengths[slot]=52; available[slot]=1;
}
static const char *target(void) { char buf[256]; return ripps2ExitPath(buf,sizeof(buf)); }
int main(void) {
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser") && opens==2 && !closes);
    valid(1);
    ripps2ExitPathCheck(); assert(!strcmp(target(),"mc1:/RIPPS2/IGR.ELF"));
    assert(reads==closes);
    valid(0);
    ripps2ExitPathCheck(); assert(!strcmp(target(),"mc0:/RIPPS2/IGR.ELF"));
    int before=opens;
    available[0]=available[1]=0; // GameID has changed the card surface.
    assert(!strcmp(target(),"mc0:/RIPPS2/IGR.ELF") && opens==before);
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); lengths[0]=20;
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); headers[0][0]=0; // KELF/non-ELF
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); headers[0][5]=2; // wrong endianness
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); headers[0][18]=3; // wrong machine
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); headers[0][16]=1; // relocatable, not executable
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    valid(0); strcpy(gExitPath,"Browser"); before=opens;
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser") && opens==before);
    strcpy(gExitPath,"mc1:/BOOT/OTHER.ELF");
    ripps2ExitPathCheck(); assert(!strcmp(target(),gExitPath) && opens==before);
    explicitExists=0;
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    explicitExists=1; strcpy(gExitPath,"mmce0:/APPS/RIPPS2.ELF");
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    strcpy(own,"mc0:/RIPPS2/RIPPS2.ELF"); strcpy(gExitPath,own);
    ripps2ExitPathCheck(); assert(!strcmp(target(),"Browser"));
    gExitPath[0]=0;
    ripps2ExitPathCheck(); assert(!strcmp(target(),"mc0:/RIPPS2/IGR.ELF"));
    assert(reads==closes);
    puts("IGR bridge: both slots, header rejection, cached target, explicit overrides passed");
}
''', encoding='utf-8')
    exe = path / 'bridge'
    subprocess.run([cc, '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(test), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

# Both config-load paths must populate the cache before a launch switches cards.
opl = (root / 'src/opl.c').read_text(encoding='utf-8')
assert opl.count('ripps2ExitPathCheck();') >= 2
assert 'igrFindBootLoader();' not in (root / 'src/system.c').read_text(encoding='utf-8')
