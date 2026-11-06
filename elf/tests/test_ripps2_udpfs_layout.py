"""Run the UDPFS catalogue/path code against a real host directory tree.

Includes partial I/O, cancellation and allocation failures: an incomplete scan
must never replace the last-good list or detach its exact server paths.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl'))


def without_includes(text):
    return re.sub(r'^#include .*\n', '', text, flags=re.M)


support = (ROOT / 'include/supportbase.h').read_text()
types = support[support.index('#define UL_GAME_NAME_MAX'):support.index('typedef struct', support.index('} base_game_info_t;'))]
source = (ROOT / 'src/udpfslist.c').read_text()
shared = (ROOT / 'src/supportbase.c').read_text()
frontend = (ROOT / 'src/udpfssupport.c').read_text()
def function(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2]
path_code = '\n'.join([function(shared, 'static void sbCreatePath_name('),
                       function(shared, 'void sbCreatePath('),
                       function(frontend, 'int udpfsGamePath(')])
harness = r'''
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <time.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define SCECdPS2CD 0x12
#define SCECdPS2DVD 0x14
#define FOLDER_SUB_MAX 128
#define FOLDER_DEPTH_MAX 8
static int cancelled, probes, allocation = -1, readFailure = -1, statFailure;
static int openDirs, maxDirs, closeResult;
static void *test_malloc(size_t n) {
    if (allocation == 0) return NULL;
    if (allocation > 0) allocation--;
    return malloc(n);
}
static void *test_calloc(size_t n, size_t size) {
    if (allocation == 0) return NULL;
    if (allocation > 0) allocation--;
    return calloc(n, size);
}
typedef struct {
    unsigned int mode, size, hisize;
    unsigned char mtime[8];
} iox_stat_t;
typedef struct { iox_stat_t stat; char name[256]; } iox_dirent_t;
#define FIO_S_ISDIR(mode) (((mode) & 0xF000) == 0x1000)
#define FIO_S_ISREG(mode) (((mode) & 0xF000) == 0x2000)
static int realStat(const char *path, iox_stat_t *info) {
    struct stat st;
    unsigned long long modified;
    if (statFailure) return -EIO;
    if (stat(path, &st) < 0) return -errno;
    info->mode = S_ISDIR(st.st_mode) ? 0x1000 : 0x2000;
    info->size = (uint64_t)st.st_size;
    info->hisize = (uint64_t)st.st_size >> 32;
    if (strstr(path, "Root.iso")) { info->size = 0x4000007b; info->hisize = 1; } // 5 GiB + 123
    modified = st.st_mtime;
    memcpy(info->mtime, &modified, 8);
    return 0;
}
static int fileXioGetStat(const char *path, iox_stat_t *info) {
    int result = realStat(path, info);
    // Actual server OPEN/GETSTAT fallback loses virtual-image metadata.
    if (!result && strstr(path, ".cso.iso")) {
        info->size = info->hisize = 0;
        memset(info->mtime, 0, sizeof(info->mtime));
    }
    return result;
}
static DIR *currentDir;
static char currentPath[256];
static int fileXioDopen(const char *path) {
    assert(!currentDir);
    currentDir = opendir(path);
    if (!currentDir) return -errno;
    strcpy(currentPath, path);
    if (++openDirs > maxDirs) maxDirs = openDirs;
    return 7;
}
static int fileXioDclose(int fd) {
    int result;
    assert(fd == 7 && currentDir);
    result = closedir(currentDir);
    currentDir = NULL;
    openDirs--;
    return result < 0 ? -errno : closeResult;
}
static int fileXioDread(int fd, iox_dirent_t *entry) {
    struct dirent *de;
    char path[512];
    assert(fd == 7 && currentDir);
    if (readFailure == 0) return -EIO;
    if (readFailure > 0) readFailure--;
    errno = 0;
    de = readdir(currentDir);
    if (!de) return errno ? -errno : 0;
    strcpy(entry->name, de->d_name);
    snprintf(path, sizeof(path), "%s/%s", currentPath, de->d_name);
    return realStat(path, &entry->stat) < 0 ? -EIO : 1;
}
int ioScanCancelled(void) { return cancelled; }
int sbIsoStartup(const char *path, char *startup, int size) {
    FILE *f = fopen(path, "rb");
    int ok;
    probes++;
    assert(openDirs <= 1); // leave the other UDPFS handles to art and ISO mounts
    if (!f) return 0;
    ok = fgets(startup, size, f) && !strncmp(startup, "SLUS_", 5);
    fclose(f);
    return ok;
}
#define malloc test_malloc
#define calloc test_calloc
@TYPES@
@HEADER@
@SOURCE@
#undef malloc
#undef calloc
static base_game_info_t *udpfsGames;
static udpfs_game_file_t *udpfsFiles;
static int udpfsGameCount;
static char sbPathOverride[256], sbBrowseSub[FOLDER_SUB_MAX];
static unsigned int USBA_crc32(const char *name) { (void)name; return 0; }
@PATH_CODE@

static int find(base_game_info_t *games, int count, const char *name) {
    int i;
    for (i = 0; i < count; i++) if (!strcmp(games[i].name, name)) return i;
    fprintf(stderr, "Missing %s among %d entries\n", name, count);
    abort();
}
int main(int argc, char **argv) {
    base_game_info_t *games = NULL, *oldGames;
    udpfs_game_file_t *files = NULL, *oldFiles;
    char prefix[256], path[256], expected[256];
    int count = 0, oldCount, i, before, failures = 0;
    assert(argc == 2);
    snprintf(prefix, sizeof(prefix), "%s/", argv[1]);
    closeResult = 1; // PS2 fileXio can report positive success through newlib
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) == 10);
    assert(openDirs == 0 && maxDirs == 1);
    assert(!udpfsListChanged());
    i = find(games, count, "Compressed.cso");
    assert(files[i].bytes > 0 && files[i].modified > 0); // DREAD, not OPEN metadata
    statFailure = 1;
    assert(udpfsListChanged());
    statFailure = 0;
    snprintf(expected, sizeof(expected), "%s/Root.iso", argv[1]);
    for (i = 0; i < count && strcmp(files[i].path, expected); i++);
    assert(i < count);
    assert(files[i].bytes == (5ULL << 30) + 123 && games[i].sizeMB == 5120);
    assert(!strcmp(games[i].startup, "SLUS_111.11"));
    assert(udpfsFilePath(&games[i], &files[i], games[i].name, path, sizeof(path)));
    snprintf(expected, sizeof(expected), "%s/Root.iso", argv[1]);
    assert(!strcmp(path, expected));
    assert(udpfsFilePath(&games[i], &files[i], "Renamed", path, sizeof(path)));
    snprintf(expected, sizeof(expected), "%s/Renamed.iso", argv[1]);
    assert(!strcmp(path, expected));
    assert(!udpfsFilePath(&games[i], &files[i], "../escape", path, sizeof(path)) && !path[0]);
    assert(!udpfsFilePath(&games[i], &files[i], games[i].name, path, 5) && !path[0]);
    i = find(games, count, "Classic");
    assert(games[i].format == GAME_FORMAT_OLD_ISO && !strcmp(games[i].startup, "SLUS_222.22"));
    assert(udpfsFilePath(&games[i], &files[i], "New", path, sizeof(path)));
    snprintf(expected, sizeof(expected), "%s/DVD/SLUS_222.22.New.ISO", argv[1]);
    assert(!strcmp(path, expected));
    i = find(games, count, "CD game");
    assert(games[i].media == SCECdPS2CD);
    i = find(games, count, "Compressed.cso");
    assert(strstr(files[i].path, "Compressed.cso.iso"));
    i = find(games, count, "Deep");
    assert(strstr(files[i].path, "RPG/a/b/c/d/e/f/Deep.iso"));
    udpfsGames = games; udpfsFiles = files; udpfsGameCount = count;
    strcpy(sbBrowseSub, "unrelated-device-folder");
    for (i = 0; i < count; i++) {
        sbCreatePath(&games[i], path, "udpfs:/", "/", 0);
        assert(!strcmp(path, files[i].path));
    }
    before = probes;
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) == 10);
    assert(probes == before + 1); // only the intentionally invalid ISO is re-probed
    oldGames = games; oldFiles = files; oldCount = count;
    cancelled = 1;
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) < 0);
    cancelled = 0;
    closeResult = -1;
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) < 0);
    assert(games == oldGames && files == oldFiles && count == oldCount && !openDirs);
    closeResult = 0;
    for (i = 0; i < 12; i++) {
        readFailure = i;
        assert(udpfsReadList(&games, &files, &count, prefix, "", 0) < 0);
        assert(games == oldGames && files == oldFiles && count == oldCount && !openDirs);
    }
    readFailure = -1;
    statFailure = 1;
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) < 0);
    statFailure = 0;
    assert(udpfsReadList(&games, &files, &count, "/missing-ripps2-share/", "", 0) < 0);
    assert(games == oldGames && files == oldFiles && count == oldCount);
    for (i = 0; i < 80; i++) {
        allocation = i;
        if (udpfsReadList(&games, &files, &count, prefix, "", 0) >= 0) break;
        failures++;
        assert(games == oldGames && files == oldFiles && count == oldCount && !openDirs);
    }
    allocation = -1;
    assert(failures > 15 && i < 80);
    assert(udpfsReadList(&games, &files, &count, prefix, "", 1) == 8);
    i = find(games, count, "RPG");
    assert(games[i].format == GAME_FORMAT_FOLDER);
    assert(!udpfsFilePath(&games[i], &files[i], games[i].name, path, sizeof(path)) && !path[0]);
    assert(udpfsReadList(&games, &files, &count, prefix, "RPG", 1) == 4);
    find(games, count, "Generic nested"); find(games, count, "OPL nested");
    find(games, count, "CD nested"); find(games, count, "a");
    snprintf(prefix, sizeof(prefix), "%s/flat/", argv[1]);
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) == 1);
    snprintf(prefix, sizeof(prefix), "%s/empty/", argv[1]);
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) == 0);
    assert(!games && !files && !count && !openDirs);
    udpfsListReset();
    puts("PASS: UDPFS mixed/flat/OPL layouts, case, aliases, paths, cache, folders and atomic failures");
}
'''
harness = harness.replace('@TYPES@', types).replace('@HEADER@', without_includes((ROOT / 'include/udpfslist.h').read_text()))
harness = harness.replace('@SOURCE@', without_includes(source)).replace('@PATH_CODE@', path_code)

with tempfile.TemporaryDirectory(prefix='ripps2-udpfs-') as tmp:
    tmp = Path(tmp)
    share = tmp / 'share'
    fixture = [
        'Root.iso', 'DVD/SLUS_222.22.Classic.ISO', 'cd/CD game.iso',
        'RPG/Generic nested.iso', 'DVD/RPG/OPL nested.iso', 'cd/RPG/CD nested.iso',
        'Compressed.cso.iso', 'RPG/a/b/c/d/e/f/Deep.iso', 'flat/Flat.iso',
        'DVD/Root.iso', 'ART/Ignore.iso', 'neutrino/Ignore.iso',
        'raw.cso', 'raw.zso', 'ul.cfg', 'Broken.iso',
    ]
    for name in fixture:
        p = share / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'not an ISO' if name == 'Broken.iso' else b'SLUS_111.11')
    (share / 'empty').mkdir()
    before = {str(p.relative_to(share)): p.read_bytes() for p in share.rglob('*') if p.is_file()}
    c = tmp / 'test.c'
    exe = tmp / 'test'
    c.write_text(harness)
    subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-g',
                    '-fsanitize=address,undefined', '-o', str(exe), str(c)], check=True)
    subprocess.run([str(exe), str(share)], check=True)
    after = {str(p.relative_to(share)): p.read_bytes() for p in share.rglob('*') if p.is_file()}
    assert before == after, 'Scanning must not write to the server'
