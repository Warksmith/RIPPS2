"""Compile the actual SELECT handler: direct, saved-page and All Games routing."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))
source = (ROOT / 'src/opl.c').read_text()
start = source.index('static void itemExecRefresh(')
handler = source[start:source.index('\n}', start) + 2]
harness = r'''
#include <assert.h>
#include <stddef.h>
enum { BDM_MODE, BDM_MODE_LAST, HDD_MODE, ETH_MODE, UDPFS_MODE,
       APP_MODE, FAV_MODE, MIX_MODE, MODE_COUNT };
enum { NET_PROTO_SMB, NET_PROTO_UDPFS, LIB_VIEW_PS1, LIB_VIEW_MIXED,
       IO_MENU_UPDATE_DEFFERED, SFX_CONFIRM };
#define MODE_IS_MIX(mode) ((mode) == MIX_MODE)
typedef struct { int mode, enabled; } item_list_t;
struct menu_item { item_list_t *userdata; };
static struct { item_list_t *support; } list_support[MODE_COUNT];
static item_list_t sources[MODE_COUNT];
static int gNetworkProtocol, savedPage = -1, requests, dirty[MODE_COUNT], queued[MODE_COUNT];
static int mixPageMode(item_list_t *s) { (void)s; return savedPage; }
static void udpfsRequestRescan(void) { requests++; }
static void libViewMarkDirty(int mode) { dirty[mode]++; }
static void ioPutRequestUnlessWaiting(int op, int *mode) {
    assert(op == IO_MENU_UPDATE_DEFFERED); queued[*mode]++;
}
static void itemInitSupport(item_list_t *s) {
    if (!s->enabled) { s->enabled = 1; queued[s->mode]++; }
}
static void ripps2StartSourceMode(int mode) { itemInitSupport(&sources[mode]); }
static void ripps2StartSources(void) { ripps2StartSourceMode(UDPFS_MODE); }
static void sfxPlay(int sound) { (void)sound; }
static int bdmModeIsPCCF(int mode) { (void)mode; return 0; }
static void bdmRequestPccfProbe(void) {}
static void loadFavourites(void) {}
static void hddVcdInvalidateCache(void) {}
static void mixRequestUpdate(void) {}
static void ethRequestCheckedRefresh(void) {}
static int libListViewActive(item_list_t *s) { (void)s; return LIB_VIEW_MIXED; }
@HANDLER@
static void reset(void) {
    requests = 0; savedPage = -1; gNetworkProtocol = NET_PROTO_UDPFS;
    for (int i = 0; i < MODE_COUNT; i++) {
        sources[i] = (item_list_t){i, 1};
        list_support[i].support = &sources[i];
        dirty[i] = queued[i] = 0;
    }
}
static void refresh(int mode) {
    struct menu_item menu = {&sources[mode]}; itemExecRefresh(&menu);
}
static void check(void) {
    assert(requests == 1 && dirty[UDPFS_MODE] > 0 && queued[UDPFS_MODE] == 1);
}
int main(void) {
    reset(); refresh(UDPFS_MODE); check();
    reset(); sources[UDPFS_MODE].enabled = 0; refresh(UDPFS_MODE); check();
    reset(); refresh(MIX_MODE); check();
    reset(); sources[MIX_MODE].enabled = 0; sources[UDPFS_MODE].enabled = 0;
    refresh(MIX_MODE); check();
    reset(); savedPage = HDD_MODE; refresh(MIX_MODE);
    assert(!requests && !dirty[UDPFS_MODE] && queued[HDD_MODE] == 1);
    reset(); savedPage = UDPFS_MODE; refresh(MIX_MODE); check();
    reset(); savedPage = UDPFS_MODE; sources[UDPFS_MODE].enabled = 0;
    refresh(MIX_MODE); check();
    reset(); refresh(HDD_MODE); assert(!requests && !dirty[UDPFS_MODE]);
    reset(); refresh(FAV_MODE); assert(!requests && !dirty[UDPFS_MODE]);
    reset(); gNetworkProtocol = NET_PROTO_SMB; refresh(MIX_MODE); assert(!requests);
    reset(); gNetworkProtocol = NET_PROTO_SMB; refresh(ETH_MODE); assert(!requests);
    struct menu_item empty = {NULL}; itemExecRefresh(&empty); assert(!requests);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'refresh.c'
    exe = Path(tmp) / 'refresh'
    c.write_text(harness.replace('@HANDLER@', handler))
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('PASS: SELECT forces UDPFS IDs from live, manual, saved and All Games pages only')
