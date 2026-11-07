"""Run the UDPFS catalogue/path code against a real host directory tree.

Includes partial I/O, cancellation and allocation failures: an incomplete scan
must never replace the last-good list or detach its exact server paths.
"""
import os
from pathlib import Path
import re
import struct
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
#define ripps2Diag(...) ((void)0)
typedef uint8_t u8;
typedef uint32_t u32;
#define SCECdPS2CD 0x12
#define SCECdPS2DVD 0x14
#define FOLDER_SUB_MAX 128
#define FOLDER_DEPTH_MAX 8
static int cancelled, probes, allocation = -1, readFailure = -1, statFailure;
static int openDirs, maxDirs, closeResult;
static int unknownMetadata;
static int gRipps2FastCache, gEnableWrite, writeAllowed = 1, writes, activeWrites;
static int ioWriteBegin(void) {
    if (!writeAllowed) return 0;
    writes++; activeWrites++; return 1;
}
static void ioWriteEnd(void) { assert(activeWrites == 1); activeWrites--; }
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
    if (unknownMetadata && strstr(path, ".iso")) memset(info->mtime, 0, 8);
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
    startup[strcspn(startup, "\r\n")] = 0;
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
    udpfs_asset_names_t assets;
    char prefix[256], path[256], expected[256];
    int count = 0, oldCount, i, before, failures = 0;
    assert(argc == 2 || argc == 7);
    snprintf(prefix, sizeof(prefix), "%s/", argv[1]);
    if (argc == 7) {
        int result;
        gRipps2FastCache = strcmp(argv[2], "cache-disabled") != 0;
        gEnableWrite = strcmp(argv[2], "write-disabled") != 0;
        writeAllowed = strcmp(argv[2], "write-blocked") != 0;
        unknownMetadata = !strcmp(argv[2], "unknown-stat");
        cancelled = !strcmp(argv[2], "cancel");
        if (!strcmp(argv[2], "read-failure")) readFailure = 0;
        result = udpfsReadList(&games, &files, &count, prefix, "", !strcmp(argv[2], "browse"));
        assert(result == atoi(argv[4]) && probes == atoi(argv[3]) && writes == atoi(argv[5]));
        assert(!activeWrites && !openDirs);
        if (result > 0) {
            i = find(games, count, "Compressed.cso");
            assert(!strcmp(games[i].startup, argv[6]));
            assert(strstr(files[i].path, "Compressed.cso.iso"));
            i = find(games, count, "Classic");
            assert(!strcmp(games[i].startup, "SLUS_222.22"));
            // Fresh metadata still populates the list and exact paths on cache hits.
            i = find(games, count, "Root");
            assert(games[i].sizeMB == 5120);
        }
        free(games); free(files); udpfsListReset();
        return 0;
    }
    closeResult = 1; // PS2 fileXio can report positive success through newlib
    assert(udpfsReadList(&games, &files, &count, prefix, "", 0) == 10);
    assert(udpfsTakeAssetNames(&assets) && assets.count == 4);
    assert(!udpfsTakeAssetNames(&assets)); // one use; missing folders must be retried live
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
    assert(!udpfsTakeAssetNames(&assets)); // never publish roots from a cancelled scan
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
        'DVD/Root.iso', 'ART/Ignore.iso', 'ARt/Ignore.iso', 'thm/Ignore.iso', 'LNG/Ignore.iso',
        'RPG/THM/Ignore.iso', 'neutrino/Ignore.iso',
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

    def scan(mode='cache', probes=1, count=10, writes=0, startup='SLUS_111.11'):
        # A new process for every call: no in-memory IDs survive a restart.
        subprocess.run([str(exe), str(share), mode, str(probes), str(count), str(writes), startup], check=True)

    cache = share / 'RIPPS2.UID'
    scan('write-disabled', probes=10)
    assert not cache.exists()
    scan('write-blocked', probes=10)
    assert not cache.exists()
    scan(probes=10, writes=1)
    good = cache.read_bytes()
    assert good[:8] == b'RIPUID01'
    assert struct.unpack_from('<I', good, 8)[0] == 9
    scan()  # Only the invalid ISO is probed; valid compressed and plain ISOs are unopened.
    scan('write-disabled')  # A read-only library can consume a previously generated cache.
    scan('browse', count=8)
    scan('cancel', probes=0, count=-1)
    scan('read-failure', probes=0, count=-1)
    assert cache.read_bytes() == good, 'Incomplete/subfolder/unchanged scans must not rewrite IDs'
    scan('cache-disabled', probes=10)
    assert cache.read_bytes() == good
    scan('unknown-stat', probes=10)
    assert cache.read_bytes() == good

    # Changes must re-read SYSTEM.CNF, including same-size replacements with a new timestamp.
    compressed = share / 'Compressed.cso.iso'
    stamp = compressed.stat().st_mtime
    compressed.write_bytes(b'SLUS_333.33')
    os.utime(compressed, (stamp + 5, stamp + 5))
    scan(probes=2, writes=1, startup='SLUS_333.33')
    scan(startup='SLUS_333.33')
    compressed.write_bytes(b'SLUS_444.44\nextra bytes')
    os.utime(compressed, (stamp + 5, stamp + 5))
    scan(probes=2, writes=1, startup='SLUS_444.44')
    scan(startup='SLUS_444.44')
    compressed.write_bytes(b'SLUS_111.11')
    os.utime(compressed, (stamp, stamp))
    scan(probes=2, writes=1)

    new = share / 'New.iso'
    new.write_bytes(b'SLUS_555.55')
    scan(probes=2, count=11, writes=1)
    new.unlink()
    scan(writes=1)
    original = share / 'flat/Flat.iso'
    renamed = share / 'flat/Renamed.iso'
    original.rename(renamed)
    scan(probes=2, writes=1)
    renamed.rename(original)
    scan(probes=2, writes=1)
    good = cache.read_bytes()

    def checksum(data):
        value = 2166136261
        for byte in data:
            value = ((value ^ byte) * 16777619) & 0xffffffff
        return value

    malformed = [b'', good[:19], good[:-1], good + b'x', b'BADMAGIC' + good[8:]]
    for offset, value in [(8, 0xffffffff), (12, 1), (16, 0)]:
        bad = bytearray(good)
        struct.pack_into('<I', bad, offset, value)
        malformed.append(bad)
    # Even checksum-valid malformed strings/duplicate paths cannot supply IDs.
    entry_size = struct.unpack_from('<I', good, 12)[0]
    for kind in ['path', 'startup', 'duplicate']:
        bad = bytearray(good)
        if kind == 'path':
            bad[20:20+256] = b'x' * 256
        elif kind == 'startup':
            bad[20+272:20+285] = b'x' * 13
        else:
            bad[20+entry_size:20+entry_size+256] = bad[20:20+256]
        struct.pack_into('<I', bad, 16, checksum(bad[20:]))
        malformed.append(bad)
    for bad in malformed:
        cache.write_bytes(bad)
        scan(probes=10, writes=1)
        assert cache.read_bytes() == good

    # An unwritable cache path is only a performance loss, never a missing game.
    cache.unlink()
    cache.mkdir()
    scan(probes=10, writes=1)
    cache.rmdir()
    scan(probes=10, writes=1)
    assert {str(p.relative_to(share)): p.read_bytes() for p in share.rglob('*')
            if p.is_file() and p != cache} == before
    # Library-sized case: 291 valid games, one legacy filename, no invalid image.
    (share / 'Broken.iso').unlink()
    cache.unlink()
    for i in range(281):
        (share / f'Library {i:03}.cso.iso').write_bytes(b'SLUS_111.11')
    scan(probes=290, count=291, writes=1)
    scan(probes=0, count=291)
    print('PASS: persistent UDPFS IDs, restart probe reduction 10 -> 1, invalidation, corruption and write guards')
    print('PASS: 291-game library, cold 290 ISO probes -> warm 0 after process restart')
