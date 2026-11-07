# UDPFS artwork downloads

Build 159 adds MMCE staging for PS2 front covers while using **UDPFS Files**.
It uses the disc IDs already found by RIPPS2, so the PC does not need to inspect
ISOs or compressed images. UDPBD and UDPFS block-device mode remain unsupported.

1. Start the UDPFS game list and enable writes. With folder navigation enabled,
   the job covers the current list; jobs currently hold up to 512 missing covers.
2. Open **Download** in Artwork settings, or **Cover Art** in Network settings.
3. Select MMCE card 1 or 2. If that card has a saved job, choose **Resume staged
   artwork** or **Start a new artwork job**. Resuming offers download or copy-only.
4. For a new job, select HD (280 × 400) or Standard (140 × 200).
5. Keep the card inserted while the network restarts and the covers download.
   The Internet phase needs a working IP configuration, gateway and DNS. A PC
   connected directly for UDPFS does not automatically provide Internet access.
6. When UDPFS returns, choose whether to copy completed covers back now.

The job manifest is saved before any network teardown. Network switching uses
IOP resets: MMCE and controllers are reinitialized, and automatic source startup
is suspended during the job. Saved network/source preferences are not changed.
On return, the normal sources and audio are initialized again.

## Manual transfer

Each job gets its own directory, displayed by the completion dialog:

```text
mmce0:/RIPPS2/ARTWORK/<job-token>/
    ART/
        SLUS_203.12_COV.png
    0.ok
```

Copy the job's `ART` folder into the original server library root, preserving
existing files. The folder uses the server's actual capitalization (`art` if
that is what RIPPS2 resolved). The `.ok` receipts and `job0.bin` / `job1.bin`
manifests are for resuming on the PS2 and are not required by the server.

A completed PNG has a matching `<index>.ok` receipt. The receipt's index refers
to its entry in the manifest; the PS2 verifies both file length and checksum
before accepting it. A failed or interrupted download can leave an incomplete
PNG without a valid receipt: **resume the job before copying its folder manually**.
Keep old job directories until their artwork has been transferred. Starting a
new job retains old directories, but the UI resumes the newest valid manifest.

## Automatic transfer and recovery

Before the first network switch, RIPPS2 attempts to write a unique marker under
the original server's `RIPPS2` directory. Automatic delivery requires that exact
marker after reconnection. It will not create a replacement marker on a newly
discovered server. If the original share is read-only, downloading to MMCE still
works, but the user must copy the files manually.

Completed files are copied and read back for byte verification. MMCE copies are
always retained, including after success. Different existing server artwork is
preserved. A pending marker allows a later resume to repair an interrupted upload
only when the destination is a byte-for-byte prefix of this job's staged image.
An unknown partial file, or one with different contents, is preserved.

The UDPFS driver has no rename operation, so a final filename can be visible
before an upload completes. Keep the job on MMCE until verification succeeds;
use **Resume staged artwork → Copy completed files to UDPFS** after a disconnect
or power loss. Copy-only resume does not redownload covers or rescan game images.
Only files with valid local completion receipts are eligible for delivery.

Failed network startup, missing MMCE, server mismatch, and cancellation leave
the staged files available for retry. The dual manifest slots permit fallback
to the previous valid job if writing a new manifest was interrupted. A job
captures the library at creation time; start a new job to include newly added games.

## Validation and console checks

Host harnesses exercise the actual job persistence, upload recovery, controller
workflow and maintenance lifecycle. They cover truncated files/manifests,
corrupt receipts, invalid destinations, existing artwork, incorrect shares,
manual export, copy-only resume, and network failure restoration.

Hardware validation remains required: repeated UDPFS → Internet → UDPFS cycles,
both MMCE slots, controller recovery, HDD coexistence, cable removal during
download/upload, card removal, and interrupted-power recovery. The existing
low-level IOP reset/RPC primitives can still block if the IOP itself is wedged;
host tests and a successful ELF build do not establish hardware compatibility.

This feature downloads PS2 front covers from the existing xlenore provider.
It does not add PS1, disc-art or background-art providers.
