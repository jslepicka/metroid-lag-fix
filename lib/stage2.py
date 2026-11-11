"""Stage 2: the sound and controller routines, sprite drawing, the enemy-hit loop, the frozen-enemy and wall
tests, and the room drawer (asm/sound, sprites, graphics, hit_loop, frozen, walls, room_drawer), on top of
stage 1.

Each source file is split into chunks (';@chunk Name [$ADDR]'). Chunks with an address are pinned there (hooks
and in-place rewrites); the rest go wherever the recorded layout (lib/layout.py) puts them: fixed-bank space
freed by replaced routines, the padding at the end of every bank (chunks named *_P), spare work RAM, and work
RAM the game only uses on the title screen (chunks named *_W must be in work RAM). Work-RAM code is stored in
bank 6 and copied into place by WLoad whenever graphics are loaded.

The build also rewrites some of the game's tables from the input ROM: each bank's sprite placement table as
a block of y offsets followed by a block of x offsets, each area's metatile table as four corner tables, and
the graphics load sequences as lists read from the original code; and it works out, per room, which rows the
room fill can skip (with the Python room drawer, lib/roomdraw.py).
"""
import os, re
import asm6502, frames
from asm6502 import assemble
import layout

ASM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'asm')
NL = chr(10)
ORG = '        .org $%04X' + NL

# sprite placement regions: (pointer table, slots, region lo, region hi); object frames live in every area bank
PLACE_EN = {1: (0x9F0E, 16, 0x9F2E, 0x9FC2), 2: (0x9D78, 14, 0x9D94, 0x9E0A), 3: (0xA540, 16, 0xA560, 0xA5C8),
            4: (0x9E25, 16, 0x9E45, 0x9ED9), 5: (0x9D04, 15, 0x9D22, 0x9DD8)}
PLACE_OBJ = (0x86DF, 15, 0x86FD, 0x87CB)
# fixed-bank space freed by replaced routines (pinned chunks take their own addresses first)
FREE = [(0xF0A0, 0xF0EC), (0xD979, 0xD9A2), (0xC5D7, 0xC6DF), (0xDCB7, 0xDCF4), (0xDDB0, 0xDE34), (0xDE3D, 0xDE46),
        (0xDE47, 0xDF2C), (0xDF32, 0xDFDE), (0xE038, 0xE048), (0xCA35, 0xCAF4), (0xC6E0, 0xC7AA), (0xC7AE, 0xC7D4)]
PAD = [(0xBFA0, 0xBFAF), (0xBFE0, 0xBFF9)]   # zero padding before the reset stub and vectors, the same in banks 0-6:
                                              # chunks named *_P (read-only, gameplay) go there, in every bank
BG_FREE = [(0xE7E1, 0xE81D)]                  # the old wall and floor tile loop
ROOM_FIXED = [(0xEA42, 0xEA5C), (0xEA60, 0xEABB), (0xEF13, 0xEFF3), (0xEFF8, 0xF017), (0xF01C, 0xF033)]
                                              # the old room drawer (the new one still reads its mask table $EFF4 and
                                              # fill table $F018; $EABC-$EAC9 stay: the $FE path and AddToRoomPtr)
GLIST = 0xBF00                                # bank 6: the graphics load lists (were code at $C5D7-$C6DF)
GFX_CODE = (0xC5D7, 0xC6E0)
BANK0_GFX_CALLS = {0x9124: 'GC6D6', 0x9314: 'GTitle2', 0x9367: 'GC6D6', 0x93A8: 'GC6D6'}
WRAM_RES = [(0x74FE, 0x752E)]                 # the room fill table (48 bytes) and its area tag
WRAM_DEAD = [(0x752F, 0x754F), (0x76FC, 0x7738), (0x75E7, 0x7668)]
                                              # stage 1 code no longer reachable: its power-on generator (the unrolled
                                              # code is in the image now), its enemy-hit loop and frozen-enemy box test
WRAM_FREE = [(0x6F50, 0x6FEF), (0x6D4B, 0x6DFF), (0x6C74, 0x6C7F), (0x77E2, 0x77EF), (0x6F22, 0x6F2F), (0x6F31, 0x6F3F),
             (0x6F41, 0x6F4F)] + WRAM_DEAD    # spare work RAM; $6FF0-$6FFA belong to the room drawer
WRAM_TITLE = [(0x6E00, 0x6F1F), (0x0120, 0x019F)]
                                              # title and ending sprite memory, and page 1 below the deepest the stack
                                              # can reach ($01CA; only $0100-$010F are variables): copied only in play
WLOAD = 0xB990                                # bank 6, after the moved graphics table
GFXT = 0xB8C0                                 # bank 6, unused block: the graphics table ($C6E0, 203 bytes) moves here


def off(bank, a): return bank * 0x4000 + a - 0x8000 if a < 0xC000 else 7 * 0x4000 + a - 0xC000


def split_places(prg, bank, spec):
    """Rewrite one placement region as [y bytes][x bytes] and re-point its frames; return N (x = y + N)."""
    ptab, slots, lo, hi = spec
    assert (hi - lo) % 2 == 0
    data = bytes(prg[off(bank, lo):off(bank, hi)])
    n = (hi - lo) // 2
    prg[off(bank, lo):off(bank, hi)] = data[0::2] + data[1::2]
    for k in range(slots):
        a = off(bank, ptab + 2 * k)
        p = prg[a] | prg[a + 1] << 8
        if lo <= p < hi:
            assert (p - lo) % 2 == 0, 'odd placement pointer'
            q = lo + (p - lo) // 2 - 3          # biased: Y starts at 3 (the frame header)
            prg[a] = q & 0xFF; prg[a + 1] = q >> 8
    return n


def gfx_lists(orig_prg):
    """The graphics load sequences at $C5D7-$C6DF (LDY #id / JSR $C7AB ... LDY #id / JMP $C7AB) as lists of ids:
    $FE where the code skips the next load unless $69B3 is zero, $FF at the end of each sequence."""
    out = []; a = GFX_CODE[0]
    while a < GFX_CODE[1]:
        b = [orig_prg[off(7, a + i)] for i in range(5)]
        if b[0] == 0xA0 and b[2] in (0x20, 0x4C) and b[3:] == [0xAB, 0xC7]:
            out.append(b[1])
            if b[2] == 0x4C: out.append(0xFF)
        elif b == [0xAD, 0xB3, 0x69, 0xF0, 0x05]:
            out.append(0xFE)
        else:
            raise SystemExit('unexpected graphics load code at $%04X' % a)
        a += 5
    return out


def chunks(src):
    out = []; cur = None
    for line in src.splitlines(keepends=True):
        m = re.match(r';@chunk\s+(\w+)(?:\s+\$([0-9A-Fa-f]{4}))?', line)
        if m:
            cur = [m.group(1), int(m.group(2), 16) if m.group(2) else None, '']; out.append(cur); continue
        if cur is None: continue
        cur[2] += line
    return out


def regions():
    return ([list(r) + ['pad'] for r in PAD] + [list(r) + ['fixed'] for r in FREE + ROOM_FIXED + BG_FREE] +
            [list(r) + ['wram'] for r in WRAM_FREE] + [list(r) + ['wram_t'] for r in WRAM_TITLE])


ALLOW = {'fixed': ('fixed',), 'fw': ('fixed', 'wram'), 'any': ('fixed', 'wram', 'wram_t')}


def fits(name, kind, region_kind):
    if (region_kind == 'pad') != name.endswith('_P'): return False
    if region_kind == 'pad': return True
    return region_kind in ALLOW[kind] and not (name.endswith('_W') and region_kind == 'fixed')


def place(parts, head, repack=False):
    """parts: [(source, kind)]. Returns (assembled bytes, labels, layout used)."""
    cs = []
    for src, kind in parts:
        cs += [(n, p, body, kind) for n, p, body in chunks(src)]
    s = head; at = 0x2000; starts = {}
    for name, pin, body, kind in cs:                       # measure every chunk
        a0 = pin if pin is not None else at
        s += ORG % a0 + body; starts[name] = a0
        if pin is None: at += 0x200
    o, _ = assemble(s)
    order = sorted(starts.values()) + [0x10000]
    nxt = {a: order[i + 1] for i, a in enumerate(order[:-1])}
    size = {name: max(a for a in o if starts[name] <= a < nxt[starts[name]]) - starts[name] + 1 for name, _, _, _ in cs}
    rec = layout.LAYOUT
    if not repack:
        changed = [n for n, p, b, k in cs if n not in rec or rec[n][1] != size[n]]
        if changed:
            raise SystemExit('code pieces changed size: %s; run build.py with --repack' % ', '.join(changed))
        org = {n: rec[n][0] for n, p, b, k in cs}
        for n, p, b, k in cs:                               # pinned pieces stay pinned
            assert p is None or org[n] == p, n
    else:
        import pack
        org = pack.pack(cs, size, regions(), fits)
    check(cs, org, size)
    s = head
    for name, pin, body, kind in cs:
        s += ORG % org[name] + body
    out, lab = assemble(s)
    return out, lab, {n: (org[n], size[n]) for n, p, b, k in cs}


def check(cs, org, size):
    """Every unpinned piece lies inside a region it may use, and no two pieces overlap."""
    regs = regions(); used = []
    for name, pin, body, kind in cs:
        a, n = org[name], size[name]
        if pin is None:
            assert any(r[0] <= a and a + n - 1 <= r[1] and fits(name, kind, r[2]) for r in regs), 'piece %s at $%04X' % (name, a)
        for b, m, other in used:
            assert a + n <= b or b + m <= a, 'pieces %s and %s overlap' % (name, other)
        used.append((a, n, name))


WLOAD_SRC = """
; bank 6: copy the work-RAM code segments into work RAM (called from LoadGFX with bank 6 mapped).
        .org $%04X
WLoad:  LDX #$00
wl1:    LDA WTab+1,X
        BEQ wl9
        CMP #$FF                ; marker: the gameplay-only segments follow
        BNE wl1a
        LDA $1D                 ; title / ending: leave their sprite RAM alone
        BNE wl9
        INX
        INX
        INX
        INX
        INX
        BNE wl1
wl1a:   STA $03
        LDA WTab,X
        STA $02
        LDA WTab+2,X
        STA $00
        LDA WTab+3,X
        STA $01
        LDY WTab+4,X
wl2:    DEY
        LDA ($00),Y
        STA ($02),Y
        TYA
        BNE wl2
        TXA
        CLC
        ADC #$05
        TAX
        BNE wl1
wl9:    LDX $23                 ; the area's fill table for the room drawer (asm/room_drawer.asm)
        DEX
        CPX #$05
        BCS wl10
        LDA TBOFF,X
        TAX
        LDY #$00
wt1:    LDA TBALL,X
        STA $74FE,Y
        INX
        INY
        CPY #$30
        BNE wt1
        LDA $23
        STA $752E
wl10:   RTS
TBOFF:  .byte $00,$30,$60,$90,$C0
TBALL:
%s
WTab:
"""


def stage1_wram(prg):
    """Stage 1's work-RAM code: the static image its power-on copier assembles from the chunk table at bank 0
    $8206 (bank, lo, hi, length ... $FF) into $74C0, plus what its generator writes: the sprite clear at $7400
    (64 x STA $0200+4i) and the HUD copy at $6C80 (40 x LDA #template / STA $0200+i,X, then JMP HudTail)."""
    w = {}; i = off(0, 0x8206); img = []
    while prg[i] != 0xFF:
        b, lo, hi, n = prg[i], prg[i + 1], prg[i + 2], prg[i + 3]
        a = lo | hi << 8; img += list(prg[off(b, a):off(b, a) + n]); i += 4
    for k, v in enumerate(img): w[0x74C0 + k] = v
    for k in range(64): w[0x7400 + 3 * k] = 0x8D; w[0x7401 + 3 * k] = 4 * k; w[0x7402 + 3 * k] = 0x02
    pat = bytes([0x8A, 0x08, 0x18, 0x69, 0x28, 0xAA, 0x28, 0xA9, 0x28, 0xA0, 0x28, 0xC0, 0x28, 0x60])
    ht = 0x74C0 + bytes(img).index(pat)                      # HudTail
    for x in range(40):
        a = 0x6C80 + 5 * x
        w[a] = 0xA9; w[a + 1] = prg[off(7, 0xE1B9 + x)]; w[a + 2] = 0x9D; w[a + 3] = x; w[a + 4] = 0x02
    w[0x6D48] = 0x4C; w[0x6D49] = ht & 255; w[0x6D4A] = ht >> 8
    for lo, hi in WRAM_DEAD + WRAM_RES:
        for a in range(lo, hi + 1): w.pop(a, None)
    return w


def fill_tables(orig_prg):
    """Per area bank 1-5, per room (48 bytes each): the byte offset of the first fill store the room drawer runs.
    The fill stores go outside in (rows 0, 14, 1, 13, ...); k = min(top, bottom) name-table rows the room's
    structures cover completely lets it skip 2k stores (6k bytes); 45 = every row covered (attribute fill only)."""
    import roomdraw as R
    frames.load(orig_prg)
    class D2(R.Draw):
        def init_tables(self):
            super().init_tables(); self.track = set()
        def put(self, addr, v):
            if hasattr(self, 'track'): self.track.add(addr & 0x3FF)
            super().put(addr, v)
    out = []
    for bank in R.AREA_BANKS:
        rd16 = lambda a: frames.rd(bank, a) | frames.rd(bank, a + 1) << 8
        n = (rd16(R.AREA_POINTERS + 2) - rd16(R.AREA_POINTERS)) // 2
        assert n <= 48
        tab = []
        for room in range(n):
            nt = {a for a in D2(bank, room, 0x60).track if a < 0x3C0}
            full = [all((r * 64 + k) in nt for k in range(64)) for r in range(15)]
            if all(full): tab.append(45); continue
            t = 0
            while full[t]: t += 1
            bb = 0
            while full[14 - bb]: bb += 1
            tab.append(6 * min(t, bb))
        out += tab + [0] * (48 - n)
    return out


def meta_counts(prg):
    """Metatiles per area bank (1..5): the highest metatile any room's structures use, plus one."""
    rd = lambda b, a: prg[b * 0x4000 + a - 0x8000]
    rd16 = lambda b, a: rd(b, a) | rd(b, a + 1) << 8
    out = {}
    for bank in range(1, 6):
        room_t, st_t = rd16(bank, 0x959A), rd16(bank, 0x959C)
        used = set()
        for r in range((st_t - room_t) // 2):
            p = rd16(bank, room_t + 2 * r) + 1
            while rd(bank, p) not in (0xFF, 0xFD, 0xFE): used.add(rd(bank, p + 1)); p += 3
        mx = 0
        for sidx in used:
            p = rd16(bank, st_t + 2 * sidx)
            assert rd(bank, p) != 0xFF, 'empty structure'
            while rd(bank, p) != 0xFF:
                n = rd(bank, p) & 15 or 16
                mx = max([mx] + [rd(bank, p + 1 + k) for k in range(n)]); p += n + 1
        out[bank] = mx + 1
    return out


def split_meta(prg, orig_prg):
    """Each area's metatile table as four tables M apart (top left, top right, bottom left, bottom right)."""
    mc = meta_counts(orig_prg)
    for bank, m in mc.items():
        meta = orig_prg[off(bank, 0x959E)] | orig_prg[off(bank, 0x959F)] << 8
        a = off(bank, meta)
        data = bytes(orig_prg[a:a + 4 * m])
        assert bytes(prg[a:a + 4 * m]) == data, 'stage 1 changed a metatile table'
        prg[a:a + 4 * m] = data[0::4] + data[1::4] + data[2::4] + data[3::4]
    return mc


def read(name): return open(os.path.join(ASM, name)).read()


def segments(addrs):
    if not addrs: return []
    out = []; s0 = addrs[0]; p = s0
    for a in addrs[1:]:
        if a != p + 1 or a - s0 >= 255: out.append((s0, p)); s0 = a
        p = a
    out.append((s0, p)); return out


def build(rom, orig_prg, repack=False):
    """rom: bytearray, the stage 1 iNES file (16-byte header). orig_prg: the original 128K PRG. Applied in place.
    Returns the layout used."""
    prg = memoryview(rom)[16:]
    asm6502.ROM_READ = lambda bk, a: orig_prg[off(bk, a)]
    ne = [0] * 8
    for bank, spec in PLACE_EN.items():
        ne[bank] = split_places(prg, bank, spec)
    nobj = None
    for bank in range(1, 6):
        n = split_places(prg, bank, PLACE_OBJ)
        assert nobj in (None, n); nobj = n
    glists = gfx_lists(orig_prg)
    for i, v in enumerate(glists): prg[off(6, GLIST + i)] = v
    subst = lambda s: s.replace('GFXT', '$%04X' % GFXT).replace('WLOADA', '$%04X' % WLOAD).replace('GLIST', '$%04X' % GLIST)
    src = subst(read('sprites.asm') + read('graphics.asm'))
    src = src[:src.index(';@chunk GfxJ')]                # sprite pieces (+ graphics.asm's preamble); the graphics
    gsrc = subst(read('graphics.asm'))                   # pieces are placed on their own, fixed bank only
    src += read('frozen.asm') + read('hit_loop.asm') + read('walls.asm') + read('sound.asm')
    rsrc = read('room_drawer.asm')
    for b, m in split_meta(prg, orig_prg).items(): rsrc = rsrc.replace('$MT%d' % b, '$%02X' % m)
    prg[off(6, GFXT):off(6, GFXT) + 203] = orig_prg[off(7, 0xC6E0):off(7, 0xC6E0) + 203]
    src = src.replace('$NOBJ', '$%02X' % nobj)
    for i in range(8): src = src.replace('$NE%d' % i, '$%02X' % ne[i])
    head = src[:re.search(r'^;@chunk', src, re.M).start()] + rsrc[:re.search(r'^;@chunk', rsrc, re.M).start()]
    out, lab, used = place([(src, 'fw'), (gsrc, 'fixed'), (rsrc, 'any')], head, repack)
    wram = stage1_wram(bytes(prg))
    for a, v in out.items():
        if 0x6000 <= a < 0x8000 or 0x100 <= a < 0x200: wram[a] = v; continue
        if 0xB4BD <= a <= 0xB4FA:                        # the sound routine the code banks 0-5 share
            for bk in range(6): prg[off(bk, a)] = v
            continue
        if 0xBFA0 <= a < 0xBFFA:                         # bank padding: the same in banks 0-6
            for bk in range(7): prg[off(bk, a)] = v
            continue
        assert a >= 0xC000, hex(a)
        prg[off(7, a)] = v
    for a, name in BANK0_GFX_CALLS.items():              # bank 0 callers of the old load sequences
        assert prg[off(0, a)] == 0x20
        t = lab[name] & 0xFFFF
        prg[off(0, a) + 1] = t & 255; prg[off(0, a) + 2] = t >> 8
    # work-RAM image: contiguous segments, stored in bank 6 after WLoad and its table
    intitle = lambda a: any(lo <= a <= hi for lo, hi in WRAM_TITLE)
    segs = segments(sorted(a for a in wram if not intitle(a)))
    tsegs = segments(sorted(a for a in wram if intitle(a)))
    ft = fill_tables(orig_prg)
    wsrc = WLOAD_SRC % (WLOAD, NL.join('        .byte ' + ','.join('$%02X' % v for v in ft[i:i + 16]) for i in range(0, len(ft), 16)))
    nseg = len(segs) + len(tsegs) + (1 if tsegs else 0)
    code0, _ = assemble(wsrc + '        .byte $00,$00' + NL)
    tab_end = max(code0) + 1 + 5 * nseg + 2
    blocks = [[tab_end, 0xBEFF], [0x99C0, 0x9D9F], [0x8AA0, 0x8BDF], [0x98A0, 0x997F], [GLIST + len(glists), 0xBF9F]]
    place_at = {}
    for lo, hi in segs + tsegs:                          # bank 6 storage for each segment, first fit
        n = hi - lo + 1
        for bl in blocks:
            if bl[1] - bl[0] + 1 >= n: place_at[lo] = bl[0]; bl[0] += n; break
        else: raise SystemExit('bank 6 has no room for a %d-byte work-RAM segment' % n)
    tab = ''
    for lo, hi in segs + ([(None, None)] if tsegs else []) + tsegs:
        if lo is None:
            tab += '        .byte $00,$FF,$00,$00,$00' + NL; continue
        d = place_at[lo]; n = hi - lo + 1
        tab += ('        .byte $%02X,$%02X,$%02X,$%02X,$%02X' + NL) % (lo & 255, lo >> 8, d & 255, d >> 8, n)
    code, _ = assemble(wsrc + tab + '        .byte $00,$00' + NL)
    assert max(code) + 1 <= tab_end
    for a, v in code.items(): prg[off(6, a)] = v
    for lo, hi in segs + tsegs:
        d = place_at[lo]
        for a in range(lo, hi + 1): prg[off(6, d)] = wram[a]; d += 1
    return used
