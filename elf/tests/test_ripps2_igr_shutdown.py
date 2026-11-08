"""Execute the IGR shutdown RPC with missing, stalled and responsive IOP mocks."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(os.environ.get('RIPTOPL_DIR', '.')).resolve()
source = (root / 'ee_core/src/cd_igr_rpc.c').read_text()
source = source[source.index('/* These must outlive'):]
start = source.index('static u32 igrTicks(void)')
end = source.index('\n}', start) + 2
source = source[:start] + 'static u32 igrTicks(void) { u32 old = ticks; ticks += 73728000u; return old; }' + source[end:]
program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
typedef uint32_t u32;
typedef int32_t s32;
typedef struct { void *server; char padding[56]; } SifRpcClientData_t;
#define SIF_RPC_M_NOWAIT 1
#define SIF_RPC_M_NOWBDC 2
#define E_SIF_RPC_BIND 10
#define E_SIF_RPC_CALL 11
#define UNCACHED_SEG(p) (p)
static u32 ticks;
static int failure, binds, calls, phase, checks, wanted;
static SifRpcClientData_t *pending;
static void *pendingArg;
static int SifBindRpc(SifRpcClientData_t *cd, unsigned int id, int mode) {
    assert(id == 0x80000598 && mode == SIF_RPC_M_NOWAIT);
    binds++; phase = 0; pending = cd;
    if (failure == 1) return -1;
    cd->server = failure == 2 ? NULL : (void *)1;
    return 0;
}
static int SifCheckStatRpc(SifRpcClientData_t *cd) {
    assert(cd == pending); checks++;
    return (failure == 3 && phase == 0) || (failure == 5 && phase == 1);
}
static int SifCallRpc(SifRpcClientData_t *cd, int fno, int mode, void *arg,
                     int size, void *recv, int recvsize, void *callback, void *context) {
    assert(cd == pending && fno == 1 && mode == (SIF_RPC_M_NOWAIT | SIF_RPC_M_NOWBDC));
    assert(size == sizeof(s32) && *(s32 *)arg == wanted);
    assert(!recv && !recvsize && !callback && !context);
    calls++; phase = 1; pendingArg = arg;
    return failure == 4 ? -1 : 0;
}
''' + source + r'''
int main(void) {
    for (int wrap = 0; wrap < 2; wrap++) {
        for (wanted = 0; wanted < 2; wanted++) {
            for (failure = 0; failure <= 5; failure++) {
                ticks = wrap ? 0xffffff00u : 0;
                binds = calls = phase = checks = 0; pendingArg = NULL;
                int result = oplIGRShutdown(wanted);
                assert(result == (failure == 0 ? 0 : failure <= 3 ? -E_SIF_RPC_BIND : -E_SIF_RPC_CALL));
                assert(binds > 0 && binds <= 8 && checks <= 8);
                assert(calls == (failure == 0 || failure >= 4));
                // A delayed completion can still access static storage after return.
                assert(pending == &igrClient);
                if (pendingArg) assert(pendingArg == &igrPoweroff && *(s32 *)pendingArg == wanted);
            }
        }
    }
    puts("PASS: bounded IGR bind/call, poweroff value, late completion storage and timer wrap");
}
'''
with tempfile.TemporaryDirectory() as directory:
    td = Path(directory)
    c, exe = td / 'shutdown.c', td / 'shutdown'
    c.write_text(program)
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
