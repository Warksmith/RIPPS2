"""Build 117 (the user, 10/27: after a BIOS Music rip the music stopped behind the message box, and stopped again as the
menus were cycled): the .wav music read on an SD2PSX whose descriptor a failed open elsewhere clobbers.

Compiles sound.c's .wav reader (wavOpen, wavRead) with the music source it reads through (bgmCacheRead and the reopen)
against RiptOPL's model of the sd2psxtd file service (test_bgm_source.py's: a failed lookup stores -1 in the card's
descriptor, and the next read or seek of any open file writes only its low byte, so it fails). Plays a WAV round its end
twice with lookups failing between reads: every frame must come back, in order, the loop included."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(os.environ.get('RIPTOPL_DIR', '.'))
snd = (root / 'src/sound.c').read_text(encoding='utf-8').replace('\r\n', '\n')
fail = []

cc = shutil.which('gcc') or shutil.which('cc')
if cc is None:
    print('wav source: no host C compiler, skipped')
    sys.exit(0)

wav = snd[snd.index('static volatile int bgmOnce = 0;'):]
wav = wav[:wav.index('\n}\n', wav.index('static int wavOpen(const char *path)')) + 3]
src = snd[snd.index('#define BGM_REOPEN_TRIES'):snd.index('static ov_callbacks bgmSourceCallbacks')]
for need in ('wavSrc = audSrcOpen(path)', 'audSrcRead(wavSrc, wavIn, want)'):
    if need not in wav:
        fail.append('wavOpen / wavNextFrame: %s (the .wav reads through the music\'s source)' % need)

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int logs;
#define LOG(...) (logs++)
typedef long long ogg_int64_t;

#define FRAMES 200000
#define MUSIC_SIZE (44 + FRAMES * 4)
#define CARD_FILES 16
static unsigned char music[MUSIC_SIZE];
static int cardOpen[CARD_FILES];
static long cardPos[CARD_FILES];
static int opFd;

typedef struct { int handle; } FAKEFILE;

static void failedLookup(void) { opFd = -1; } /* a missing cover's open, the settings save's probe */

static int cardSelect(int handle)
{
    opFd = (int)(((unsigned)opFd & ~0xffu) | ((unsigned)handle & 0xffu));
    return (opFd >= 0 && opFd < CARD_FILES && cardOpen[opFd]) ? opFd : -1;
}

static FAKEFILE *fake_fopen(const char *path, const char *mode)
{
    FAKEFILE *f;
    int i;
    (void)path;
    (void)mode;
    for (i = 0; i < CARD_FILES && cardOpen[i]; i++)
        ;
    if (i == CARD_FILES) {
        opFd = -1;
        return NULL;
    }
    cardOpen[i] = 1;
    cardPos[i] = 0;
    opFd = i;
    f = malloc(sizeof(*f));
    f->handle = i;
    return f;
}

static size_t fake_fread(void *ptr, size_t size, size_t nmemb, FAKEFILE *f)
{
    int h = cardSelect(f->handle);
    long want = (long)(size * nmemb);
    if (h < 0)
        return 0;
    if (want > MUSIC_SIZE - cardPos[h])
        want = MUSIC_SIZE - cardPos[h];
    if (want < 0)
        want = 0;
    memcpy(ptr, music + cardPos[h], (size_t)want);
    cardPos[h] += want;
    return (size_t)want / size;
}

static int fake_fseek(FAKEFILE *f, long offset, int whence)
{
    int h = cardSelect(f->handle);
    long target;
    if (h < 0)
        return -1;
    target = whence == SEEK_SET ? offset : (whence == SEEK_CUR ? cardPos[h] + offset : MUSIC_SIZE + offset);
    if (target < 0)
        return -1;
    cardPos[h] = target;
    return 0;
}

static long fake_ftell(FAKEFILE *f)
{
    int h = cardSelect(f->handle);
    return h < 0 ? -1 : cardPos[h];
}

static int fake_fclose(FAKEFILE *f)
{
    int h = cardSelect(f->handle);
    free(f);
    if (h < 0)
        return -1;
    cardOpen[h] = 0;
    return 0;
}

static int DelayThread(int us) { (void)us; return 0; }
/* build 156: the music's file is unbuffered and its reads go into DIAG.TXT */
#include <time.h>
static int fake_setvbuf(FAKEFILE *f, char *buf, int mode, size_t size) { (void)f; (void)buf; (void)mode; (void)size; return 0; }
#define setvbuf fake_setvbuf
static void ripps2Diag(const char *fmt, ...) { (void)fmt; }

#define FILE   FAKEFILE
#define fopen  fake_fopen
#define fread  fake_fread
#define fseek  fake_fseek
#define ftell  fake_ftell
#define fclose fake_fclose

static int (*bgmPcmRead)(char *buf, int size) = NULL;
static int bgmPcmRate = 44100, bgmPcmChannels = 2;

@WAV@
@SRC@

static void put32(unsigned char *p, unsigned v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }
static void put16(unsigned char *p, unsigned v) { p[0] = v; p[1] = v >> 8; }
static short left(long k) { return (short)((k * 7) & 0x7fff); }
static short right(long k) { return (short)(-(short)((k * 13) & 0x7fff)); }

int main(void)
{
    static char chunk[4096];
    long frame = 0, k;
    int reads = 0, bad = 0, i;

    memcpy(music, "RIFF", 4);
    put32(music + 4, MUSIC_SIZE - 8);
    memcpy(music + 8, "WAVEfmt ", 8);
    put32(music + 16, 16);
    put16(music + 20, 1);
    put16(music + 22, 2);
    put32(music + 24, 48000);
    put32(music + 28, 48000 * 4);
    put16(music + 32, 4);
    put16(music + 34, 16);
    memcpy(music + 36, "data", 4);
    put32(music + 40, FRAMES * 4);
    for (k = 0; k < FRAMES; k++) {
        put16(music + 44 + k * 4, (unsigned short)left(k));
        put16(music + 46 + k * 4, (unsigned short)right(k));
    }
    if (!wavOpen("mmce0:/RIPPS2/AUDIO/bios_menu.wav") || bgmPcmRead != wavRead) {
        printf("FAIL open\n");
        return 1;
    }
    while (frame < 2 * FRAMES + 12345) { /* round the end twice */
        int got = bgmPcmRead(chunk, sizeof(chunk));
        if (got != (int)sizeof(chunk)) {
            printf("FAIL read %d returned %d at frame %ld\n", reads, got, frame);
            return 1;
        }
        for (i = 0; i < got / 4; i++, frame++) {
            short l = (short)(((unsigned char)chunk[i * 4]) | (chunk[i * 4 + 1] << 8));
            short r = (short)(((unsigned char)chunk[i * 4 + 2]) | (chunk[i * 4 + 3] << 8));
            if (l != left(frame % FRAMES) || r != right(frame % FRAMES)) {
                if (bad++ < 3)
                    printf("FAIL frame %ld: %d %d, wanted %d %d\n", frame, l, r, left(frame % FRAMES), right(frame % FRAMES));
            }
        }
        if (++reads % 7 == 0)
            failedLookup(); /* something else on the card opened a file that is not there */
    }
    wavClose();
    printf("%d reads, %ld frames, %d wrong\n", reads, frame, bad);
    return bad != 0;
}
'''

if not fail:
    with tempfile.TemporaryDirectory() as tmp:
        c, exe = os.path.join(tmp, 'wav.c'), os.path.join(tmp, 'wav.exe')
        open(c, 'w').write(HARNESS.replace('@WAV@', wav).replace('@SRC@', src))
        r = subprocess.run([cc, '-std=gnu99', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable', c, '-o', exe],
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail.append('the .wav reader does not compile on its own:\n' + r.stderr[-2000:])
        else:
            out = subprocess.run([exe], capture_output=True, text=True)
            if out.returncode != 0:
                fail.append('the .wav reader on a card that loses descriptors: ' + (out.stdout + out.stderr).strip()[-600:])
            else:
                print(out.stdout.strip())

if fail:
    print('\n'.join(fail))
    sys.exit(1)
print('wav source: a .wav track plays on through lost descriptors, round its end, every frame in order OK')
