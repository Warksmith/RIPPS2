"""Run against the patched BIBLE tree used by build_igr_bridge.sh."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

source = (Path(sys.argv[1]) / 'src/main.c').read_text(encoding='utf-8')
assert 'static int g_hotkey_launches_enabled = 0;' in source
start = source.index('static void PollEmergencyComboWindow(')
end = source.index('\nstatic int IsDiscTypeStoppable', start)
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    c = path / 'chord.c'
    c.write_text(r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef unsigned long long u64;
''' + source[start:end] + r'''
int main(void) {
    u64 deadline=2000;
    PollEmergencyComboWindow(&deadline);
    assert(deadline==2000);
    PollEmergencyComboWindow(NULL);
    puts("BIBLE IGR bridge: AUTO-only startup, no rescue or launch hotkeys");
}
''', encoding='utf-8')
    exe = path / 'chord'
    subprocess.run([shutil.which('cc') or 'gcc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
