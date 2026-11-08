"""Every image in a psx-place post goes inside [SPOILER] tags (a moderator's warning, 11/06). This wraps each [IMG] that is not
already inside a spoiler (with the [URL] round it, when it is a linked picture) in a spoiler titled from the picture's file name.

    python spoilerize.py FILE.bbcode|FILE.txt ...      (rewrites each in place; prints how many it wrapped)
"""
import os
import re
import sys

TAG = re.compile(r'\[SPOILER[^\]]*\]|\[/SPOILER\]|(\[URL=[^\]]*\]\s*)?\[IMG[^\]]*\](.*?)\[/IMG\](\s*\[/URL\])?', re.I | re.S)


def title(url):
    name = os.path.splitext(url.split('?')[0].rstrip('/').split('/')[-1])[0]
    name = re.sub(r'[-_]+', ' ', name).strip()
    return name[:60] or 'Picture'


def spoilerize(text):
    out, depth, last, n = [], 0, 0, 0
    for m in TAG.finditer(text):
        t = m.group(0)
        if t.upper().startswith('[SPOILER'):
            depth += 1
            continue
        if t.upper().startswith('[/SPOILER'):
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        linked = bool(m.group(1)) and bool(m.group(3))
        start, end = (m.start(), m.end()) if linked else (m.start() + len(m.group(1) or ''), m.end() - len(m.group(3) or ''))
        unit = text[start:end]
        out.append(text[last:start])
        out.append('[SPOILER="%s"]%s[/SPOILER]' % (title(m.group(2)), unit))
        last = end
        n += 1
    out.append(text[last:])
    return ''.join(out), n


if __name__ == '__main__':
    for p in sys.argv[1:]:
        s = open(p, encoding='utf-8').read()
        new, n = spoilerize(s)
        if n:
            open(p, 'w', encoding='utf-8', newline='').write(new)
        print('%s: %d wrapped' % (os.path.basename(p), n))
