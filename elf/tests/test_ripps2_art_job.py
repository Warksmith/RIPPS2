"""Compile the real durable artwork-job code, including interrupted file writes."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(os.environ.get('RIPTOPL_DIR', Path(__file__).resolve().parents[2] / 'riptopl')).resolve()
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
static long writeBudget = -1;
static size_t testWrite(const void *p, size_t size, size_t count, FILE *f) {
    if (writeBudget == 0) return 0;
    if (writeBudget > 0 && count > (size_t)writeBudget / size) count = writeBudget / size;
    size_t n = fwrite(p, size, count, f);
    if (writeBudget > 0) writeBudget -= size * n;
    return n;
}
#define fwrite testWrite
#include "src/ripps2artjob.c"
#undef fwrite
static unsigned char image[8193], data[8194];
static art_job_target_t targets[] = {
    {"SLUS-20312", "udpfs:/art/SLUS_203.12_COV", "First game"},
    {"SLES-12345", "udpfs:/art/SLES_123.45_COV", "Second game"}
};
int main(void) {
    const char *root = "mmce0:/RIPPS2/ARTWORK";
    assert(!mkdir("mmce0:", 0700)); assert(!mkdir("udpfs:", 0700));
    art_job_t *job = malloc(sizeof(*job)), *old;
    assert(job && !artJobLoad(root));
    assert(artJobCreate(root, job, targets, 2, 280, 400, 123));
    assert(job->generation == 1);
    old = artJobLoad(root); assert(old && !memcmp(old, job, sizeof(*job)));
    assert(!artJobSameServer(job)); assert(artJobMarkServer(job)); assert(artJobSameServer(job));
    for (unsigned i=0; i<sizeof(image); i++) image[i] = i;
    memcpy(image, "\x89PNG\r\n\x1a\n", 8);
    assert(!artJobRead(root, job, 0, data, sizeof(data)));
    assert(artJobStore(root, job, 0, image, sizeof(image)));
    assert(artJobRead(root, job, 0, data, sizeof(data)) == sizeof(image));
    assert(!memcmp(data, image, sizeof(image)));
    assert(!artJobRead(root, job, 0, data, 8));
    assert(!artJobStore(root, job, 0, data, 7));
    assert(artJobDeliver(root, job, 0, data, sizeof(data)) == 1);
    assert(artJobDeliver(root, job, 0, data, sizeof(data)) == 1);
    assert(jobCompare("udpfs:/art/SLUS_203.12_COV.png", image, sizeof(image)) == 1);
    assert(artJobRead(root, job, 0, data, sizeof(data)) == sizeof(image)); /* retained */

    /* Different existing artwork is preserved. */
    assert(artJobStore(root, job, 1, image, sizeof(image)));
    assert(jobWriteExact("udpfs:/art/SLES_123.45_COV.png", "custom", 6));
    assert(artJobDeliver(root, job, 1, data, sizeof(data)) == 2);
    assert(jobCompare("udpfs:/art/SLES_123.45_COV.png", (unsigned char *)"custom", 6) == 1);

    /* An unknown partial file is preserved; only a matching upload marker permits repair. */
    assert(jobWriteExact("udpfs:/art/SLES_123.45_COV.png", image, 100));
    assert(artJobDeliver(root, job, 1, data, sizeof(data)) == 2);
    assert(!remove("udpfs:/art/SLES_123.45_COV.png"));
    writeBudget = 24 + 2000; /* pending token then interrupted PNG */
    assert(!artJobDeliver(root, job, 1, data, sizeof(data)));
    writeBudget = -1;
    assert(artJobDeliver(root, job, 1, data, sizeof(data)) == 1);

    /* The newly discovered server must hold the original marker. */
    char marker[128]; jobServerMarker(job, marker, sizeof(marker));
    assert(!remove(marker));
    assert(!artJobDeliver(root, job, 0, data, sizeof(data)));
    assert(artJobMarkServer(job));

    /* Truncated PNGs and receipts are never accepted as completed downloads. */
    char staged[512], receipt[512];
    assert(artJobStagePath(root, job, 0, staged, sizeof(staged)));
    assert(jobWriteExact(staged, image, 33));
    assert(!artJobRead(root, job, 0, data, sizeof(data)));
    assert(artJobStore(root, job, 0, image, sizeof(image)));
    jobReceiptPath(root, job, 0, receipt, sizeof(receipt));
    assert(jobWriteExact(receipt, "bad", 3));
    assert(!artJobRead(root, job, 0, data, sizeof(data)));
    writeBudget = sizeof(image) + 2; /* receipt interrupted */
    assert(!artJobStore(root, job, 0, image, sizeof(image)));
    writeBudget = -1;
    assert(!artJobRead(root, job, 0, data, sizeof(data)));
    assert(artJobStore(root, job, 0, image, sizeof(image)));

    /* Interrupted replacement manifest retains the previous valid job. */
    writeBudget = 20;
    assert(!artJobCreate(root, job, targets, 2, 140, 200, 123));
    writeBudget = -1;
    art_job_t *loaded = artJobLoad(root);
    assert(loaded && !memcmp(loaded, old, sizeof(*old))); free(loaded);
    assert(artJobCreate(root, job, targets, 2, 140, 200, 123));
    assert(job->generation == 2 && strcmp(job->token, old->token));
    loaded = artJobLoad(root); assert(loaded && loaded->width == 140); free(loaded);

    /* Even a checksummed manifest cannot name arbitrary server files. */
    strcpy(job->targets[0].path, "udpfs:/../private/target");
    job->checksum = jobHash(job, offsetof(art_job_t, checksum));
    assert(!jobValid(job));
    assert(jobWriteExact("mmce0:/RIPPS2/ARTWORK/job0.bin", job, sizeof(*job)));
    loaded = artJobLoad(root); assert(loaded && loaded->generation == 1); free(loaded);
    targets[0].serial[0] = '.';
    assert(!artJobCreate(root, job, targets, 2, 280, 400, 123));
    free(old); free(job);
    puts("PASS: staged job recovery, checksums, target validation, share identity and verified delivery");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'test.c'
    exe = Path(tmp) / 'test'
    c.write_text(HARNESS, encoding='utf-8')
    subprocess.run(['gcc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT), str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], cwd=tmp, check=True)
