# Neutrino (found, not carried)

**Neutrino** is a small, fast and modular PS2 device emulator by **rickgaiser**, licensed **AFL-3.0**
(`LICENSE.txt`, beside this file). Releases: <https://github.com/rickgaiser/neutrino/releases>

RIPPS2 starts games through the Neutrino you keep. Since build 135 (v1.3.5-beta) it no longer carries a copy: put
Neutrino's release folder as `neutrino/` on the game's drive or on a memory card (`mc0:/neutrino/`, `mc1:/neutrino/`),
or point **Game Launching > Neutrino** at its `neutrino.elf`. RIPPS2 looks there, then wherever **STATUS > LOOK FOR
THEM** or an earlier launch found one, and a launch that finds none says where to put it. RIPPS2 reads the install's
`version.txt` (or, for an older kit, its `config/` files) and sends it only the options it knows.

Builds 77 to 134 carried Neutrino inside RIPPS2.elf and installed it where the user picked (1.8.0, then from build 115
the development build v1.8.0-61-g7be8de2). That tar is in this folder's history:
`git log -- elf/neutrino/neutrino-1.8.0-61-g7be8de2.tar.gz`. `tools/dev/pack_neutrino.py` still repacks a release
the same way, for anyone who wants that copy.

On the IGR branch, GameID-capable **Neutrino LUNA** installations receive the
return and deferred card-switch arguments automatically. Install the full
matching runtime. The `igr-hardening` runtime requires `modules/mmceigr.irx`;
current LUNA embeds restoration support in its EE core. Put RIPPS2 on the restored
boot memory card and set IGR Path to its `mc0:/` or `mc1:/` ELF path.
Build 148 recognizes both unpacked and standard ps2-packer LZMA LUNA
executables; build 147 missed the packed executable's IGR options.
See [IGR setup and engine-specific behavior](../../docs/igr.md).

Build 160 recognizes both the legacy `-mmce_gameid=<slot>:<GameID>` parser
and current LUNA's standalone `-mmce-gameid` flag, including packed loaders.
It passes the supported form and leaves switching/restoration to Neutrino.
The modern interface derives the ID and chooses slots itself. Because it
cannot exclude VMC-protected slots, automatic switching is skipped with an
active VMC unless the runtime also supports the legacy slot-specific form.
Official stock Neutrino does not gain LUNA-only arguments from its version
number or usage text.

For the build 149 IGR test kit, `build_igr_runtime.sh` builds the complete
GameID-capable LUNA runtime at `af68bf4` into a separate directory. It uses
LUNA's pinned build image documented in the script and IGR setup guide.
This optional runtime is not embedded in RIPPS2 or installed over an
existing Neutrino folder.

Console testing confirmed `af68bf4-IGR` can return directly to RIPPS2 on the
restored boot card. The failing `F:/neutrino` was
the older `02cbf4f` build, which lacks MMCE restoration. Merely having `-igr`
support does not make a runtime compatible with GameID-switched cards.

The optional `hardened` third argument to `build_igr_runtime.sh` applies
`igr-runtime-hardening.patch` and builds `af68bf4-IGR-h1`. It adds loader/core
ABI checks, complete module reads, early return-path validation and explicit
failure for missing restoration support or an unconfirmed card switch.
It preserves the working resident return sequence. Install its entire
folder separately and select that loader explicitly. The build includes
`SHA256SUMS`; the user has confirmed this variant also works for direct
memory-card return to RIPPS2. Host regression checks:

```sh
NEUTRINO_DIR=/path/to/patched/neutrino python3 elf/neutrino/test_igr_runtime.py
```
