"""Check that the assembly sources contain no code or data of the original game.

Builds the ROM as build.py does, recording every assembly, and reports each run of source lines (outside
.rom lines, which copy from the input ROM at build time) whose bytes reproduce MIN or more consecutive bytes of
the original ROM. Short runs are common 6502 idioms (a load and a store, a JSR to a game routine); longer ones
are worth a look: code copied from the game should be written as .rom $ADDR,n instead.

usage: python tools/check_sources.py "Metroid (USA).nes" [MIN]   (MIN defaults to 6)
"""
import os, sys, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'lib')); sys.path.insert(0, HERE)
import asm6502, stage1, stage2, build

MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 6
header, prg = build.read_rom(sys.argv[1])
calls = []
real = asm6502.assemble
def recording(src, origin=None, listing=None):
    lst = []
    r = real(src, origin, lst)
    calls.append((src, lst, r[0]))
    return r
stage1.assemble = stage2.assemble = recording
build.build(prg)

idx = {}                                           # 6-byte index of the original PRG
for i in range(len(prg) - MIN + 1): idx.setdefault(prg[i:i + MIN], []).append(i)
files = {f: open(os.path.join(HERE, 'asm', f)).read().splitlines() for f in sorted(os.listdir(os.path.join(HERE, 'asm')))}

def where(lines):
    """(file, first line number) of these consecutive source lines."""
    key = [l.rstrip() for l in lines]
    for f, fl in files.items():
        for i in range(len(fl) - len(key) + 1):
            if all(fl[i + k].rstrip() == key[k] for k in range(len(key))): return f, i + 1
    return '(generated)', 0

def addr(i):
    b = i // 0x4000
    return '%s$%04X' % ('' if b == 7 else '%d:' % b, (0xC000 if b == 7 else 0x8000) + i % 0x4000)

found = {}
for src, lst, out in calls:
    lines = src.splitlines()
    run = []                                        # [(line index, bytes)] contiguous in address
    def scan(run):
        data = b''.join(b for _, b in run)
        owner = [ln for ln, b in run for _ in b]
        i = 0
        while i <= len(data) - MIN:
            best = (0, None)
            for p in idx.get(data[i:i + MIN], ()):
                n = MIN
                while i + n < len(data) and p + n < len(prg) and data[i + n] == prg[p + n]: n += 1
                if n > best[0]: best = (n, p)
            if best[0]:
                lns = sorted(set(owner[i:i + best[0]]))
                f, l0 = where([lines[k] for k in range(lns[0], lns[-1] + 1)])
                found[(f, l0, lns[-1] - lns[0] + 1)] = (best[0], best[1], lines[lns[0]].strip())
                i += best[0]
            else:
                i += 1
    prev_end = None
    for ln, start, end in lst:
        text = re.sub(r'^([A-Za-z_]\w*:\s*)+', '', lines[ln].split(';')[0].strip())
        if end == start or text.startswith('.rom'):
            if run: scan(run); run = []
            prev_end = None; continue
        if any(a not in out for a in range(start, end)):
            if run: scan(run); run = []
            prev_end = None; continue
        if prev_end is not None and start != prev_end:
            scan(run); run = []
        run.append((ln, bytes(out[a] for a in range(start, end)))); prev_end = end
    if run: scan(run)

print('Source lines that reproduce %d+ consecutive bytes of the original ROM:' % MIN)
for (f, l0, nlines), (n, p, first) in sorted(found.items()):
    print('  %-18s line %4d (+%d lines): %3d bytes = original %s   %s' % (f, l0, nlines - 1, n, addr(p), first[:50]))
print('%d runs, %d bytes; %d runs of 8+ bytes' % (len(found), sum(v[0] for v in found.values()), sum(1 for v in found.values() if v[0] >= 8)))
