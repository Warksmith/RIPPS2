"""Build 156 (the user's console run, 11/08): a ripped CD .wav skipped on an MMCE card, and backing out of RIPDISC's MEDIA folder
left Memory Files' page under LAUNCH DISC.

- The music's file is unbuffered, so each read is one device request of the size asked for: 32 KB, and on an MMCE card 16 KB
  with a short gap after each (the pads and audsrv get the bus and the IOP between them).
- The music's reads, reopens and underruns go to DIAG.TXT.
- RIPDISC's hand-off into Memory Files' browser takes the category bar to MEMORY FILES, and the browser's ways back to the orbs
  set it too.
- The cover download and the sound preview draw button glyphs, not words.

Static checks on the patched tree."""
import os
import re
import sys
from pathlib import Path

root = Path(os.environ.get('RIPTOPL_DIR', '.'))
rd = lambda p: (root / p).read_text(encoding='utf-8').replace('\r\n', '\n')
snd, files, ui, art, media = rd('src/sound.c'), rd('src/ripps2files.c'), rd('src/ripps2ui.c'), rd('src/ripps2art.c'), rd('src/ripps2media.c')
fail = []


def body(text, name):
    a = text.find(name)
    return text[a:text.find('\n}\n', a)] if a >= 0 else ''


# ---- the music's file: unbuffered, read in pieces, paced on MMCE
opener = body(snd, 'static FILE *bgmOpenFile(const char *path)')
if 'setvbuf(f, NULL, _IONBF, 0)' not in opener:
    fail.append('bgmOpenFile opens the music unbuffered')
if len(re.findall(r'\bfopen\(', snd)) != 1 or 'fopen(' not in opener:
    fail.append('every music file is opened through bgmOpenFile (one fopen in sound.c)')
get = body(snd, 'static size_t bgmSourceGet(bgm_source_t *src, unsigned char *dst, size_t want)')
if 'src->paced ? BGM_MMCE_PIECE : BGM_READ_PIECE' not in get or 'DelayThread(BGM_MMCE_GAP_US)' not in get:
    fail.append('bgmSourceGet reads in pieces, with a gap between MMCE pieces')
m = re.search(r'#define BGM_MMCE_PIECE\s+\((\d+) \* 1024\)', snd)
if not m or int(m.group(1)) > 16:
    fail.append('an MMCE piece is at most 16 KB (one fileXio piece)')
m = re.search(r'#define BGM_READ_PIECE\s+\((\d+) \* 1024\)', snd)
if not m or int(m.group(1)) > 32:
    fail.append('a piece elsewhere is at most 32 KB')
if snd.count('->paced = !strncasecmp(') != 2:
    fail.append('both music sources (the Ogg reader and audSrcOpen) know an MMCE path')
fill = body(snd, 'static int bgmCacheFill(bgm_source_t *src, long at)')
if 'got = bgmSourceGet(src, src->cache, (size_t)want);' not in fill or 'bgmReadNote(src, got, clock() - t0);' not in fill:
    fail.append('bgmCacheFill reads through bgmSourceGet and notes the speed')
if 'got = bgmSourceGet(src, buf + done, n - done);' not in body(snd, 'static size_t bgmCacheRead('):
    fail.append('the no-memory path reads in pieces too')

# ---- DIAG.TXT
note = body(snd, 'static void bgmReadNote(bgm_source_t *src, size_t got, clock_t ticks)')
if 'ripps2Diag("music read %s' not in note or 'BGM_READ_NOTES' not in note or 'kbs >= 176' not in note:
    fail.append('bgmReadNote writes a file\'s first piece and its slow ones, a few per file')
if 'ripps2Diag("music reopened %s at %ld"' not in snd:
    fail.append('a reopen goes into DIAG.TXT')
if 'ripps2Diag("music: audsrv ran dry (%u), %d chunks waiting"' not in snd or 'ripps2Diag("music: the decoder fell behind (%u)"' not in snd:
    fail.append('underruns and an empty reserve go into DIAG.TXT')

# ---- the category bar follows Memory Files' browser
follow = body(ui, 'void ripps2CategoryFollow(int cat)')
if 'catTake(cat);' not in follow or 'guiSwitchScreen' in follow:
    fail.append('ripps2CategoryFollow moves the bar without a switch of its own')
if 'catTake(cat);' not in body(ui, 'void ripps2SetCategory(int cat)'):
    fail.append('ripps2SetCategory shares catTake')
ripped = body(files, 'void ripps2FilesRipped(const char *what, const char *dir)')
if ripped.find('ripps2CategoryFollow(RIPPS2_CAT_MEMORY);') < ripped.find('guiSwitchScreen(GUI_SCREEN_RIPPS2_FILES);'):
    fail.append('RIPDISC\'s hand-off takes the bar to MEMORY FILES with the browser')
for m in re.finditer(r'guiSwitchScreen\(GUI_SCREEN_RIPPS2_MEMORY\);\n', files):
    if 'ripps2CategoryFollow(RIPPS2_CAT_MEMORY);' not in files[m.end():m.end() + 120]:
        fail.append('the browser\'s way back to the orbs at %d sets the bar too' % m.start())

# ---- glyphs, not words
if 'Circle: stop' in art or 'Cross: stop' in art or 'ripps2HintOneA(' not in body(art, 'static void artDraw(void)'):
    fail.append('Download Covers draws the stop button\'s glyph')
if 'play again   ' in media or 'ripps2HintPairA(' not in media:
    fail.append('the sound preview draws its buttons\' glyphs')

print('\n'.join(fail) or 'build156: paced MMCE music, its reads in DIAG.TXT, the bar follows the browser, glyph hints OK')
sys.exit(1 if fail else 0)
