"""Exercise the actual maintenance-session lifecycle with hardware stubs."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))
source = (ROOT / 'src/opl.c').read_text()
start = source.index('static int artSessionActive;')
session = source[start:source.index('static int loadLwnbdSvr(', start)]
udpfs = (ROOT / 'src/udpfssupport.c').read_text()
start = udpfs.index('void udpfsIopWasReset(void)')
hook = udpfs[start:udpfs.index('\n}', start) + 2]
system = (ROOT / 'src/system.c').read_text()
start = system.index('void sysShutdownDev9ForReset(void)')
power = system[start:system.index('\n}', start) + 2]
HARNESS = r'''
#include <assert.h>
#define NO_EXCEPTION 0
#define IO_MODE_SELECTED_ALL 1
#define LOG_INIT() ((void)0)
static int blocked, pending, artReady = 1, writeReady = 1, cfOwned;
static int resets, cleanup, restored, audio, pads, mmce, net, poweredOff, dev9InitCount;
static int udpfsNicClaimed, udpfsIomanModLoaded, gEnableBGM;
static int sysIsPccfOwned(void) { return cfOwned; }
static void ioBlockOpsTimed(int on, int ticks) { assert(ticks == 20); blocked = on; }
static void ioBlockOps(int on) { blocked = on; }
static int ioHasPendingRequests(void) { return pending; }
static int cacheCancelPendingImageLoadsTimed(int ms) { assert(ms == 3000); return artReady; }
static int ioWriteBegin(void) { return writeReady; }
static void ioWriteEnd(void) {}
static void audioEnd(void) { audio = 0; }
static void audioInit(void) { audio = 1; }
static void guiExecDeferredOps(void) {}
static void deinitAllSupport(int e, int mode) { assert(blocked && !e && mode == 1); cleanup++; }
static void clearErrorMessage(void) {}
static void ethDeinitModules(void) { assert(blocked); net = 0; }
static int ethGetModulesLoaded(void) { return net; }
static void sysShutdownDev9(void) { assert(dev9InitCount > 0); if (!--dev9InitCount) poweredOff++; }
@POWER@
@HOOK@
static void reset(void) {
    assert(blocked && !net && !dev9InitCount); resets++;
    udpfsIopWasReset(); pads = mmce = 0;
}
static void unloadPads(void) { pads = 0; }
static void padInit(int n) { assert(!n); }
static int startPads(void) { pads = 1; return 1; }
static void delay(int n) { (void)n; }
static void mmceLoadModules(void) { assert(blocked); mmce = 1; }
static void initAllSupport(int force) { assert(!blocked && force); restored++; }
static void mixRequestUpdate(void) {}
static void cacheInvalidateFailMemo(void) {}
static void artIndexInvalidate(void) {}
static void sfxReload(int n) { assert(n == -1); }
static void bgmStart(void) {}
@SESSION@
int main(void) {
    pending = 1; assert(!ripps2ArtSessionBegin()); assert(!blocked && !cleanup && !resets);
    pending = 0; artReady = 0; assert(!ripps2ArtSessionBegin()); assert(!blocked && !resets);
    artReady = 1; writeReady = 0; assert(!ripps2ArtSessionBegin()); assert(!blocked && !resets);
    writeReady = 1; cfOwned = 1; assert(!ripps2ArtSessionBegin()); assert(!blocked && !resets);
    cfOwned = 0; udpfsNicClaimed = udpfsIomanModLoaded = 1; dev9InitCount = 3;
    assert(ripps2ArtSessionBegin());
    assert(blocked && pads && mmce && !udpfsNicClaimed && !udpfsIomanModLoaded && !restored);
    assert(resets == 1 && poweredOff == 1); /* releases ATA's references too */
    assert(!ripps2ArtSessionBegin());
    net = 1; dev9InitCount = 1; /* HTTPS phase */
    ripps2ArtSessionReset();
    assert(blocked && resets == 2 && poweredOff == 2 && !restored);
    udpfsNicClaimed = 1; dev9InitCount = 1; /* transfer phase */
    ripps2ArtSessionEnd();
    assert(!blocked && !artSessionActive && restored == 1 && audio && resets == 2);
    ripps2ArtSessionEnd(); assert(restored == 1); /* idempotent */
    assert(ripps2ArtSessionBegin());
    net = 1; dev9InitCount = 1; /* failure/cancel before transfer must reset back */
    ripps2ArtSessionEnd();
    assert(!blocked && restored == 2 && resets == 4 && poweredOff == 4);
}
'''.replace('@SESSION@', session).replace('@HOOK@', hook).replace('@POWER@', power)
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'test.c'
    exe = Path(tmp) / 'test'
    c.write_text(HARNESS)
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('PASS: busy refusal, NIC reset, DEV9 release, MMCE restoration and both return paths')
