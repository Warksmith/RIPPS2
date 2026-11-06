"""Exercise the renderer's actual vsync synchronization with a scripted EE kernel."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))
source = (ROOT / 'src/renderman.c').read_text()
start = source.index('static int rmOnVSync(')
end = source.index('\nvoid rmEndFrame(', start)
helpers = source[start:end]

# Ensure the exercised helpers are used by rendering and by both shutdown/mode-switch paths.
frame = source[end:source.index('// RIPPS2 build 120:', end)]
assert 'rmWaitVSync();' in frame and 'SleepThread();' not in frame
assert 'iWakeupThread(' not in source and 'static u8 guiWakeupCount' not in source
mode = source[source.index('int rmSetMode('):source.index('void rmGetScreenExtentsNative(')]
assert 'rmVSyncInit();' in mode and 'rmEnd();' in mode
shutdown = source[source.index('void rmEnd(void)'):source.index('#define X_SCALE')]
assert shutdown.index('rmVSyncEnd();') < shutdown.index('gsKit_deinit_global(')
assert 'gsKit_hires_sync(gsGlobal);' in frame and 'gsKit_hires_deinit_global(gsGlobal);' in shutdown

code = r'''
#include <assert.h>
#include <stdio.h>

typedef struct { int count, max_count, init_count, wait_threads, attr, option; } ee_sema_t;
static int vsyncSema = -1, vsync_id = -1;
static int alive, count, handler, next_id = 1, fail_create, fail_handler, drop_signal;
static int created, deleted, attached, detached, interrupts, blocked, fallback;
static int unrelated_wakeups;
static int (*callback)(int);

static int CreateSema(ee_sema_t *s) {
    assert(!alive && !handler);
    assert(s->init_count == 0 && s->max_count == 1 && s->attr == 0 && s->option == 0);
    if (fail_create) return -1;
    alive = next_id++; count = s->init_count; created++;
    return alive;
}
static int DeleteSema(int id) {
    assert(id == alive && !handler); /* ISR detached before semaphore destruction. */
    alive = 0; count = 0; deleted++;
    return 0;
}
static int gsKit_add_vsync_handler(int (*cb)(int)) {
    assert(alive && !handler);
    if (fail_handler) return -1;
    callback = cb; handler = next_id++; attached++;
    return handler;
}
static void gsKit_remove_vsync_handler(int id) {
    assert(handler == id && alive);
    handler = 0; callback = 0; detached++;
}
static int iPollSema(int id) {
    assert(alive == id);
    if (!count) return -1;
    return --count;
}
static int iSignalSema(int id) {
    assert(alive == id);
    if (drop_signal) { drop_signal = 0; return -1; }
    /* Deliberately ignore max_count: the ISR must coalesce its own pending ticks. */
    count++;
    return 0;
}
static void ExitHandler(void) { interrupts++; }
static int WaitSema(int id) {
    assert(id == alive && handler);
    if (!count) {
        blocked++;
        assert(callback);
        callback(0); /* Vblank arrives while the renderer is waiting. */
    }
    assert(count == 1); /* Neither a lost signal nor a backlog of old frames. */
    count--;
    return id;
}
static void gsKit_vsync_wait(void) { fallback++; }
'''
code += helpers
code += r'''
int main(void) {
    rmVSyncInit();
    assert(vsyncSema >= 0 && vsync_id >= 0);
    rmOnVSync(0); /* Interrupt before the wait. */
    rmWaitVSync();
    assert(!blocked && count == 0);
    rmWaitVSync(); /* Interrupt during the wait. */
    assert(blocked == 1 && count == 0);

    /* Time spent in MMCE/RPC/preflight must not accumulate fast-forward frames. */
    for (int i = 0; i < 600; i++) rmOnVSync(0);
    assert(count == 1);
    unrelated_wakeups = 7;
    unrelated_wakeups = 0; /* Another sleep consumes/cancels thread wakeups. */
    rmWaitVSync();
    assert(blocked == 1 && unrelated_wakeups == 0 && count == 0);
    rmWaitVSync();
    assert(blocked == 2);

    /* A failed notification must not latch out every subsequent vblank. */
    drop_signal = 1;
    rmOnVSync(0);
    assert(!count);
    rmWaitVSync();
    assert(blocked == 3 && count == 0);

    /* A video-mode switch discards old signals and creates a fresh wait object. */
    rmOnVSync(0);
    rmVSyncEnd();
    assert(vsyncSema == -1 && vsync_id == -1 && !alive && !handler);
    rmVSyncEnd(); /* Safe repeated teardown. */
    rmOnVSync(0); /* No signal through a stale id. */
    for (int i = 0; i < 20; i++) {
        rmVSyncInit();
        assert(!count);
        rmWaitVSync();
        rmVSyncEnd();
    }

    fail_create = 1;
    rmVSyncInit();
    assert(vsyncSema == -1 && vsync_id == -1);
    rmWaitVSync();
    rmVSyncEnd();
    fail_create = 0; fail_handler = 1;
    rmVSyncInit();
    assert(vsyncSema == -1 && vsync_id == -1 && !alive);
    rmWaitVSync();
    rmVSyncEnd();
    assert(fallback == 2 && created == deleted && attached == detached);
    puts("vsync: before/during wait, coalescing, unrelated wakes, lost notification, lifecycle and failures OK");
    return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    path = Path(td)
    (path / 'test.c').write_text(code)
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                    str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
