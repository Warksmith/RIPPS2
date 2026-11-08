"""Execute patched LUNA loader code with host file IO and MMCE mocks.

NEUTRINO_DIR must point at af68bf4 plus igr-runtime-hardening.patch.
"""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(os.environ['NEUTRINO_DIR']).resolve()
main = (root / 'ee/loader/src/main.c').read_text()
mods = (root / 'ee/loader/src/modlist.c').read_text()


def function(text, signature):
    start = text.index(signature)
    end = text.index('\n}', start) + 2
    return text[start:end]


preflight = main[main.index('    mod_ee_core.sFileName = sys.eecore_elf;'):
                 main.index('    /*\n     * **********************************************************************',
                            main.index('    mod_ee_core.sFileName = sys.eecore_elf;'))]
arm_start = main.index('    if (sys.sMMCEGameID != NULL) {',
                       main.index('// LUNA: QuickBoot keeps mmceman resident'))
arm = main[arm_start:main.index('\n    // Add simple checksum', arm_start)]

program = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include "modlist.h"
#define MAX_FILENAME 128
static const char *g_modules_prefix = "";
static int read_mode, read_count;
static ssize_t test_read(int fd, void *buf, size_t count) {
    read_count++;
    if (read_mode == 1 && read_count == 1) { errno = EINTR; return -1; }
    if (read_mode == 2 && read_count > 1) return 0;
    if (read_mode == 3) { errno = EIO; return -1; }
    return read(fd, buf, count > 7 ? 7 : count);
}
#define read test_read
''' + function(mods, 'int module_load(') + '\n#undef read\n' + function(
    mods, 'void *module_get_settings(') + '\n' + function(
    mods, 'struct ee_core_data *module_get_eecore_settings(') + r'''
static struct {
    char *sMMCEGameID, *sIGRPath, *eecore_elf;
    int bQuickBoot;
    struct ee_core_data eecore;
} sys;
static struct SModule mod_ee_core, mod_mmceigr = {.sFileName = "mmceigr.irx"};
static struct SDriver drv;
static int init_fail, ping_fail, send_fail, status_fail, ready_after;
static int pings, sends, queries, installed;
static unsigned waited;
static int fileXioInit(void) { return init_fail ? -1 : 0; }
static void fileXioExit(void) {}
static void mmce_wait_ms(unsigned ms) { waited += ms; }
static int fileXioDevctl(const char *dev, int cmd, void *in, int len, void *out, int outlen) {
    assert(dev[4] == sys.sMMCEGameID[0]);
    assert(!out && !outlen);
    if (cmd == 1) { pings++; return ping_fail ? -1 : 0; }
    if (cmd == 8) {
        sends++;
        assert(!strcmp(in, sys.sMMCEGameID + 2));
        assert(len == (int)strlen(in) + 1);
        return send_fail ? -1 : 0;
    }
    assert(cmd == 2);
    queries++;
    return status_fail ? -1 : queries >= ready_after ? 0 : 1;
}
int modlist_load(struct SModList *ml, unsigned filter) {
    (void)ml; (void)filter; return 0;
}
static uint8_t *mmce_install_igr(uint8_t *end) { installed++; return end; }
''' + function(main, 'static int mmce_gameid_valid(') + '\n' + function(
    main, 'static int mmce_send_gameid(') + '\nstatic int preflight(void) {\n' + preflight + r'''
    return 0;
}
static int arm_restore(void) {
    uint8_t *irxptr_end = NULL;
''' + arm + r'''
    return 0;
}
static void reset(void) {
    free(mod_ee_core.pData); free(mod_mmceigr.pData);
    memset(&mod_ee_core, 0, sizeof(mod_ee_core));
    memset(&mod_mmceigr, 0, sizeof(mod_mmceigr));
    mod_mmceigr.sFileName = "mmceigr.irx";
    memset(&sys, 0, sizeof(sys));
    sys.sMMCEGameID = "0:SLUS_201.52";
    sys.sIGRPath = "mc0:/RIPPS2/RIPPS2.ELF";
    sys.eecore_elf = "ee_core.elf";
    sys.bQuickBoot = 1;
    read_mode = read_count = init_fail = ping_fail = send_fail = status_fail = 0;
    pings = sends = queries = installed = waited = 0;
    ready_after = 1;
}
static void write_file(const char *path, const void *data, size_t size) {
    FILE *f = fopen(path, "wb"); assert(f);
    assert(fwrite(data, 1, size, f) == size); assert(!fclose(f));
}
int main(void) {
    struct ee_core_data config = {.magic = EECORE_SETTINGS_MAGIC,
                                 .SettingsSize = sizeof(config)};
    unsigned char buffer[sizeof(config) + 8];
    memset(buffer, 0, sizeof(buffer));
    memcpy(buffer + 4, &config, sizeof(config));
    struct SModule m = {.pData = buffer, .iSize = sizeof(buffer)};
    assert(module_get_eecore_settings(&m) == (void *)(buffer + 4));
    for (size_t n = 0; n < sizeof(config) + 4; n++) {
        void *short_buf = malloc(n ? n : 1); assert(short_buf);
        memcpy(short_buf, buffer, n);
        m.pData = short_buf; m.iSize = n;
        assert(!module_get_eecore_settings(&m));
        module_get_settings(&m); // ASan checks short/non-aligned tails.
        free(short_buf);
    }
    m.pData = buffer; m.iSize = sizeof(buffer);
    ((struct ee_core_data *)(buffer + 4))->SettingsSize--;
    assert(!module_get_eecore_settings(&m));
    assert(!module_get_eecore_settings(NULL));
    m.pData = NULL; assert(!module_get_eecore_settings(&m));

    write_file("ee_core.elf", &config, sizeof(config));
    write_file("mmceigr.irx", buffer, sizeof(buffer));
    for (int mode = 0; mode < 4; mode++) {
        reset(); read_mode = mode;
        m = (struct SModule){.sFileName = "ee_core.elf"};
        assert(module_load(&m) == (mode < 2 ? 0 : -1));
        if (mode < 2) assert(!memcmp(m.pData, &config, sizeof(config)));
        else assert(!m.pData && !m.iSize);
        free(m.pData);
    }
    for (int quick = 0; quick < 2; quick++) {
        for (int slot = 0; slot < 2; slot++) {
            reset(); sys.bQuickBoot = quick;
            if (slot) sys.sMMCEGameID = "1:SLUS_201.52";
            assert(preflight() == 0);
            assert(sends == !quick && installed == 0);
            assert(sys.eecore.flags & EECORE_FLAG_IGR);
            assert(!strcmp(sys.eecore.ExitPath, sys.sIGRPath));
            assert(arm_restore() == 0 && sends == 1 && installed == 1);
        }
        for (int failure = 0; failure < 5; failure++) {
            reset(); sys.bQuickBoot = quick;
            init_fail = failure == 0; ping_fail = failure == 1;
            send_fail = failure == 2; status_fail = failure == 3;
            ready_after = failure == 4 ? 999 : 1;
            if (quick) { assert(preflight() == 0); assert(arm_restore() == -1); }
            else assert(preflight() == -1);
            assert(!installed);
            if (failure >= 3) assert(queries == 745 && waited == 15000);
        }
        reset(); sys.bQuickBoot = quick; ready_after = 745;
        assert(!preflight() && !arm_restore());
        assert(queries == 745 && installed == 1);
    }
    const char *invalid[] = {"2:GAME", "0:", "x", ""};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(*invalid); i++) {
        reset(); sys.sMMCEGameID = (char *)invalid[i];
        assert(preflight() == -1 && !sends);
    }
    reset(); sys.bQuickBoot = 0; sys.sIGRPath = "mass:/RIPPS2.ELF";
    assert(preflight() == -1 && !sends);
    char long_path[160]; memset(long_path, 'a', sizeof(long_path));
    memcpy(long_path, "mc0:/", 5); long_path[159] = 0;
    reset(); sys.bQuickBoot = 0; sys.sIGRPath = long_path;
    assert(preflight() == -1 && !sends);
    reset(); sys.sIGRPath = NULL;
    assert(preflight() == -1 && !sends);
    reset(); assert(!unlink("mmceigr.irx"));
    assert(preflight() == -1 && !sends);
    write_file("mmceigr.irx", buffer, 0);
    reset(); assert(preflight() == -1 && !sends);
    write_file("mmceigr.irx", buffer, sizeof(buffer));
    config.magic = MODULE_SETTINGS_MAGIC; // old LUNA core, no ABI contract
    write_file("ee_core.elf", &config, sizeof(config));
    reset(); assert(preflight() == -1 && !sends);
    config.magic = EECORE_SETTINGS_MAGIC;
    write_file("ee_core.elf", &config, sizeof(config) - 1);
    reset(); assert(preflight() == -1 && !sends);
    write_file("ee_core.elf", &config, sizeof(config));
    reset(); sys.sMMCEGameID = NULL; sys.sIGRPath = NULL;
    assert(!preflight() && !arm_restore() && !sends && !installed);
    reset(); sys.sMMCEGameID = NULL; sys.sIGRPath = "hdd";
    assert(!preflight() && !arm_restore() && !sends && !installed);
    reset();
    puts("PASS: ABI bounds/mismatch, partial/error reads, missing restore module, early path validation, both slots and launch modes, MMCE timeout/error, and ordinary launches");
}
'''

with tempfile.TemporaryDirectory() as directory:
    td = Path(directory)
    source, exe = td / 'runtime.c', td / 'runtime'
    source.write_text(program)
    subprocess.run(['gcc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    '-I', str(root / 'ee/loader/src'), str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], cwd=td, check=True, timeout=10)
