"""Run the real staged-artwork UI controller with real job files and fake hardware."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl')).resolve()
source = (ROOT / 'src/ripps2art.c').read_text()
start = source.index('static void artDownloadStaged(void)')
workflow = source[start:source.index('\nstatic const char *artNetworkConflict', start)]
HARNESS = r'''
#include <assert.h>
#include "src/ripps2artjob.c"
#define _t(x) (x)
#define ART_MAX_GAMES ART_JOB_MAX
#define ART_MAX_BYTES ART_JOB_BYTES
#define ART_HD_W 280
#define ART_HD_H 400
#define ART_STD_W 140
#define ART_STD_H 200
#define NET_PROTO_SMB 1
#define UDPFS_MODE 9
typedef art_job_target_t art_target_t;
static art_target_t *artTargets;
static int artCount, artDone, artGot, artMissing, artFailed, artCovW, artCovH;
static char artLine[96], artLine2[96], notice[1024];
static const char *artStage;
static int gEnableWrite = 1, gNetworkStartup = 311;
static int picks[8], replies[8], pi, ri, began, ended, resets, downloads, scans, networkCalls;
static int busy, netFail, serverFail, blocked;
static int ripps2PickList(const char **items, int count) { (void)items; int n=picks[pi++]; assert(n < count); return n; }
static int guiMsgBox(const char *s, int question, void *unused) {
    (void)unused; snprintf(notice, sizeof(notice), "%s", s); return question ? replies[ri++] : 0;
}
static void guiMsgBoxStartOption(const char *s) { (void)s; }
static void mmceLoadModules(void) {}
static void artDraw(void) {}
static void ioBlockOpsTimed(int block, int ticks) { (void)ticks; blocked=block; }
static void ioBlockOps(int block) { blocked=block; }
static int ioHasPendingRequests(void) { return 0; }
static int ioWriteBegin(void) { return 1; }
static void ioWriteEnd(void) {}
static unsigned int GetTimerSystemTime(void) { return 1234; }
static void artCollect(int mode) {
    assert(mode == UDPFS_MODE);
    scans++; artCount=2;
    artTargets[0]=(art_target_t){"SLUS-20312", "udpfs:/ART/SLUS_203.12_COV", "Remote game"};
    artTargets[1]=(art_target_t){"SLES-12345", "mass0:/ART/SLES_123.45_COV", "Local game"};
}
static int ripps2ArtSessionBegin(void) { if(busy) return 0; began++; blocked=1; return 1; }
static void ripps2ArtSessionReset(void) { assert(blocked); resets++; }
static void ripps2ArtSessionEnd(void) { assert(blocked); ended++; blocked=0; }
static int netLoadInitModules(int proto) { assert(proto==1 && blocked); networkCalls++; return netFail; }
static void artDownloadTargets(unsigned char *body, unsigned char *rgb, const art_job_t *job, const char *root) {
    (void)body; (void)rgb; assert(blocked); downloads++;
    unsigned char png[256]={0}; memcpy(png,"\x89PNG\r\n\x1a\n",8);
    assert(artJobStore(root,job,0,png,sizeof(png))); artGot=1;
}
static int udpfsEnsureReady(unsigned int ms) { assert(ms==5000 && blocked); return !serverFail; }
static int artCancelled(void) { return 0; }
static void ripps2ArtPackNoteNew(const char *p) { assert(!strncmp(p,"udpfs:/",7)); }
@WORKFLOW@
static void resetInputs(void) {
    pi=ri=began=ended=resets=downloads=scans=networkCalls=blocked=0;
    busy=netFail=serverFail=0; memset(picks,0,sizeof(picks)); memset(replies,0,sizeof(replies));
}
int main(void) {
    assert(!mkdir("mmce0:",0700)); assert(!mkdir("udpfs:",0700));
    resetInputs(); replies[0]=replies[1]=replies[2]=1;
    artDownloadStaged();
    assert(began==1 && ended==1 && resets==1 && scans==1 && downloads==1 && !blocked && !artTargets);
    assert(strstr(notice,"1 covers verified"));
    art_job_t *job=artJobLoad("mmce0:/RIPPS2/ARTWORK"); assert(job && job->count==1); free(job);

    /* Transfer-only resume does not rescan games or start Internet networking. */
    resetInputs(); picks[2]=1;
    artDownloadStaged();
    assert(began==1 && ended==1 && !scans && !downloads && !networkCalls && !artTargets);

    resetInputs(); replies[0]=1; netFail=1;
    artDownloadStaged();
    assert(ended==1 && !downloads && !blocked && !artTargets && strstr(notice,"311"));

    resetInputs(); replies[0]=1; busy=1;
    artDownloadStaged();
    assert(!began && !ended && !networkCalls && !artTargets);

    /* New job + manual export still restores the menu and keeps staged files. */
    remove("udpfs:/ART/SLUS_203.12_COV.png");
    resetInputs(); picks[1]=1; replies[0]=replies[1]=1; replies[2]=0;
    artDownloadStaged();
    assert(ended==1 && downloads==1 && !blocked && strstr(notice,"Staged artwork"));

    resetInputs(); picks[2]=1; serverFail=1;
    artDownloadStaged();
    assert(ended==1 && !networkCalls && strstr(notice,"did not reconnect"));

    /* A different share must not receive the resume job. */
    job=artJobLoad("mmce0:/RIPPS2/ARTWORK"); assert(job);
    char marker[128]; jobServerMarker(job,marker,sizeof(marker)); remove(marker); free(job);
    resetInputs(); picks[2]=1;
    artDownloadStaged();
    assert(ended==1 && strstr(notice,"marker was not found"));

    /* Absent MMCE: refuse before any teardown. */
    resetInputs(); picks[0]=1; replies[0]=1;
    artDownloadStaged();
    assert(!began && !artTargets && strstr(notice,"Could not save"));
}
'''.replace('@WORKFLOW@', workflow)
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'test.c'
    exe = Path(tmp) / 'test'
    c.write_text(HARNESS)
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT), str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
print('PASS: new job, download, transfer-only resume, manual export and failure restoration')
