"""Compile the real UDPFS GETSTAT path; cover servers with OPEN-only metadata."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))
source = (ROOT / 'modules/network/udpfs_shared/src/udpfs_core.c').read_text()
start = source.index('static int udpfs_stat_from_open(')
end = source.index('\n/*\n * Create directory', start)
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "udpfs_packet.h"
typedef struct {
    uint32_t mode, attr, size, hisize;
    uint8_t ctime[8], atime[8], mtime[8];
} iox_stat_t;
static uint8_t g_tx_buf[272], g_rx_buf[312];
static void *g_socket;
static int connected = 1, transport, serverError, openError, closeError;
static int opens, closes, lastDir, lastFlags;
static char requestPath[256];
#define M_DEBUG(...) ((void)0)
static uint32_t _padded_len(uint32_t n) { return (n+3)&~3; }
static int udprdma_is_connected(void *s) { (void)s; return connected; }
static int _request(void *req, uint32_t size, void *out, uint32_t cap) {
    udpfs_msg_getstat_reply_t *r = out;
    assert(size >= 8 && cap == sizeof(*r));
    strcpy(requestPath, (char *)req + 4);
    if (transport) return transport;
    memset(r, 0, sizeof(*r));
    r->msg_type = UDPFS_MSG_GETSTAT_REPLY;
    r->result = serverError;
    r->mode = 0x2000; r->size = 123;
    return sizeof(*r);
}
static int udpfs_core_open(const char *path, int flags, int mode, int isDir, int32_t *handle) {
    udpfs_msg_open_reply_t *r = (void *)g_rx_buf;
    assert(!strcmp(path, requestPath) && mode == 0);
    opens++; lastDir = isDir; lastFlags = flags;
    if (openError && !(openError == -EISDIR && isDir)) return openError;
    memset(r, 0, sizeof(*r));
    r->mode = isDir ? 0x1000 : 0x2000;
    r->size = 0x90000000; r->hisize = 1;
    memset(r->ctime, 1, 8); memset(r->mtime, 2, 8);
    *handle = 7;
    return 0;
}
static int udpfs_core_close(int32_t handle) {
    assert(handle == 7); closes++;
    memset(g_rx_buf, 0, sizeof(g_rx_buf));
    return closeError;
}
@SOURCE@
int main(void) {
    iox_stat_t st;
    assert(udpfs_core_getstat("/DVD/Game.iso", &st) == 0 && st.size == 123 && !opens);
    serverError = -EIO;
    assert(udpfs_core_getstat("udpfs-test.cso.iso", &st) == 0);
    assert(opens == 1 && closes == 1 && lastFlags == 1 && !lastDir);
    assert(st.size == 0x90000000 && st.hisize == 1 && st.mode == 0x2000);
    assert(st.ctime[0] == 1 && st.mtime[0] == 2 && st.atime[0] == 2);
    assert(udpfs_core_getstat("/", &st) == 0 && lastDir && st.mode == 0x1000);
    serverError = -ENOSYS; openError = -EISDIR;
    assert(udpfs_core_getstat("DVD", &st) == 0 && lastDir);
    openError = -ENOENT;
    assert(udpfs_core_getstat("missing.iso", &st) == -ENOENT && closes == 3);
    openError = 0; closeError = -EIO;
    assert(udpfs_core_getstat("Game.iso", &st) == -EIO && closes == 4);
    opens = closes = 0; closeError = 0;
    serverError = -EACCES;
    assert(udpfs_core_getstat("denied", &st) == -EACCES && !opens);
    serverError = -ENOENT;
    assert(udpfs_core_getstat("missing", &st) == -ENOENT && !opens);
    serverError = -EIO; transport = -ETIMEDOUT;
    assert(udpfs_core_getstat("Game.iso", &st) == -ETIMEDOUT && !opens);
    connected = 0;
    assert(udpfs_core_getstat("/", &st) == -EIO && !opens);
    puts("PASS: UDPFS stat fallback, root, virtual ISO sizes, timestamps and error/handle discipline");
}
'''.replace('@SOURCE@', source[start:end])
with tempfile.TemporaryDirectory(prefix='ripps2-udpfs-stat-') as tmp:
    tmp = Path(tmp)
    c, exe = tmp / 'test.c', tmp / 'test'
    c.write_text(code)
    subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(ROOT / 'modules/network/udpfs_ioman/src'),
                    str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
