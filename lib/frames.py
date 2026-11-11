"""Parse Metroid metasprite frames (enemy frames per area bank, object frames in the shared library)."""
PRG = None

def load(prg):
    """Set the original 128K PRG that frames are read from."""
    global PRG
    PRG = bytes(prg)

# bank: (T1, T2, place table, frame count)
AREAS = {1: (0x9DE0, 0x9EE0, 0x9F0E, 148), 2: (0x9C64, 0x9D64, 0x9D78, 138), 3: (0xA42C, 0xA52C, 0xA540, 138),
         4: (0x9CF7, 0x9DF7, 0x9E25, 151), 5: (0x9BF0, 0x9CF0, 0x9D04, 138)}
OBJ = (0x860B, 0x86DF, 106)

def rd(bank, a):
    if a >= 0xC000: return PRG[7 * 0x4000 + a - 0xC000]
    return PRG[bank * 0x4000 + a - 0x8000]
def rd16(bank, a): return rd(bank, a) | rd(bank, a + 1) << 8

def frame_ptrs(bank):
    """[(frame id, frame ptr, place ptr)] for an area bank (enemy frames), or bank=None for objects (read via bank 1)."""
    out = []
    if bank is None:
        t, p, n = OBJ
        for i in range(n):
            fp = rd16(1, t + 2 * i); hdr = rd(1, fp)
            out.append((i, fp, rd16(1, p + 2 * (hdr & 0x0F))))
        return out
    t1, t2, p, n = AREAS[bank]
    for i in range(n):
        fp = rd16(bank, (t1 if i < 128 else t2) + 2 * (i & 0x7F)); hdr = rd(bank, fp)
        out.append((i, fp, rd16(bank, p + 2 * (hdr & 0x0F))))
    return out

def parse(bank, fp, pp):
    """Decode the stream from byte 3. Returns dict(hdr, ry, rx, ops) where ops are
    ('T', tile, dy, dx) | ('FC', dy, dx) | ('FD', byte) | ('FE',) ; ends at FF. dy/dx raw placement bytes."""
    b = bank or 1
    hdr, ry, rx = rd(b, fp), rd(b, fp + 1), rd(b, fp + 2)
    i, j, ops = 3, 0, []
    while True:
        if i > 200: raise ValueError('runaway frame %04X' % fp)
        c = rd(b, fp + i)
        if c == 0xFF: ops.append(('FF', i)); break
        if c == 0xFC: ops.append(('FC', rd(b, fp + i + 1), rd(b, fp + i + 2))); i += 3; continue
        if c == 0xFD: ops.append(('FD', rd(b, fp + i + 1))); i += 2; continue
        if c == 0xFE: ops.append(('FE',)); j += 2; i += 1; continue
        ops.append(('T', c, rd(b, pp + j), rd(b, pp + j + 1))); j += 2; i += 1
    return dict(hdr=hdr, ry=ry, rx=rx, ops=ops)

def special(f):
    return any(o[0] == 'T' and (0x80 <= o[2] < 0x90 or 0x80 <= o[3] < 0x90) for o in f['ops'])

