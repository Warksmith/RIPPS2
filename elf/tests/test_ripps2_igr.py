"""Execute the IGR launch contract and native MMCE restore against host mocks."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(os.environ.get('RIPTOPL_DIR', '.')).resolve()
system = (root / 'src/system.c').read_text()
mmce = (root / 'src/mmcesupport.c').read_text()


def function(text, name):
    match = re.search(r'^(?:static )?(?:const char \*|void|int|unsigned int)\s*' + name + r'\(', text, re.M)
    assert match, name
    start = text.index('{', match.start())
    depth = 1
    at = start + 1
    while depth:
        depth += (text[at] == '{') - (text[at] == '}')
        at += 1
    return text[match.start():at]


cc = shutil.which('cc') or shutil.which('gcc')
assert cc, 'A host C compiler is required for the IGR regression tests'


def run(source, name, td):
    file = td / (name + '.c')
    exe = td / name
    file.write_text(source)
    subprocess.run([cc, '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(root),
                    str(file), str(root / 'src/elfprobe.c'), '-I', str(root / 'include'), '-llzma', '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, cwd=td)


with tempfile.TemporaryDirectory() as temp:
    td = Path(temp)
    helpers = '\n'.join(function(system, f) for f in (
        'sysStartupShapeOk', 'neutrinoArgHasActiveFlag', 'neutrinoArgActiveValue'))
    contract = system[system.index('static char sysIgrArg'):system.index('static int sysRunNeutrinoLaunch(')]
    run(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define ripps2Diag(...) ((void)0)
#define COMPAT_MODE_6 32
#define NF_IGR 0x400
#define NF_MMCE_GAMEID 0x800
typedef struct { char arg[2][160]; } neutrino_vmc_args_t;
static char gNeutrinoArgs[256], gExitPath[256], boot[256] = "mmce0:/RIPPS2.ELF";
static int flags = NF_IGR | NF_MMCE_GAMEID, available = 1, seenMask;
static int sysNeutrinoTakes(const char *p, unsigned bit) { (void)p; return (flags & bit) != 0; }
static int ripps2GetBootPath(char *p, int n) { snprintf(p,n,"%s",boot); return boot[0] != 0; }
static int mmceGameIDSlot(int mask) { seenMask=mask; return available && !(mask & 1) ? 0 : -1; }
''' + helpers + contract + r'''
int main(void) {
    neutrino_vmc_args_t vmc = {{{0}}};
    const char *p="mmce0:/neutrino/neutrino.elf", *g="SLUS_203.12";
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(!strcmp(sysIgrArg,"-igr=hdd"));
    assert(!strcmp(sysIgrGameArg,"-mmce_gameid=0:SLUS_203.12"));
    assert(sysNeutrinoDefersGameID(p,g));
    assert(!sysNeutrinoDefersGameID(NULL,g));
    assert(!sysNeutrinoDefersGameID("other",g));
    assert(!sysNeutrinoDefersGameID(p,"SLUS_111.11"));
    sysPrepareNeutrinoIgr(p,g,COMPAT_MODE_6,NULL,NULL);
    assert(!sysIgrArg[0] && !sysIgrGameArg[0] && !sysNeutrinoDefersGameID(p,g));
    flags=0;
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(!sysIgrArg[0] && !sysIgrGameArg[0]);
    flags=NF_IGR;
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(!strcmp(sysIgrArg,"-igr=hdd") && !sysIgrGameArg[0]);
    flags |= NF_MMCE_GAMEID;
    strcpy(boot,"mc1:/RIPPS2/RIPPS2.ELF");
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(!strcmp(sysIgrArg,"-igr=mc1:/RIPPS2/RIPPS2.ELF"));
    strcpy(gExitPath,"Browser");
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(!strcmp(sysIgrArg,"-igr=hdd"));
    strcpy(gNeutrinoArgs,"-igr=mc0:/GLOBAL.ELF");
    sysPrepareNeutrinoIgr(p,g,0,"-igr=mc1:/GAME.ELF",NULL);
    assert(!sysIgrArg[0] && sysIgrGameArg[0]);
    strcpy(gNeutrinoArgs,"$-igr=mc0:/DISABLED.ELF");
    sysPrepareNeutrinoIgr(p,g,0,"--b -igr=mass:/GAME.ELF",NULL);
    assert(!strcmp(sysIgrArg,"-igr=hdd") && sysIgrGameArg[0]);
    gNeutrinoArgs[0]=0;
    sysPrepareNeutrinoIgr(p,g,0,"-igr=mass:/UNSUPPORTED.ELF",NULL);
    assert(!sysIgrArg[0] && !sysIgrGameArg[0] && !sysIgrDeferred);
    strcpy(vmc.arg[0],"-mc0=mass:/VMC/card.bin");
    sysPrepareNeutrinoIgr(p,g,0,NULL,&vmc);
    assert(seenMask==1 && !sysIgrGameArg[0]);
    sysPrepareNeutrinoIgr(p,g,0,"-mc0=foo -mc1=bar",NULL);
    assert(seenMask==3 && !sysIgrGameArg[0]);
    available=0;
    sysPrepareNeutrinoIgr(p,g,0,NULL,NULL);
    assert(sysIgrArg[0] && !sysIgrGameArg[0]);
    sysPrepareNeutrinoIgr(p,g,0,"-mmce_gameid=1:SLUS_203.12",NULL);
    assert(sysIgrDeferred && !sysIgrGameArg[0]);
    puts("Neutrino IGR: return targets, overrides, stale launches, Mode 6, VMC and absent cards passed");
    return 0;
}
''', 'contract', td)

    # Read real fake ELF files with NUL-terminated parser literals, including a
    # literal split at the 32 KiB read boundary and an upstream version sidecar.
    probe = system[system.index('#define NF_CFG'):system.index('// 1 when the Neutrino at neutrinoPath')]
    run(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include "include/elfprobe.h"
#define LOG(...) ((void)0)
''' + probe + r'''
int main(void) {
    FILE *f=fopen("version.txt","wb"); fputs("v1.8.0\n",f); fclose(f);
    f=fopen("neutrino.elf","wb");
    for(int i=0;i<32766;i++) fputc(0,f);
    const char tokens[]="-igr=\0-dvd=\0-mmce_gameid=\0";
    fwrite(tokens,1,sizeof(tokens),f); fclose(f);
    sysNeutrinoReadFlags("./neutrino.elf");
    assert((sysNeutrinoFlagSet & (NF_IGR|NF_MMCE_GAMEID)) == (NF_IGR|NF_MMCE_GAMEID));
    f=fopen("neutrino.elf","wb"); fputs("packed unknown ELF",f); fclose(f);
    sysNeutrinoReadFlags("./neutrino.elf");
    assert(!(sysNeutrinoFlagSet & (NF_IGR|NF_MMCE_GAMEID)));
    f=fopen("neutrino.elf","wb");
    const char stock[]="-dvd=\0 usage -igr=<target> -mmce_gameid=<slot>:<id>";
    fwrite(stock,1,sizeof(stock),f); fclose(f);
    sysNeutrinoReadFlags("./neutrino.elf");
    assert(!(sysNeutrinoFlagSet & (NF_IGR|NF_MMCE_GAMEID)));
    puts("Neutrino capability probing: sidecar, boundary, packed and stock cases passed");
    return 0;
}
''', 'probe', td)

    # Execute the real native IRX command/settle logic with a simulated SIO2 device.
    run(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char u8;
#define MMCE_IGR_HOST_TEST
static int commands, statusCalls, fail, busy, elapsed;
static u8 sent[2][8];
static void delay_us(int us) { elapsed += us/1000; }
static int mmce_sio2_tx_rx_pio(int port, u8 txlen, u8 rxlen, u8 *tx, u8 *rx) {
    assert(port==3); memset(rx,0,rxlen); rx[1]=0xaa;
    if(tx[1]==2) { statusCalls++; if(fail) return -1; rx[4]=busy || statusCalls==3; return 0; }
    assert(commands<2 && (tx[1]==4 || tx[1]==6));
    memcpy(sent[commands++],tx,txlen);
    return fail==2 ? -1 : 0;
}
#include "modules/iopcore/mmceigr/mmceigr.c"
int main(void) {
    assert(restore(3,"2002a0003")==0);
    assert(commands==2 && sent[0][3]==0 && sent[0][5]==0 && sent[0][6]==42);
    assert(sent[1][4]==0 && sent[1][5]==3 && elapsed>=4000);
    commands=statusCalls=elapsed=0;
    assert(restore(3,"100000000")==0 && commands==1 && sent[0][3]==1);
    commands=statusCalls=elapsed=0; fail=1;
    assert(restore(3,"200010001")==-1 && commands==1 && elapsed==60000);
    commands=statusCalls=elapsed=0; fail=0; busy=1;
    assert(restore(3,"200010001")==-1 && commands==1 && elapsed==60000);
    commands=0; fail=2; busy=0;
    assert(restore(3,"200010001")==-1 && commands==1);
    commands=0;
    assert(restore(3,"000000000")==0 && commands==0);
    assert(restore(3,"2ffff0001")==-1 && commands==0);
    assert(restore(3,"200010000")==-1 && commands==0);
    assert(restore(3,"2nope0001")==-1 && commands==0);
    puts("Native MMCE restore: numbered card/channel, boot fallback, errors, delayed busy and timeouts passed");
    return 0;
}
''', 'restore', td)

    capture = mmce[mmce.index('static char mmcePrevious'):mmce.index('int mmceSendGameID(')]
    run(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "include/mmcereturn.h"
#include "include/elfprobe.h"
#define LOG(...) ((void)0)
#define _l(x) "protected"
#define MMCE_GAMEID_START_MS 2000
#define MMCE_PRESENCE_PROBE_MAX 3
#define MMCE_PRESENCE_RETRY_US 200000
static int gMMCEIGRSlot, gMMCEEnableGameID=1, mmceModLoaded=1;
static char mmcePrefix[]="mmce0:/", mmceGameIdTarget[8];
static int card=42, channel=3, sendError, deferred, sends, queries, present=3, missedPings, waits;
static void mmceGetDeviceRoot(char *p, int n) { snprintf(p,n,"%s",mmcePrefix); }
static int sysNeutrinoDefersGameID(const char *p,const char *g) { (void)p; (void)g; return deferred; }
static void guiWarning(const char *s,int n) { (void)s; (void)n; }
static void ripps2Diag(const char *s,...) { (void)s; }
static void DelayThread(int us) { (void)us; waits++; }
static int mmceWaitCardReady(const char *p) { (void)p; return 1; }
static int fileXioDevctl(const char *p,int cmd,void *a,int al,void *b,int bl) {
    (void)a; (void)al; (void)b; (void)bl;
    if(cmd==1 && missedPings>0) { missedPings--; return -1; }
    if(!(present & (1 << (p[4]-'0')))) return -1;
    if(cmd==3) { queries++; return card; }
    if(cmd==5) { queries++; return channel; }
    if(cmd==8) { assert(queries>=2); sends++; return sendError ? -1 : 0; }
    return 0;
}
''' + capture + function(mmce, 'mmceSendGameID') + r'''
int main(void) {
    char args[MMCE_RETURN_ARG_SIZE];
    assert(mmceGameIDSlot(0)==0 && mmceGameIDSlot(1)==1 && mmceGameIDSlot(3)==-1);
    present=0; waits=0;
    assert(mmceGameIDSlot(0)==-1 && waits==4);
    present=3; gMMCEEnableGameID=0; waits=0;
    assert(mmceGameIDSlot(0)==-1 && waits==0);
    gMMCEEnableGameID=1; mmceModLoaded=0;
    assert(mmceGameIDSlot(0)==-1 && waits==0);
    mmceModLoaded=1;
    missedPings=2; waits=0;
    assert(mmceGameIDSlot(0)==0 && waits==2);
    missedPings=2; waits=0;
    assert(mmceSendGameID("SLUS_203.12",NULL,0)==1 && sends==1 && waits>=2);
    mmceReturnArgs(args);
    assert(!strcmp(args,"R2002a0003000000000") && mmceReturnNeeded());
    gMMCEIGRSlot=3;
    mmceReturnArgs(args);
    assert(!strcmp(args,"R2002a0003100000000"));
    gMMCEIGRSlot=0; sendError=1;
    assert(mmceSendGameID("SLUS_203.12",NULL,0)==0);
    assert(!mmceReturnNeeded());
    sendError=0; card=0;
    assert(mmceSendGameID("SLUS_203.12",NULL,1)==1);
    mmceReturnArgs(args);
    assert(!strcmp(args,"R000000000100000000"));
    sends=queries=0;
    assert(mmceSendGameID("SLUS_203.12","mc0:/neutrino.elf",0)==0);
    assert(!sends && !queries && !mmceReturnNeeded());
    deferred=1;
    assert(mmceSendGameID("SLUS_203.12","mmce0:/neutrino.elf",0)==0);
    assert(!sends && !queries && !mmceReturnNeeded());
    deferred=0; gMMCEEnableGameID=0;
    assert(mmceSendGameID("SLUS_203.12",NULL,0)==0 && !sends);
    puts("MMCE launch capture: exact slot/card/channel, fallback, failed sends, VMC and deferral passed");
    return 0;
}
''', 'capture', td)

# Cross-file ordering: no launcher GameID can run before LUNA's deferred send;
# restore happens after shutdown/IOP reboot and before MCMAN/Exit.
send = function(mmce, 'mmceSendGameID')
assert send.index('sysNeutrinoDefersGameID') < send.index('fileXioDevctl(mmceDevice, 0x8')
assert send.index('previousCard =') < send.index('fileXioDevctl(mmceDevice, 0x8') < send.index('memcpy(mmcePrevious +')
launch = function(system, 'sysRunNeutrinoLaunch')
assert launch.index('sysPrepareNeutrinoIgr') < launch.index('argv[argc++] = sysIgrArg') < launch.index('int pool =')
pad = (root / 'ee_core/src/padhook.c').read_text()
thread = function(pad, 'IGR_Thread')
assert thread.index('oplIGRShutdown(0)') < thread.index('Reset_Iop') < thread.index('config->MmceReturnArgs') < thread.index('IGR_Exit(0)')
print('IGR integration ordering passed')
