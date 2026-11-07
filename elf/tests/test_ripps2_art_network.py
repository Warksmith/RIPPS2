"""Cover download rejects resident UDP NIC drivers before touching the lists."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))
source = (ROOT / 'src/ripps2art.c').read_text(encoding='utf-8')
start = source.index('static const char *artNetworkConflict(void)')
helper = source[start:source.index('\n}', start) + 2]
run = source[source.index('void ripps2ArtDownload(void)'):]
assert run.index('artNetworkConflict()') < run.index('malloc(') < run.index('artCollect(')
assert run.index('return;') < run.index('malloc(')
assert run.count('artNetworkConflict()') == 2  # recheck after a failed startup

harness = r'''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#define _t(s) (s)
static int udpfsResident, udpbdResident;
static int udpfsGetModulesLoaded(void) { return udpfsResident; }
static int bdmIsUDPBDLoaded(void) { return udpbdResident; }
@HELPER@
int main(void) {
    assert(artNetworkConflict() == NULL); /* local, SMB and HTTP remain allowed */
    for (int fs = 0; fs <= 1; fs++) {
        for (int bd = 0; bd <= 1; bd++) {
            udpfsResident = fs; udpbdResident = bd;
            const char *message = artNetworkConflict();
            assert((message != NULL) == (fs || bd));
            if (message) {
                assert(strstr(message, "restart"));
                assert(strstr(message, "ART"));
            }
        }
    }
    return 0;
}
'''.replace('@HELPER@', helper)
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'test.c'
    exe = Path(tmp) / 'test'
    c.write_text(harness, encoding='utf-8')
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('PASS: artwork NIC conflict guard and early return')
